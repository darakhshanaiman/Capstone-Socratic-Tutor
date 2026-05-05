import os
import re
import sqlite3
import asyncio
import time
import tempfile
from datetime import datetime
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
from langchain_pinecone import PineconeVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    UnstructuredPowerPointLoader,
    TextLoader,
)

from multi_agent_graph import app as graph_app
from schema import ChatRequest, ChatResponse, StreamChunk, HealthCheck

load_dotenv()

# Vector DB Configuration
PINECONE_INDEX_NAME = "socratic-tutor-index"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# Global clients
pinecone_client = None
embeddings_model = None

# Global checkpointer and database connection
db_connection = None
checkpointer = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.
    Initializes the database connection, checkpointer, Pinecone, and embeddings.
    Cleans up database connection on shutdown.
    """
    global db_connection, checkpointer, pinecone_client, embeddings_model

    print("🚀 Starting RAG Pipeline API...")

    db_connection = sqlite3.connect("checkpoint_db.sqlite", check_same_thread=False)
    checkpointer = SqliteSaver(db_connection)

    print("✅ Checkpointer initialized with SQLite database.")

    try:
        print("🔗 Initializing Pinecone and embeddings...")

        pinecone_api_key = os.environ.get("PINECONE_API_KEY")
        if not pinecone_api_key:
            raise ValueError("PINECONE_API_KEY is missing from environment variables.")

        pinecone_client = Pinecone(api_key=pinecone_api_key)
        embeddings_model = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

        existing_indexes = [index.name for index in pinecone_client.list_indexes()]

        if PINECONE_INDEX_NAME not in existing_indexes:
            print(f"Creating Pinecone index: {PINECONE_INDEX_NAME}")

            pinecone_client.create_index(
                name=PINECONE_INDEX_NAME,
                dimension=384,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )

            time.sleep(5)

        print("✅ Pinecone and embeddings initialized successfully.")

    except Exception as e:
        print(f"⚠️ Warning: Pinecone initialization failed: {str(e)}")
        print("The API will still run, but document ingestion will be unavailable.")

    yield

    print("🛑 Shutting down RAG Pipeline API...")

    if db_connection:
        db_connection.close()
        print("✅ Database connection closed.")


app = FastAPI(
    title="RAG Pipeline API",
    description="A Web Service for the Socratic AI Tutor with LangGraph",
    version="1.0.0",
    lifespan=lifespan,
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
    """Health check endpoint to verify the API is running."""
    return HealthCheck(
        status="healthy",
        version="1.0.0",
        message="RAG Pipeline API is running and ready to process requests.",
    )


@app.post("/ingest")
async def ingest_files(files: list[UploadFile] = File(...)):
    """
    Upload and embed course materials into Pinecone vector database.

    Accepts PDF, DOCX, TXT, and PPTX files.
    Splits documents into chunks.
    Embeds chunks using HuggingFace embeddings.
    Stores chunks in Pinecone for RAG retrieval.
    """
    if not pinecone_client or not embeddings_model:
        raise HTTPException(
            status_code=503,
            detail="Vector database not initialized. Please check Pinecone configuration.",
        )

    try:
        print(f"\n📤 Processing {len(files)} file(s) for ingestion...")

        all_docs = []
        files_processed = 0

        for file in files:
            try:
                if not file.filename:
                    print("⚠️ Skipping unnamed file.")
                    continue

                file_content = await file.read()
                file_ext = file.filename.split(".")[-1].lower()

                print(f"📄 Loading: {file.filename}")

                if file_ext not in {"pdf", "docx", "txt", "pptx"}:
                    print(f"⚠️ Unsupported file type skipped: {file.filename}")
                    continue

                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as tmp_file:
                    tmp_file.write(file_content)
                    tmp_path = tmp_file.name

                try:
                    if file_ext == "pdf":
                        loader = PyPDFLoader(tmp_path)
                    elif file_ext == "docx":
                        loader = Docx2txtLoader(tmp_path)
                    elif file_ext == "txt":
                        loader = TextLoader(tmp_path)
                    elif file_ext == "pptx":
                        loader = UnstructuredPowerPointLoader(tmp_path)

                    docs = loader.load()

                    if docs:
                        all_docs.extend(docs)
                        files_processed += 1
                        print(f"✅ Loaded {len(docs)} document part(s) from {file.filename}")
                    else:
                        print(f"⚠️ No content extracted from {file.filename}")

                finally:
                    os.unlink(tmp_path)

            except Exception as e:
                print(f"❌ Error processing {file.filename}: {str(e)}")
                continue

        if not all_docs:
            raise HTTPException(
                status_code=400,
                detail="No documents could be extracted from the uploaded files.",
            )

        print("\n✂️ Splitting documents into chunks...")

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
        )

        splits = splitter.split_documents(all_docs)

        print(f"📊 Created {len(splits)} chunks from {len(all_docs)} document part(s).")
        print("🔍 Embedding and storing in Pinecone index...")

        PineconeVectorStore.from_documents(
            documents=splits,
            embedding=embeddings_model,
            index_name=PINECONE_INDEX_NAME,
        )

        print(f"✅ Successfully indexed {len(splits)} chunks.")

        return {
            "status": "success",
            "files_processed": files_processed,
            "documents_loaded": len(all_docs),
            "chunks_created": len(splits),
            "model": EMBEDDING_MODEL,
            "vector_db": "Pinecone",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    except HTTPException:
        raise

    except Exception as e:
        print(f"❌ Error in /ingest endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing files: {str(e)}",
        )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Standard chat endpoint.

    Accepts a user message and optional thread_id.
    Returns the final answer after processing through the LangGraph.
    Uses thread_id for multi-turn conversation persistence.
    """
    try:
        config = {"configurable": {"thread_id": request.thread_id}}
        input_data = {"messages": [HumanMessage(content=request.message)]}

        output = graph_app.invoke(input_data, config=config)

        messages = output.get("messages", [])
        if not messages:
            raise HTTPException(status_code=500, detail="No response from agent.")

        final_message = messages[-1]

        final_answer = (
            final_message.content
            if hasattr(final_message, "content")
            else str(final_message)
        )

        final_answer = re.sub(
            r"<think>.*?</think>",
            "",
            final_answer,
            flags=re.DOTALL,
        ).strip()

        return ChatResponse(
            thread_id=request.thread_id,
            status="completed",
            final_answer=final_answer,
            node_executed="tutor",
            messages_count=len(messages),
        )

    except HTTPException:
        raise

    except Exception as e:
        print(f"❌ Error in /chat endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}",
        )


