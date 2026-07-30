@echo off
setlocal

rem Absolute path of the directory containing this batch file.
set "SCRIPT_DIR=%~dp0"
set "VENV_DIR=%SCRIPT_DIR%.venv"
set "REQUIREMENTS_FILE=%SCRIPT_DIR%requirements.txt"

if not exist "%REQUIREMENTS_FILE%" (
    echo [ERROR] requirements.txt was not found.
    echo Path: "%REQUIREMENTS_FILE%"
    exit /b 1
)

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo Creating Python virtual environment...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create the virtual environment.
        exit /b 1
    )
) else (
    echo Using existing virtual environment: "%VENV_DIR%"
)

call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Failed to activate the virtual environment.
    exit /b 1
)

echo Upgrading pip...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip.
    exit /b 1
)

echo Installing packages from requirements.txt...
python -m pip install -r "%REQUIREMENTS_FILE%"
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    exit /b 1
)

echo.
echo Virtual environment is ready.
echo Path: "%VENV_DIR%"

endlocal
exit /b 0
