"""
Professional Streamlit Interface for RAG Pipeline
Upload course materials → Instant embedding → Chat with tutor
"""

import streamlit as st
import requests
import json
import uuid
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# ============= PAGE CONFIG =============
st.set_page_config(
    page_title="📚 Socratic AI Tutor",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5em;
        color: #1f77b4;
        margin-bottom: 0.5em;
    }
    .info-box {
        background-color: #f0f2f6;
        border-left: 4px solid #1f77b4;
        padding: 1em;
        border-radius: 4px;
        margin-bottom: 1em;
    }
    .success-box {
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        padding: 1em;
        border-radius: 4px;
        margin-bottom: 1em;
    }
    .warning-box {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 1em;
        border-radius: 4px;
        margin-bottom: 1em;
    }
    .chat-message {
        padding: 1rem;
        margin-bottom: 1rem;
        border-radius: 8px;
        display: flex;
        gap: 1rem;
    }
    .user-message {
        background-color: #e3f2fd;
        justify-content: flex-end;
    }
    .assistant-message {
        background-color: #f5f5f5;
    }
</style>
""", unsafe_allow_html=True)

# ============= CONFIGURATION =============
API_BASE_URL = os.getenv("API_URL", "http://localhost:8000")
SUPPORTED_FORMATS = ["pdf", "txt", "docx", "pptx"]

# Initialize session state
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = []

# ============= HELPER FUNCTIONS =============
def check_api_health():
    """Verify API is running."""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        return response.status_code == 200
    except Exception as e:
        st.error(f"❌ API unavailable: {str(e)}")
        return False

def upload_and_embed_files(uploaded_files):
    """Upload files to the API for embedding."""
    try:
        files_to_upload = [
            ("files", (file.name, file, file.type))
            for file in uploaded_files
        ]
        
        response = requests.post(
            f"{API_BASE_URL}/ingest",
            files=files_to_upload,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            return True, result
        else:
            return False, response.json().get("detail", "Unknown error")
    except Exception as e:
        return False, str(e)

def send_chat_message(user_message):
    """Send message to the RAG agent."""
    try:
        payload = {
            "message": user_message,
            "thread_id": st.session_state.thread_id
        }
        
        response = requests.post(
            f"{API_BASE_URL}/chat",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": response.json().get("detail", "Unknown error")}
    except Exception as e:
        return {"error": str(e)}

# ============= MAIN UI =============
st.markdown("<h1 class='main-header'>📚 Socratic AI Tutor</h1>", unsafe_allow_html=True)
st.markdown("**Intelligent learning assistant powered by RAG + LangGraph**")

# Check API health
if not check_api_health():
    st.warning(
        "⚠️ **API Server Not Running**\n\n"
        "Please start the FastAPI server with:\n"
        "```\nuvicorn api:app --reload\n```"
    )
    st.stop()

# Create three columns layout
col1, col2 = st.columns([1, 2])

# ============= LEFT SIDEBAR: FILE UPLOAD =============
with col1:
    st.subheader("📂 Course Material Library", divider="blue")
    
    uploaded_files = st.file_uploader(
        "Upload course materials",
        type=SUPPORTED_FORMATS,
        accept_multiple_files=True,
        help="Supported: PDF, TXT, DOCX, PPTX"
    )
    
    if uploaded_files:
        st.markdown(f"**📄 {len(uploaded_files)} file(s) selected:**")
        for file in uploaded_files:
            st.caption(f"• {file.name} ({file.size / 1024:.1f} KB)")
        
        if st.button("🚀 Embed & Index", use_container_width=True, type="primary"):
            with st.spinner("📤 Uploading and embedding... This may take a moment..."):
                success, result = upload_and_embed_files(uploaded_files)
                
                if success:
                    st.success(f"✅ Successfully embedded {result.get('files_processed', 0)} file(s)!")
                    st.markdown(f"- **Chunks created:** {result.get('chunks_created', 0)}")
                    st.markdown(f"- **Embedding model:** {result.get('model', 'Unknown')}")
                    st.session_state.uploaded_files.extend([f.name for f in uploaded_files])
                else:
                    st.error(f"❌ Upload failed: {result}")
    
    # Display upload history
    if st.session_state.uploaded_files:
        st.markdown("---")
        st.markdown("**📚 Indexed Materials:**")
        for fname in st.session_state.uploaded_files:
            st.caption(f"✓ {fname}")
    
    # Session info
    st.markdown("---")
    st.markdown("**Session Info:**")
    st.caption(f"Thread ID: `{st.session_state.thread_id}`")
    if st.button("🔄 New Session", use_container_width=True):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.chat_history = []
        st.rerun()

# ============= RIGHT: CHAT INTERFACE =============
with col2:
    st.subheader("💬 Ask Your Tutor", divider="green")
    
    # Chat history display
    chat_container = st.container(height=400, border=True)
    
    with chat_container:
        if not st.session_state.chat_history:
            st.info(
                "👋 **Welcome!**\n\n"
                "1. Upload your course materials on the left\n"
                "2. Ask questions about the content\n"
                "3. Get instant, accurate answers"
            )
        else:
            for msg in st.session_state.chat_history:
                if msg["role"] == "user":
                    st.markdown(f"**You:** {msg['content']}")
                else:
                    st.markdown(f"**Tutor:** {msg['content']}")
                st.divider()
    
    # Chat input
    st.markdown("---")
    user_input = st.text_area(
        "Your question:",
        placeholder="e.g., What are the four stages of Data Engineering?",
        label_visibility="collapsed",
        height=80
    )
    
    col_send, col_clear = st.columns([4, 1])
    
    with col_send:
        send_button = st.button("📤 Send", use_container_width=True, type="primary")
    
    with col_clear:
        if st.button("🗑️", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()
    
    # Process message
    if send_button and user_input.strip():
        if not st.session_state.uploaded_files:
            st.warning("⚠️ Please upload course materials first!")
        else:
            # Add user message to history
            st.session_state.chat_history.append({
                "role": "user",
                "content": user_input
            })
            
            with st.spinner("🤔 Thinking..."):
                response = send_chat_message(user_input)
                
                if "error" not in response:
                    assistant_message = response.get("final_answer", "No response received.")
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": assistant_message
                    })
                    st.rerun()
                else:
                    st.error(f"❌ Error: {response['error']}")

# ============= FOOTER =============
st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: #666; font-size: 0.85em;">
    📚 **Socratic AI Tutor** | Built with Streamlit + LangGraph + Pinecone Vector DB<br>
    <a href="https://github.com" style="color: #1f77b4; text-decoration: none;">GitHub</a> • 
    <a href="https://docs.langchain.com/docs/" style="color: #1f77b4; text-decoration: none;">LangChain Docs</a>
    </div>
    """,
    unsafe_allow_html=True
)