@app.post("/stream")
async def stream(request: ChatRequest):
    """
    Streaming endpoint using Server-Sent Events.

    This endpoint uses POST, so use fetch() on the frontend instead of EventSource.

    Example JavaScript:

    const response = await fetch('/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: 'Define the concept of Data Idempotency.',
        thread_id: 'test_session_002'
      })
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      console.log(chunk);
    }
    """

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            config = {"configurable": {"thread_id": request.thread_id}}
            input_data = {"messages": [HumanMessage(content=request.message)]}

            async for event in graph_app.astream(input_data, config=config):
                for node_name, node_state in event.items():
                    if "messages" not in node_state:
                        continue

                    msg = node_state["messages"][-1]

                    node_chunk = StreamChunk(
                        event="node_executed",
                        node_name=node_name,
                        content=None,
                        timestamp=datetime.utcnow().isoformat() + "Z",
                    )
                    yield f"data: {node_chunk.model_dump_json()}\n\n"

                    if hasattr(msg, "content") and msg.content:
                        content = re.sub(
                            r"<think>.*?</think>",
                            "",
                            msg.content,
                            flags=re.DOTALL,
                        ).strip()

                        if content:
                            message_chunk = StreamChunk(
                                event="message",
                                node_name=node_name,
                                content=content,
                                timestamp=datetime.utcnow().isoformat() + "Z",
                            )
                            yield f"data: {message_chunk.model_dump_json()}\n\n"

                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        for tool_call in msg.tool_calls:
                            tool_chunk = StreamChunk(
                                event="tool_call",
                                node_name=node_name,
                                content=f"Tool: {tool_call.get('name', 'unknown')}",
                                timestamp=datetime.utcnow().isoformat() + "Z",
                            )
                            yield f"data: {tool_chunk.model_dump_json()}\n\n"

                await asyncio.sleep(0.01)

            complete_chunk = StreamChunk(
                event="complete",
                node_name=None,
                content="Stream completed",
                timestamp=datetime.utcnow().isoformat() + "Z",
            )
            yield f"data: {complete_chunk.model_dump_json()}\n\n"

        except Exception as e:
            print(f"❌ Error in /stream endpoint: {str(e)}")

            error_chunk = StreamChunk(
                event="error",
                node_name=None,
                content=f"Error: {str(e)}",
                timestamp=datetime.utcnow().isoformat() + "Z",
            )
            yield f"data: {error_chunk.model_dump_json()}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/threads/{thread_id}")
async def get_thread_state(thread_id: str):
    """
    Retrieve the current state of a conversation thread.

    Useful for debugging and monitoring.
    Returns the graph state for the given thread_id.
    """
    try:
        if not checkpointer:
            raise HTTPException(
                status_code=500,
                detail="Checkpointer not initialized.",
            )

        config = {"configurable": {"thread_id": thread_id}}
        state = graph_app.get_state(config)

        return {
            "thread_id": thread_id,
            "messages_count": len(state.values.get("messages", [])),
            "next_nodes": state.next,
            "state": state.values,
        }

    except HTTPException:
        raise

    except Exception as e:
        print(f"❌ Error retrieving thread state: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving thread: {str(e)}",
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )