# Quick start script for RAG Pipeline with Streamlit
# Run with: .\start.ps1

Write-Host @"
========================================
 Socratic AI Tutor - Full Stack Startup
========================================
"@ -ForegroundColor Cyan

Write-Host ""
Write-Host "Checking Python environment..." -ForegroundColor Yellow

# Activate virtual environment if it exists
if (Test-Path ".venv\Scripts\Activate.ps1") {
    & ".venv\Scripts\Activate.ps1"
    Write-Host "✓ Virtual environment activated" -ForegroundColor Green
} else {
    Write-Host "⚠ No virtual environment found. Using system Python." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Starting services..." -ForegroundColor Yellow
Write-Host ""

# Start FastAPI backend
Write-Host "[1/2] Starting FastAPI Backend (port 8000)..." -ForegroundColor Cyan
Start-Process -FilePath "cmd" -ArgumentList "/k uvicorn api:app --reload --port 8000" -NoNewWindow:$false
Start-Sleep -Seconds 3

# Display connection info
Write-Host @"

========================================
   🚀 Services Starting...
   
   API Backend: http://localhost:8000
   Streamlit UI: http://localhost:8501
   
   Visit http://localhost:8501 in your browser!
========================================
"@ -ForegroundColor Green

Write-Host ""
Write-Host "[2/2] Starting Streamlit Frontend (port 8501)..." -ForegroundColor Cyan
Write-Host ""

# Start Streamlit
& streamlit run app_streamlit.py
