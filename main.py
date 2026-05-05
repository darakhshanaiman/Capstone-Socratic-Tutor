import re
import sqlite3
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver

from multi_agent_graph import app as graph_app
from schema import ChatRequest, ChatResponse, StreamChunk, HealthCheck


# Global checkpointer and database connection
db_connection = None
checkpointer = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.
    Initializes the database connection and checkpointer at startup,
    and cleans up at shutdown.
    """
    global db_connection, checkpointer
    
    print("🚀 Starting RAG Pipeline API...")
    db_connection = sqlite3.connect("checkpoint_db.sqlite", check_same_thread=False)
    checkpointer = SqliteSaver(db_connection)
    print("✅ Checkpointer initialized with SQLite database.")
    
    yield
    
    print("🛑 Shutting down RAG Pipeline API...")
    if db_connection:
        db_connection.close()
        print("✅ Database connection closed.")


app = FastAPI(
    title="RAG Pipeline API",
    description="A Web Service for the Socratic AI Tutor with LangGraph",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthCheck)
async def health_check():
    return HealthCheck(
        status="healthy",
        version="1.0.0",
        message="RAG Pipeline API is running and ready to process requests."
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        config = {"configurable": {"thread_id": request.thread_id}}
        input_data = {"messages": [HumanMessage(content=request.message)]}
        output = graph_app.invoke(input_data, config=config)

        messages = output.get("messages", [])
        if not messages:
            raise HTTPException(status_code=500, detail="No response from agent")

        final_message = messages[-1]
        final_answer = (
            final_message.content
            if hasattr(final_message, "content")
            else str(final_message)
        )
        final_answer = re.sub(r'<think>.*?</think>', '', final_answer, flags=re.DOTALL).strip()

        return ChatResponse(
            thread_id=request.thread_id,
            status="completed",
            final_answer=final_answer,
            node_executed="tutor",
            messages_count=len(messages)
        )
    except Exception as e:
        print(f"❌ Error in /chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")


@app.post("/stream")
async def stream(request: ChatRequest):
    async def event_generator() -> AsyncGenerator:
        try:
            config = {"configurable": {"thread_id": request.thread_id}}
            input_data = {"messages": [HumanMessage(content=request.message)]}

            async for event in graph_app.astream(input_data, config=config):
                for node_name, node_state in event.items():
                    if "messages" not in node_state:
                        continue

                    msg = node_state["messages"][-1]
                    
                    chunk = StreamChunk(
                        event="node_executed",
                        node_name=node_name,
                        content=None,
                        timestamp=datetime.utcnow().isoformat() + "Z"
                    )
                    yield f"data: {chunk.model_dump_json()}\n\n"

                    if hasattr(msg, "content") and msg.content:
                        content = re.sub(r'<think>.*?</think>', '', msg.content, flags=re.DOTALL).strip()
                        if content:
                            chunk = StreamChunk(
                                event="message",
                                node_name=node_name,
                                content=content,
                                timestamp=datetime.utcnow().isoformat() + "Z"
                            )
                            yield f"data: {chunk.model_dump_json()}\n\n"

                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        for tool_call in msg.tool_calls:
                            chunk = StreamChunk(
                                event="tool_call",
                                node_name=node_name,
                                content=f"Tool: {tool_call.get('name', 'unknown')}",
                                timestamp=datetime.utcnow().isoformat() + "Z"
                            )
                            yield f"data: {chunk.model_dump_json()}\n\n"

                await asyncio.sleep(0.01)

            chunk = StreamChunk(
                event="complete",
                node_name=None,
                content="Stream completed",
                timestamp=datetime.utcnow().isoformat() + "Z"
            )
            yield f"data: {chunk.model_dump_json()}\n\n"
        except Exception as e:
            print(f"❌ Error in /stream endpoint: {str(e)}")
            error_chunk = StreamChunk(
                event="error",
                node_name=None,
                content=f"Error: {str(e)}",
                timestamp=datetime.utcnow().isoformat() + "Z"
            )
            yield f"data: {error_chunk.model_dump_json()}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/threads/{thread_id}")
async def get_thread_state(thread_id: str):
    try:
        if not checkpointer:
            raise HTTPException(status_code=500, detail="Checkpointer not initialized")

        config = {"configurable": {"thread_id": thread_id}}
        state = graph_app.get_state(config)

        return {
            "thread_id": thread_id,
            "messages_count": len(state.values.get("messages", [])),
            "next_nodes": state.next,
            "state": state.values
        }
    except Exception as e:
        print(f"❌ Error retrieving thread state: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving thread: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
