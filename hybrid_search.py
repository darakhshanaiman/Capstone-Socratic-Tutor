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
        keyword_docs = []
        if self.keyword:
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

# Global cache for retrievers
_retriever_cache = {}

def setup_hybrid_retriever(subject=""):
    global _retriever_cache
    
    if subject in _retriever_cache:
        print(f"--- Using Cached Hybrid Search Engine (Subject: {subject}) ---")
        return _retriever_cache[subject]

    print(f"--- Preparing Hybrid Search Engine (Subject: {subject}) ---")
    # --- Fuzzy Subject Matching ---
    available_subjects = [f.name for f in os.scandir(FOLDER_PATH) if f.is_dir()]
    if subject not in available_subjects and available_subjects:
        # Try to find the closest match
        import difflib
        matches = difflib.get_close_matches(subject, available_subjects, n=1, cutoff=0.3)
        if matches:
            print(f"⚠️ [Fuzzy Match] Subject '{subject}' not found. Using closest match: '{matches[0]}'")
            subject = matches[0]

    target_folder = os.path.join(FOLDER_PATH, subject)
    
    # Load local documents for BM25
    docs = []
    if os.path.exists(target_folder):
        try:
            docs.extend(DirectoryLoader(target_folder, glob="**/*.pdf", loader_cls=PyPDFLoader).load())
            docs.extend(DirectoryLoader(target_folder, glob="**/*.docx", loader_cls=Docx2txtLoader).load())
            docs.extend(DirectoryLoader(target_folder, glob="**/*.pptx", loader_cls=UnstructuredPowerPointLoader).load())
        except Exception as e:
            print(f"⚠️ [Load Warning] Error reading some files: {e}")

    # Fallback Logic: If no local docs, we can't do BM25, but we can still do Pinecone!
    bm25_retriever = None
    if docs:
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        splits = splitter.split_documents(docs)
        bm25_retriever = BM25Retriever.from_documents(splits)
        bm25_retriever.k = 3
    else:
        print(f"⚠️ [Retriever Warning] No local files found for '{subject}'. Falling back to pure Vector Search.")

    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vectorstore = PineconeVectorStore(index_name=INDEX_NAME, embedding=embeddings)
    
    search_kwargs = {"k": 3}
    if subject:
        search_kwargs["namespace"] = subject
        
    pinecone_retriever = vectorstore.as_retriever(search_kwargs=search_kwargs)

    retriever = ManualHybridRetriever(bm25_retriever, pinecone_retriever)
    _retriever_cache[subject] = retriever
    return retriever