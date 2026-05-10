import os
from typing import Annotated, TypedDict
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from tools import project_tools

load_dotenv()

# --- 1. Define the Graph State ---
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

# --- 2. Setup the Smarter LLM and Bind Tools ---
llm = ChatGroq(
    model="llama-3.3-70b-versatile", # The upgraded 70B model
    temperature=0.0,
    api_key=os.environ.get("GROQ_API_KEY")
)
llm_with_tools = llm.bind_tools(project_tools)

# --- 3. Define the Nodes ---
def agent_node(state: AgentState):
    """
    Takes the current State, calls the LLM, and returns the next step.
    """
    print("\n[Agent Thinking...]")
    
# The Chain of Thought Socratic Prompt
    system_prompt = SystemMessage(content="""
    You are a strict, logical Socratic Tutor. You must THINK before you act. 
    
    CRITICAL INSTRUCTION: You MUST enclose your internal logical thought process inside <think> and </think> tags. 
    Write your actual response to the student AFTER the closing </think> tag.

    TUTORING PROCESS RULES:
    1. GREETING: If the user just says "hi" or greets you, do NOT use any tools. Simply say hello back and ask what course topic they want to study.
    2. NEW TOPIC: If the user provides a topic, ALWAYS use the 'retrieve_concept_definition' tool first to find the ground truth.
    3. MISSING INFO FALLBACK: If the tool returns no relevant information, DO NOT ask a question. Inform the user that the topic is not covered in the curriculum.
    4. QUESTIONING: If the context DOES contain the topic, ask ONE scaffolding question based ONLY on the retrieved text.
    5. EVALUATING: If the user attempts an answer, evaluate it against the context. If right, congratulate them and use 'update_mastery_state'. If wrong, give a hint and ask again.
    6. NO HALLUCINATION: Never make up facts. Stick strictly to the retrieved context.
    """)
    
    messages_to_send = [system_prompt] + state["messages"]
    response = llm_with_tools.invoke(messages_to_send)
    return {"messages": [response]}

# The missing tool node! This executes our Python functions.
tool_node = ToolNode(project_tools) 

# --- 4. The Conditional Router ---
def router(state: AgentState) -> str:
    """
    Checks the LLM's last message to decide whether to use a tool or end.
    """
    last_message = state["messages"][-1]
    
    if last_message.tool_calls:
        return "tools"
    
    return END

# --- 5. Build and Compile the Graph ---
workflow = StateGraph(AgentState)

workflow.add_node("agent", agent_node)
workflow.add_node("tools", tool_node)

workflow.set_entry_point("agent")
workflow.add_conditional_edges("agent", router, {"tools": "tools", END: END})
workflow.add_edge("tools", "agent")

app = workflow.compile()