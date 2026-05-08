from typing import Union

from langchain_core.tools import tool
from pydantic import BaseModel, Field, field_validator
from hybrid_search import setup_hybrid_retriever


# --- 1. The Retrieval Tool ---
@tool
def retrieve_concept_definition(query: str):
    """Use this tool to search the curriculum for definitions and concepts."""
    retriever = setup_hybrid_retriever()
    results = retriever.invoke(query)
    return "\n\n".join([doc.page_content for doc in results])


# --- 2. The Gradebook Database ---
student_mastery_db = {}


# --- 3. The Grading Tool ---
class UpdateMasterySchema(BaseModel):
    user_id: str = Field(description="The unique ID of the student.")
    topic: str = Field(description="The specific course topic or subject being graded.")
    change: Union[int, str] = Field(
        description="The amount to change the mastery score. Use 1 for correct and 0 for incorrect."
    )
    reason: str = Field(description="A brief explanation of why the score is changing.")

    @field_validator("change")
    @classmethod
    def validate_change(cls, value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0


@tool(args_schema=UpdateMasterySchema)
def update_mastery_state(user_id: str, topic: str, change: Union[int, str], reason: str):
    """Always use this tool to update a student's score after they answer a scaffolding question."""

    try:
        change = int(change)
    except (TypeError, ValueError):
        change = 0

    if user_id not in student_mastery_db:
        student_mastery_db[user_id] = {}

    if topic not in student_mastery_db[user_id]:
        student_mastery_db[user_id][topic] = 0

    student_mastery_db[user_id][topic] += change

    current_score = student_mastery_db[user_id][topic]
    print(f"\n📝 [Gradebook Updated] {user_id} -> {topic}: {current_score} points. ({reason})")

    return f"Success! {topic} mastery is now {current_score}."


# --- 4. Check Mastery Tool ---
class CheckMasterySchema(BaseModel):
    user_id: str = Field(description="The unique ID of the student.")


@tool(args_schema=CheckMasterySchema)
def check_mastery_level(user_id: str):
    """Use this tool whenever the user asks to see their score, grades, or mastery level."""

    if user_id not in student_mastery_db or not student_mastery_db[user_id]:
        return "The student has no mastery scores yet."

    grades = "\n".join(
        [f"- {topic}: {score} points" for topic, score in student_mastery_db[user_id].items()]
    )

    return f"Here are the current mastery scores for {user_id}:\n{grades}"


# --- 5. Export All Tools ---
project_tools = [
    retrieve_concept_definition,
    update_mastery_state,
    check_mastery_level,
]