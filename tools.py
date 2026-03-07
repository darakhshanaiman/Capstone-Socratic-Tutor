from langchain_core.tools import tool
from pydantic import BaseModel, Field
from hybrid_search import setup_hybrid_retriever

# Connect to the Perception Layer built in Lab 2
retriever = setup_hybrid_retriever()

# --- 1. The Grounding Tool ---
class ConceptDefinitionSchema(BaseModel):
    query: str = Field(description="The specific course topic or concept to look up in the vector database.")

@tool("retrieve_concept_definition", args_schema=ConceptDefinitionSchema)
def retrieve_concept_definition(query: str) -> str:
    """
    Queries the Vector DB to find the official definition and context of a course concept.
    Always use this tool before asking a scaffolding question or evaluating a student's answer
    to ensure your response is grounded in the actual curriculum.
    """
    print(f"\n   [Tool Executing] Retrieving course material for: '{query}'")
    docs = retriever.invoke(query)
    if not docs:
        return "No relevant course material found for this concept."
    return "\n\n".join([doc.page_content for doc in docs])


# --- 2. The Action Tool ---
class UpdateMasterySchema(BaseModel):
    user_id: str = Field(description="The unique identifier for the student.")
    change: int = Field(description="The amount to increment or decrement the mastery level (e.g., +1 or -1).")
    reason: str = Field(description="A brief explanation of why the mastery level is changing.")

@tool("update_mastery_state", args_schema=UpdateMasterySchema)
def update_mastery_state(user_id: str, change: int, reason: str) -> str:
    """
    Python functions that perform calculations, API calls, or database lookups specific to your use case.
    Updates the student's mastery level in the database after evaluating their response.
    """
    print(f"\n   [Tool Executing] Updating Mastery for '{user_id}' | Change: {change} | Reason: {reason}")
    
    # In a production environment, this would write to a JSON file or Redis DB.
    # For now, we simulate the database action successfully executing.
    return f"SUCCESS: Mastery for {user_id} updated by {change}."

# Export the tools list for the graph to use
project_tools = [retrieve_concept_definition, update_mastery_state]