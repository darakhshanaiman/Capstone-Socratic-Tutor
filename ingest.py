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
BASE_FOLDER = "the course content"

def ingest():
    print("--- Connecting to Pinecone ---")
    pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
    
    # 1. Ensure the index exists, but DO NOT delete it
    if INDEX_NAME not in [i.name for i in pc.list_indexes()]:
        print(f"Creating fresh index: {INDEX_NAME}")
        pc.create_index(
            name=INDEX_NAME,
            dimension=384, 
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1")
        )
        time.sleep(5) # Give Pinecone a moment to initialize
    else:
        print(f"✅ Index '{INDEX_NAME}' already exists. Using it.")

    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    # 2. Iterate over Subject Folders
    if not os.path.exists(BASE_FOLDER):
        os.makedirs(BASE_FOLDER)
        
    subjects = [f.name for f in os.scandir(BASE_FOLDER) if f.is_dir()]
    if not subjects:
        print(f"❌ No subject folders found in '{BASE_FOLDER}'. Please create folders for each subject and add files inside them.")
        return

    for subject in subjects:
        subject_folder = os.path.join(BASE_FOLDER, subject)
        print(f"\n--- Scanning subject '{subject}' in '{subject_folder}' ---")
        docs = []

        try:
            docs.extend(DirectoryLoader(subject_folder, glob="**/*.pdf", loader_cls=PyPDFLoader).load())
        except Exception:
            pass
        try:
            docs.extend(DirectoryLoader(subject_folder, glob="**/*.docx", loader_cls=Docx2txtLoader).load())
        except Exception:
            pass
        try:
            docs.extend(DirectoryLoader(subject_folder, glob="**/*.pptx", loader_cls=UnstructuredPowerPointLoader).load())
        except Exception:
            pass

        if not docs:
            print(f"⚠️ No readable documents found for subject '{subject}'!")
            continue

        print(f"✅ Total Extracted for {subject}: {len(docs)} pages/slides.")

        # 3. Split Text
        print("--- Splitting Text into Chunks ---")
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        splits = splitter.split_documents(docs)

        # 4. Upload to Pinecone under a Namespace
        print(f"--- Refreshing Pinecone namespace: {subject} ---")
        index = pc.Index(INDEX_NAME)
        index.delete(delete_all=True, namespace=subject) # Clear only this subject
        
        print(f"--- Uploading to Pinecone Vector DB (namespace: {subject}) ---")
        PineconeVectorStore.from_documents(splits, embeddings, index_name=INDEX_NAME, namespace=subject)
        
        print(f"✅ Ingestion Complete for subject: {subject}!")

if __name__ == "__main__":
    ingest()