import os
from dotenv import load_dotenv
from langchain_community.retrievers import BM25Retriever
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

class ManualHybridRetriever:
    def __init__(self, keyword_retriever, vector_retriever):
        self.keyword = keyword_retriever
        self.vector = vector_retriever

    def invoke(self, query):
        print(f"   > Searching Keywords for: {query}")
        keyword_docs = self.keyword.invoke(query)
        
        print(f"   > Searching Vector DB for: {query}")
        vector_docs = self.vector.invoke(query)
        
        seen_content = set()
        final_docs = []
        
        for doc in vector_docs + keyword_docs:
            content_sig = doc.page_content.strip()[:100] 
            if content_sig not in seen_content:
                final_docs.append(doc)
                seen_content.add(content_sig)
        
        return final_docs[:4] 

def setup_hybrid_retriever():
    print("--- Preparing Hybrid Search Engine ---")
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

    # Fallback if folder is totally empty
    if not docs:
        raise ValueError("The course folder is empty or files couldn't be read. Please add files.")

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = splitter.split_documents(docs)
    
    bm25_retriever = BM25Retriever.from_documents(splits)
    bm25_retriever.k = 3

    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vectorstore = PineconeVectorStore(index_name=INDEX_NAME, embedding=embeddings)
    pinecone_retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

    return ManualHybridRetriever(bm25_retriever, pinecone_retriever)