import os
import time
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
from langchain_pinecone import PineconeVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    DirectoryLoader, 
    PyPDFLoader, 
    Docx2txtLoader, 
    UnstructuredPowerPointLoader
)

load_dotenv()

INDEX_NAME = "socratic-tutor-index"
FOLDER_PATH = "the course content"

def ingest():
    print("--- Connecting to Pinecone ---")
    pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
    
    # 1. Wipe the old index to prevent duplicates
    if INDEX_NAME in [i.name for i in pc.list_indexes()]:
        print("Deleting old index to prevent duplicates...")
        pc.delete_index(INDEX_NAME)
        time.sleep(5) # Give Pinecone a moment to delete
        
    print(f"Creating fresh index: {INDEX_NAME}")
    pc.create_index(
        name=INDEX_NAME,
        dimension=384, 
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )
    time.sleep(5) # Give Pinecone a moment to initialize

    # 2. Load Documents
    print(f"--- Scanning '{FOLDER_PATH}' for files ---")
    docs = []

    try:
        docs.extend(DirectoryLoader(FOLDER_PATH, glob="**/*.pdf", loader_cls=PyPDFLoader).load())
    except Exception:
        pass
    try:
        docs.extend(DirectoryLoader(FOLDER_PATH, glob="**/*.docx", loader_cls=Docx2txtLoader).load())
    except Exception:
        pass
    try:
        docs.extend(DirectoryLoader(FOLDER_PATH, glob="**/*.pptx", loader_cls=UnstructuredPowerPointLoader).load())
    except Exception:
        pass

    if not docs:
        print("❌ No readable documents found in the folder!")
        return

    print(f"✅ Total Extracted: {len(docs)} pages/slides.")

    # 3. Split Text
    print("--- Splitting Text into Chunks ---")
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = splitter.split_documents(docs)

    # 4. Upload to Pinecone (No SQLRecordManager needed)
    print("--- Uploading to Pinecone Vector DB ---")
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    PineconeVectorStore.from_documents(splits, embeddings, index_name=INDEX_NAME)
    
    print("✅ Ingestion Complete! Data is ready for RAG.")

if __name__ == "__main__":
    ingest()