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
import time
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
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        return response.status_code == 200
    except Exception as e:
        st.error(f"❌ API unavailable: {str(e)}")
        return False

def upload_and_embed_files(uploaded_files, subject):
    """Upload files to the API for embedding."""
    try:
        files_to_upload = [
            ("files", (file.name, file, file.type))
            for file in uploaded_files
        ]
        
        response = requests.post(
            f"{API_BASE_URL}/ingest",
            files=files_to_upload,
            data={"subject": subject},
            timeout=300
        )
        
        if response.status_code == 200:
            result = response.json()
            return True, result
        else:
            return False, response.json().get("detail", "Unknown error")
    except Exception as e:
        return False, str(e)

def save_feedback(user_input, agent_response, feedback_value):
    """Save feedback to a JSON file."""
    log_file = "feedback_log.json"
    entry = {
        "user_input": user_input,
        "agent_response": agent_response,
        "feedback": feedback_value,
        "timestamp": datetime.now().isoformat()
    }
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
    else:
        data = []
    data.append(entry)
    with open(log_file, "w") as f:
        json.dump(data, f, indent=4)

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
            timeout=120
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": response.json().get("detail", "Unknown error")}
    except Exception as e:
        return {"error": str(e)}

def check_pending_grade(thread_id):
    """Check if there's a grade awaiting HITL approval."""
    try:
        response = requests.get(f"{API_BASE_URL}/check_pending/{thread_id}", timeout=10)
        if response.status_code == 200:
            return response.json()
        return {"pending": False}
    except Exception:
        return {"pending": False}

