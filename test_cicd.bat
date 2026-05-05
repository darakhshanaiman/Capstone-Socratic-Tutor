@echo off
REM Quick CI/CD Test Script for Lab 10
REM Tests the evaluation pipeline locally

echo.
echo ========================================
echo  Lab 10: CI/CD Pipeline Quick Test
echo ========================================
echo.

REM Check if GROQ_API_KEY is set
if "%GROQ_API_KEY%"=="" (
    echo ❌ GROQ_API_KEY environment variable not set!
    echo.
    echo Please set it with:
    echo   set GROQ_API_KEY=your_groq_api_key_here
    echo.
    pause
    exit /b 1
)

echo ✅ GROQ_API_KEY is set
echo.

REM Check if required files exist
if not exist "ci_eval.py" (
    echo ❌ ci_eval.py not found!
    pause
    exit /b 1
)

if not exist "test_dataset.json" (
    echo ❌ test_dataset.json not found!
    pause
    exit /b 1
)

if not exist "docker-compose.yaml" (
    echo ❌ docker-compose.yaml not found!
    pause
    exit /b 1
)

echo ✅ All required files found
echo.

REM Start containers if not running
echo 🔍 Checking if containers are running...
docker ps | findstr "rag-api" >nul
if errorlevel 1 (
    echo 🐳 Starting containers...
    docker compose up -d

    echo ⏳ Waiting for services to start...
    timeout /t 15 /nobreak >nul

    REM Check if API is responding
    curl -f http://localhost:8000/health >nul 2>&1
    if errorlevel 1 (
        echo ❌ API is not responding. Please check Docker logs:
        echo    docker compose logs rag-api
        pause
        exit /b 1
    )
) else (
    echo ✅ Containers are already running
)

echo.
echo 🧪 Running CI/CD evaluation...
echo.

REM Run the evaluation
python ci_eval.py --threshold 0.85

REM Get the exit code
set EXIT_CODE=%errorlevel%

echo.
echo ========================================
if %EXIT_CODE%==0 (
    echo 🎉 CI/CD TEST PASSED!
    echo    Agent meets quality standards.
) else (
    echo 💥 CI/CD TEST FAILED!
    echo    Agent below quality threshold.
)
echo ========================================
echo.

echo 💡 To run the full pipeline simulation:
echo    python simulate_cicd.py
echo.
echo 💡 To test breaking change detection:
echo    python test_breaking_change.py
echo.

pause