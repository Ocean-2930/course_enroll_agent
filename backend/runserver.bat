@echo off
setlocal

rem Absolute path of the directory containing this batch file.
set "SCRIPT_DIR=%~dp0"
set "VENV_DIR=%SCRIPT_DIR%.venv"

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [ERROR] Virtual environment was not found.
    echo Run init_venv.bat first.
    exit /b 1
)

call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Failed to activate the virtual environment.
    exit /b 1
)

pushd "%SCRIPT_DIR%"
if errorlevel 1 (
    echo [ERROR] Failed to enter the backend directory.
    exit /b 1
)

echo Starting FastAPI server...
echo Health: http://127.0.0.1:8000/api/health
echo Docs: http://127.0.0.1:8000/docs
echo Press Ctrl+C to stop.
echo.

python -m uvicorn main:app --host 127.0.0.1 --port 8000
set "SERVER_EXIT_CODE=%ERRORLEVEL%"

popd
endlocal & exit /b %SERVER_EXIT_CODE%