def approve_grade(thread_id, approved: bool):
    """Approve or reject a pending grade update."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/approve_grade",
            data={"thread_id": thread_id, "approved": "yes" if approved else "no"},
            timeout=30
        )
        if response.status_code == 200:
            return response.json()
        return {"status": "error", "message": "Failed to process approval."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_thread_history(thread_id):
    """Retrieve chat history for an existing thread."""
    try:
        response = requests.get(f"{API_BASE_URL}/threads/{thread_id}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            messages = data.get("state", {}).get("messages", [])
            history = []
            for msg in messages:
                # msg can be a dict (from API)
                m_type = msg.get("type")
                role = "user" if m_type == "human" else "assistant"
                content = msg.get("content", "")
                if content:
                    history.append({"role": role, "content": content})
            return history
        return None
    except Exception:
        return None

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
    
    # Subject Selection
    base_folder = "the course content"
    if not os.path.exists(base_folder):
        os.makedirs(base_folder)
    subjects = [f.name for f in os.scandir(base_folder) if f.is_dir()]
    
    if not subjects:
        st.warning("No subjects found. Create a new one below.")
        selected_subject = ""
    else:
        selected_subject = st.selectbox("Select Existing Subject", subjects)
        
    new_subject = st.text_input("Or Create New Subject:", placeholder="e.g., Biology_101")
    
    active_subject = new_subject.strip() if new_subject.strip() else selected_subject

    if active_subject:
        # Show existing files for this subject
        subject_path = os.path.join(base_folder, active_subject)
        if os.path.exists(subject_path):
            existing_files = os.listdir(subject_path)
            if existing_files:
                st.markdown(f"**📚 Existing Knowledge for '{active_subject}':**")
                for f in existing_files:
                    st.caption(f"✓ {f}")
                st.info("The content above is already indexed. You can start chatting immediately!")
            else:
                st.warning(f"Subject '{active_subject}' exists but has no files yet.")

        st.markdown("---")
        uploaded_files = st.file_uploader(
            f"Add more materials to '{active_subject}'",
            type=SUPPORTED_FORMATS,
            accept_multiple_files=True,
            help="Supported: PDF, TXT, DOCX, PPTX"
        )
        
        if uploaded_files:
            st.markdown(f"**📄 {len(uploaded_files)} file(s) selected:**")
            for file in uploaded_files:
                st.caption(f"• {file.name} ({file.size / 1024:.1f} KB)")
            
            if st.button("🚀 Upload & Index", use_container_width=True, type="primary"):
                with st.spinner("📤 Uploading and embedding... This may take a moment..."):
                    success, result = upload_and_embed_files(uploaded_files, active_subject)
                    
                    if success:
                        st.success(f"✅ Successfully embedded {result.get('files_processed', 0)} file(s)!")
                        st.markdown(f"- **Chunks created:** {result.get('chunks_created', 0)}")
                        st.session_state.uploaded_files.extend([f.name for f in uploaded_files])
                        time.sleep(2) # Give it time to render before rerun
                        st.rerun() # Refresh to update the subject list
                    else:
                        st.error(f"❌ Upload failed: {result}")
    else:
        st.info("💡 **Tip:** Subjects are saved automatically. Select an existing subject or create a new one to begin.")
    
    # Display upload history
    if st.session_state.uploaded_files:
        st.markdown("---")
        st.markdown("**📚 Indexed Materials:**")
        for fname in st.session_state.uploaded_files:
            st.caption(f"✓ {fname}")
    
    # Session info
    st.markdown("---")
    st.markdown("**Session Management:**")
    st.caption(f"Current Thread ID: `{st.session_state.thread_id}`")
    
    if st.button("🔄 New Session", use_container_width=True):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.chat_history = []
        st.rerun()

    st.markdown("---")
    resume_id = st.text_input("Resume Existing Session:", placeholder="Paste Thread ID here")
    if st.button("🔌 Resume", use_container_width=True):
        if resume_id.strip():
            with st.spinner("⏳ Loading history..."):
                history = get_thread_history(resume_id.strip())
                if history is not None:
                    st.session_state.thread_id = resume_id.strip()
                    st.session_state.chat_history = history
                    st.success("✅ Session resumed!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Thread ID not found or error loading history.")
        else:
            st.warning("Please enter a Thread ID.")

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
            # Container for messages to help with layout
            chat_container = st.container()
            with chat_container:
                for i, msg in enumerate(st.session_state.chat_history):
                    if msg["role"] == "user":
                        with st.chat_message("user"):
                            st.write(msg["content"])
                    else:
                        with st.chat_message("assistant", avatar="🤖"):
                            st.write(msg["content"])
                            if "feedback" not in msg:
                                f_col1, f_col2, _ = st.columns([1, 1, 8])
                                with f_col1:
                                    if st.button("👍", key=f"good_{i}"):
                                        user_msg = st.session_state.chat_history[i-1]["content"] if i > 0 else ""
                                        save_feedback(user_msg, msg["content"], "Good")
                                        st.session_state.chat_history[i]["feedback"] = "Good"
                                        st.rerun()
                                with f_col2:
                                    if st.button("👎", key=f"bad_{i}"):
                                        user_msg = st.session_state.chat_history[i-1]["content"] if i > 0 else ""
                                        save_feedback(user_msg, msg["content"], "Bad")
                                        st.session_state.chat_history[i]["feedback"] = "Bad"
                                        st.rerun()
                            else:
                                st.caption(f"Feedback: {msg['feedback']}")
    
    # --- HITL Grade Approval Panel ---
    pending = check_pending_grade(st.session_state.thread_id)
    if pending.get("pending"):
        details = pending.get("details", {})
        topic = details.get("topic", "the subject")
        change = details.get("change", 1)
        reason = details.get("reason", "Student answered a question.")
        
        st.markdown("---")
        with st.container():
            st.warning(f"⏳ **Grade Approval Required (Human-in-the-Loop)**")
            st.markdown(f"The Evaluator wants to award **+{change} point** in **{topic}**.")
            st.caption(f"Reason: _{reason}_")
            
            col_approve, col_reject = st.columns(2)
            with col_approve:
                if st.button("✅ Approve Grade", use_container_width=True, type="primary"):
                    result = approve_grade(st.session_state.thread_id, approved=True)
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": f"✅ **Grade Approved!** {result.get('message', 'Mastery updated.')}"
                    })
                    st.rerun()
            with col_reject:
                if st.button("❌ Reject Grade", use_container_width=True):
                    result = approve_grade(st.session_state.thread_id, approved=False)
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": f"❌ **Grade Rejected.** {result.get('message', 'No changes made.')}"
                    })
                    st.rerun()
    
    # Chat input using st.chat_input (modern and auto-clearing)
    if prompt := st.chat_input("Ask about your course materials...\n"):

        if not active_subject:
            st.warning("⚠️ Please select or create a subject first!")
        else:
            # Add user message to history
            st.session_state.chat_history.append({
                "role": "user",
                "content": prompt
            })
            
            with st.status("🤔 Thinking...", expanded=True) as status:
                # Be very explicit about the subject name to prevent AI hallucinations (e.g., 'data engineering' vs 'data eng')
                contextualized_input = (
                    f"### SYSTEM CONTEXT (CRITICAL):\n"
                    f"- Current Course: '{active_subject}' (Use this EXACT string for course_name parameter)\n"
                    f"- Student ID: '{st.session_state.thread_id}'\n\n"
                    f"{prompt}"
                )
                
                response = send_chat_message(contextualized_input)
                
                if "error" not in response:
                    assistant_message = response.get("final_answer", "No response received.")
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": assistant_message
                    })
                    status.update(label="✅ Answer Found!", state="complete", expanded=False)
                    st.rerun()
                else:
                    status.update(label="❌ Error", state="error")
                    st.error(f"Error: {response['error']}")

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
