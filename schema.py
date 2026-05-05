from pydantic import BaseModel, Field
from typing import Optional, Literal
from uuid import uuid4


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    message: str = Field(..., description="The user's message/query")
    thread_id: Optional[str] = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique thread ID for conversation persistence. Auto-generated if not provided.",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "What are the four stages of Data Engineering?",
                "thread_id": "076-student-001",
            }
        }


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""

    thread_id: str = Field(..., description="The thread ID used for this request")
    status: Literal["processing", "completed", "error"] = Field(
        ..., description="Current response status"
    )
    final_answer: str = Field(..., description="The agent's final response")
    node_executed: Optional[str] = Field(
        None, description="Last node executed in the graph"
    )
    messages_count: int = Field(
        ..., description="Total number of messages in the conversation"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "thread_id": "076-student-001",
                "status": "completed",
                "final_answer": "The four stages are Generation, Ingestion, Transformation, and Serving.",
                "node_executed": "tutor",
                "messages_count": 2,
            }
        }


class HealthCheck(BaseModel):
    """Response model for health check endpoint."""

    status: Literal["healthy", "unhealthy"] = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    message: str = Field(..., description="Status message")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "message": "RAG Pipeline API is running and ready to process requests.",
            }
        }


class StreamChunk(BaseModel):
    """Model for streaming response chunks."""

    event: Literal[
        "node_executed",
        "message",
        "tool_call",
        "complete",
        "error",
    ] = Field(..., description="Streaming event type")
    node_name: Optional[str] = Field(
        None, description="Name of the node being executed"
    )
    content: Optional[str] = Field(
        None, description="Content chunk, tool call info, final answer, or error message"
    )
    timestamp: Optional[str] = Field(None, description="ISO format timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "event": "message",
                "node_name": "tutor",
                "content": "Data idempotency means...",
                "timestamp": "2024-04-19T10:30:00Z",
            }
        }