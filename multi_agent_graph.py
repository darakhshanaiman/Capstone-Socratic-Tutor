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


from tools import retrieve_concept_definition, check_mastery_level, update_mastery_state
from agents_config import TUTOR_PROMPT, EVALUATOR_PROMPT

load_dotenv()

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.0, api_key=os.environ.get("GROQ_API_KEY"))

@tool
def transfer_to_evaluator():
    """Use this tool ONLY when the user has provided an answer to your scaffolding question and needs to be graded."""
    return "Successfully handed over to the Mastery Evaluator."

# --- Split Tools into Safe vs High-Risk ---
tutor_tools = [retrieve_concept_definition, check_mastery_level, transfer_to_evaluator]
tutor_llm = llm.bind_tools(tutor_tools)

# The grading tool is our high-risk tool that requires human approval
evaluator_tools = [update_mastery_state]
evaluator_llm = llm.bind_tools(evaluator_tools)

def tutor_node(state):
    try:
        # Standard invocation
        response = tutor_llm.invoke([TUTOR_PROMPT] + state["messages"])
        return {"messages": [response]}
        
    except Exception as e:
        # Catch the 400 Bad Request error specifically
        if "tool_use_failed" in str(e) or "update_mastery_state" in str(e):
            print("🛑 [Security Guardrail] Intercepted unauthorized tool call attempt.")
            
            # We return a manual AIMessage so the system doesn't crash.
            # This 'fakes' a refusal from the AI.
            refusal_msg = AIMessage(
                content="I'm sorry, I'm feeling a bit overwhelmed! As a Socratic Tutor, I don't have the authority to change grades. Let's get back to our lesson."
            )
            return {"messages": [refusal_msg]}
        
        # If it's a different error, raise it
        raise e

def evaluator_node(state: AgentState):
    response = evaluator_llm.invoke([EVALUATOR_PROMPT] + state["messages"])
    return {"messages": [response]}

# Create TWO separate tool nodes
tutor_tools_node = ToolNode(tutor_tools)
evaluator_tools_node = ToolNode(evaluator_tools) # This is the high-risk node

# --- Routing Logic ---
def tutor_router(state: AgentState) -> str:
    last_message = state["messages"][-1]
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
    if last_message.name == "transfer_to_evaluator":
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