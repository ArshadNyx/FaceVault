@echo off
REM Face Unlock Application Launcher
REM This batch file starts the Face Unlock application

REM Change to the application directory
cd /d "%~dp0"

REM Activate virtual environment and run the application
call "%~dp0venv\Scripts\activate.bat"
python "%~dp0main_gui.py"

REM If the application closes, pause to see any errors
if errorlevel 1 (
    echo.
    echo Application exited with an error.
    pause
)
