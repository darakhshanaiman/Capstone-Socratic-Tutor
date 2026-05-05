@echo off
REM Quick start script for RAG Pipeline with Streamlit
REM This script starts both the FastAPI backend and Streamlit frontend

echo.
echo ========================================
echo  Socratic AI Tutor - Full Stack Startup
echo ========================================
echo.

REM Activate virtual environment if it exists
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    echo ✓ Virtual environment activated
) else (
    echo ⚠ No virtual environment found. Using system Python.
)

echo.
echo Starting services...
echo.

REM Start FastAPI in background
echo [1/2] Starting FastAPI Backend (port 8000)...
start cmd /k "uvicorn api:app --reload --port 8000"
timeout /t 3 /nobreak

REM Start Streamlit
echo [2/2] Starting Streamlit Frontend (port 8501)...
echo.
echo ========================================
echo   API Backend: http://localhost:8000
echo   Streamlit UI: http://localhost:8501
echo ========================================
echo.
streamlit run app_streamlit.py
