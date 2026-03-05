@echo off
setlocal enabledelayedexpansion

echo =====================================
echo    FIRST RUN MAY TAKE A FEW MINUTES
echo =====================================
echo.

:: Go to the folder where this .bat file lives
cd /d "%~dp0"

:: -----------------------------
:: Check Python
:: -----------------------------
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed on this computer.
    echo.
    echo Please follow these steps:
    echo   1. Open your browser and go to: https://www.python.org/downloads/
    echo   2. Click the big yellow "Download Python" button
    echo   3. Run the installer
    echo   4. IMPORTANT: Check the box that says "Add Python to PATH"
    echo   5. Once installed, double-click this file again
    echo.
    pause
    exit /b 1
)

echo [OK] Python is installed.

:: -----------------------------
:: Check pip
:: -----------------------------
pip --version >nul 2>&1
if errorlevel 1 (
    echo [INFO] pip is missing. Installing pip...
    python -m ensurepip --upgrade
)

echo [OK] pip is available.

:: -----------------------------
:: Install uv if missing
:: -----------------------------
uv --version >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing uv package manager...
    pip install uv

    :: Refresh PATH with all common Python Scripts locations
    for /f "delims=" %%i in ('python -c "import sysconfig; print(sysconfig.get_path(\"scripts\"))"') do (
        set "PATH=%%i;%PATH%"
    )
    set "PATH=%APPDATA%\Python\Scripts;%PATH%"
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%"
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python310\Scripts;%PATH%"
)

:: Use "python -m uv" as the reliable cross-machine way to call uv
set UV=python -m uv
echo [OK] uv is available.

:: -----------------------------
:: Create virtual environment
:: (delete it first if it exists but is broken/incomplete)
:: -----------------------------
if exist ".venv" (
    if not exist ".venv\Scripts\python.exe" (
        echo [INFO] Existing .venv is incomplete, recreating it...
        rmdir /s /q ".venv"
    )
)

if not exist ".venv" (
    echo [INFO] Creating virtual environment for the first time...
    %UV% venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo [OK] Virtual environment ready.

:: NOTE: No need to activate manually - uv sync and uv run handle the venv automatically

:: -----------------------------
:: Install dependencies
:: -----------------------------
echo [INFO] Installing project dependencies ^(this may take a minute^)...
%UV% sync
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    echo Make sure you have an internet connection and try again.
    pause
    exit /b 1
)

echo [OK] All dependencies installed.

:: -----------------------------
:: Run Streamlit
:: -----------------------------
echo.
echo =====================================
echo    Starting the application...
echo    A browser window will open soon.
echo    To stop the app, close this window.
echo =====================================
echo.

%UV% run streamlit run main.py

:: If we get here, the app was closed
echo.
echo Application has stopped.
pause