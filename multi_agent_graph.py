import os
import sqlite3
from typing import Annotated, TypedDict
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import AIMessage, HumanMessage,BaseMessage
from langchain_core.tools import tool
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.sqlite import SqliteSaver
from groq import BadRequestError # Import the specific error
from datetime import datetime


from tools import retrieve_concept_definition, check_mastery_level, update_mastery_state
from agents_config import TUTOR_PROMPT, EVALUATOR_PROMPT

load_dotenv()

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.0, api_key=os.environ.get("GROQ_API_KEY"))

@tool
def evaluate_student_answer(answer: str = "", topic: str = "", user_id: str = ""):
    """Use this tool when the student has answered your scaffolding question and needs to be graded."""
    return f"Successfully handed over to the Mastery Evaluator for grading in {topic}."

# --- Split Tools into Safe vs High-Risk ---
tutor_tools = [retrieve_concept_definition, check_mastery_level, evaluate_student_answer]
tutor_llm = llm.bind_tools(tutor_tools)

# The grading tool is our high-risk tool that requires human approval
evaluator_tools = [update_mastery_state]
evaluator_llm = llm.bind_tools(evaluator_tools)

def tutor_node(state):
    try:
        # Standard invocation
        response = tutor_llm.invoke([TUTOR_PROMPT] + state["messages"])
        
        # Log response for debugging
        print(f"🤖 [Tutor Node] AI Response Type: {type(response)}")
        if response.content:
            print(f"🤖 [Tutor Node] Response Content: {response.content[:100]}...")
        if response.tool_calls:
            print(f"🤖 [Tutor Node] Tool Calls: {[t['name'] for t in response.tool_calls]}")
            
        return {"messages": [response]}
        
    except Exception as e:
        # Log to terminal for the developer
        print(f"❌ [Tutor Error] {str(e)}")
        
        # Log to file for deep debugging
        with open("debug_log.txt", "a") as f:
            import traceback
            f.write(f"\n--- {datetime.now()} ---\n")
            f.write(f"Tutor Node Error: {str(e)}\n")
            f.write(traceback.format_exc())

        # Check if this was a known security violation attempt
        if "update_mastery_state" in str(e):
            return {"messages": [AIMessage(content="I'm sorry, I cannot perform grading operations. Please answer my question so I can transfer you to the evaluator.")]}
        
        # Otherwise, tell the user something went wrong technically
        return {"messages": [AIMessage(content="I'm having a bit of trouble processing that. Could you please try rephrasing or selecting your subject again?")]}
        
        # If it's a different error, raise it
        raise e

def evaluator_node(state: AgentState):
    response = evaluator_llm.invoke([EVALUATOR_PROMPT] + state["messages"])
    print(f"🎓 [Evaluator Node] Tool Calls: {[t['name'] for t in response.tool_calls] if response.tool_calls else 'none'}")
    print(f"🎓 [Evaluator Node] Content: {response.content[:100] if response.content else '(empty)'}")
    return {"messages": [response]}

# Create TWO separate tool nodes
tutor_tools_node = ToolNode(tutor_tools)
evaluator_tools_node = ToolNode(evaluator_tools) # This is the high-risk node

# --- Routing Logic ---
def tutor_router(state: AgentState) -> str:
    messages = state["messages"]
    last_message = messages[-1]

    # Loop detection: If the conversation has too many messages, stop the loop.
    if len(messages) > 20:
        print("⚠️ [Loop Detection] Loop detected. Forcing synthesis.")
        # If the last message was a tool call, we MUST go to the tools node first to get results
        if last_message.tool_calls:
            return "tutor_tools"
        # If we have tool results but are about to loop again, stop and summarize
        return END

    if last_message.tool_calls:
        return "tutor_tools"
    return END

def evaluator_router(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "evaluator_tools"
    return END

def tutor_tool_router(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if last_message.name == "evaluate_student_answer":
        return "evaluator"
    return "tutor"

def evaluator_tool_router(state: AgentState) -> str:
    return "evaluator"

# --- Build Graph ---
workflow = StateGraph(AgentState)

workflow.add_node("tutor", tutor_node)
workflow.add_node("evaluator", evaluator_node)
workflow.add_node("tutor_tools", tutor_tools_node)
workflow.add_node("evaluator_tools", evaluator_tools_node)

workflow.set_entry_point("tutor")

workflow.add_conditional_edges("tutor", tutor_router, {"tutor_tools": "tutor_tools", END: END})
workflow.add_conditional_edges("tutor_tools", tutor_tool_router, {"tutor": "tutor", "evaluator": "evaluator"})

workflow.add_conditional_edges("evaluator", evaluator_router, {"evaluator_tools": "evaluator_tools", END: END})
workflow.add_conditional_edges("evaluator_tools", evaluator_tool_router, {"evaluator": "evaluator"})

# --- Add Checkpointer and HITL Interruption ---
conn = sqlite3.connect("checkpoint_db.sqlite", check_same_thread=False)
memory = SqliteSaver(conn)

# We interrupt BEFORE the evaluator_tools node executes the grade change
app = workflow.compile(
    checkpointer=memory,
    interrupt_before=["evaluator_tools"]
)