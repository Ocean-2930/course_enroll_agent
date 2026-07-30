@echo off
setlocal

rem Absolute path of the directory containing this batch file.
set "SCRIPT_DIR=%~dp0"
set "HOST=127.0.0.1"
set "PORT=5173"

if not exist "%SCRIPT_DIR%index.html" (
    echo [ERROR] index.html was not found.
    echo Path: "%SCRIPT_DIR%index.html"
    exit /b 1
)

pushd "%SCRIPT_DIR%"
if errorlevel 1 (
    echo [ERROR] Failed to enter the frontend directory.
    exit /b 1
)

echo Starting frontend static server...
echo URL: http://%HOST%:%PORT%/
echo Press Ctrl+C to stop.
echo.

python -m http.server %PORT% --bind %HOST%
set "SERVER_EXIT_CODE=%ERRORLEVEL%"

popd
endlocal & exit /b %SERVER_EXIT_CODE%
