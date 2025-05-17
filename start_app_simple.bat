@echo off
:: Simple starter script for USD Web Analysis
echo Starting USD Web Analysis...

:: Set the frontend directory
set FRONTEND_DIR=%~dp0frontend-new

:: Check if the directory exists
if not exist "%FRONTEND_DIR%" (
    echo ERROR: Frontend directory not found at %FRONTEND_DIR%
    echo.
    pause
    exit /b 1
)

:: Change to the frontend directory
cd /d "%FRONTEND_DIR%"
if errorlevel 1 (
    echo ERROR: Failed to change to frontend directory
    echo.
    pause
    exit /b 1
)

:: Run the application
echo Starting application...
npm run electron-dev

:: Wait before closing
echo.
echo Application closed. Press any key to exit...
pause > nul
