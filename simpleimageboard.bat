@echo off
SETLOCAL

REM Enable ANSI colors
SET ESC=

REM Set the Python executable path (leave as is if Python is in PATH)
SET PYTHON_PATH=python

REM Get the directory of this .bat file
SET SCRIPT_DIR=%~dp0

REM Python script for reasoning
SET PYTHON_SCRIPT=%SCRIPT_DIR%check_python_env.py

REM Check Python Path
where "%PYTHON_PATH%" >nul 2>nul
IF ERRORLEVEL 1 (
    echo %ESC%[31mPython not found. Ensure it's installed and in PATH.%ESC%[0m
    exit /b 1
)

REM Run the Python script for reasoning
echo %ESC%[36mRunning Python script to check and manage the virtual environment...%ESC%[0m
"%PYTHON_PATH%" "%PYTHON_SCRIPT%"
IF %ERRORLEVEL% NEQ 0 (
    echo %ESC%[31mAn error occurred while running the Python script. Exiting...%ESC%[0m
    exit /b %ERRORLEVEL%
)

REM Activate the virtual environment
SET VENV_DIR=%SCRIPT_DIR%env
CALL "%VENV_DIR%\Scripts\activate.bat"
IF %ERRORLEVEL% NEQ 0 (
    echo %ESC%[31mError activating virtual environment. Exiting...%ESC%[0m
    exit /b %ERRORLEVEL%
)

REM Upgrade pip explicitly
echo %ESC%[36mUpgrading pip...%ESC%[0m
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip
IF %ERRORLEVEL% NEQ 0 (
    echo %ESC%[31mError upgrading pip. Exiting...%ESC%[0m
    exit /b %ERRORLEVEL%
)

REM Install necessary dependencies
echo %ESC%[36mInstalling dependencies...%ESC%[0m
"%VENV_DIR%\Scripts\pip.exe" install -r "%SCRIPT_DIR%requirements.txt"
IF %ERRORLEVEL% NEQ 0 (
    echo %ESC%[31mError installing dependencies. Exiting...%ESC%[0m
    exit /b %ERRORLEVEL%
)

REM Run taginDB.py
echo.
echo %ESC%[36mRunning taginDB.py...%ESC%[0m
"%PYTHON_PATH%" "%SCRIPT_DIR%taginDB.py"
IF %ERRORLEVEL% NEQ 0 (
    echo %ESC%[31mError encountered in taginDB.py. Exiting...%ESC%[0m
    exit /b %ERRORLEVEL%
)

REM Ask the user if they want to run checkDatabase.py
echo.
echo %ESC%[36mRunning checkDatabase.py...%ESC%[0m
echo %ESC%[33mThe script to check the database for corruption and integrity may take a significant amount of time to run.%ESC%[0m
set /p RUN_CHECKDB=Do you want to run it? (Y/N): 
if /i "%RUN_CHECKDB%"=="Y" (
    echo %ESC%[36mRunning database checks...%ESC%[0m
    "%PYTHON_PATH%" "%SCRIPT_DIR%checkDatabase.py"
    IF %ERRORLEVEL% NEQ 0 (
        echo %ESC%[31mError encountered in checkDatabase.py. Exiting...%ESC%[0m
        exit /b %ERRORLEVEL%
    )
) else (
    echo %ESC%[33mSkipping database checks.%ESC%[0m
)

REM Run tagcounts.py
echo.
echo %ESC%[36mRunning tagcounts.py...%ESC%[0m
"%PYTHON_PATH%" "%SCRIPT_DIR%tagcounts.py"
IF %ERRORLEVEL% NEQ 0 (
    echo %ESC%[31mError encountered in tagcounts.py. Exiting...%ESC%[0m
    exit /b %ERRORLEVEL%
)

echo.
echo %ESC%[32mSetup executed successfully.%ESC%[0m

REM Run Images_searcher.py
echo.
echo %ESC%[36mRunning Images_searcher.py...%ESC%[0m
"%PYTHON_PATH%" "%SCRIPT_DIR%Images_searcher.py"
IF %ERRORLEVEL% NEQ 0 (
    echo %ESC%[31mError encountered in Images_searcher.py. Exiting...%ESC%[0m
    exit /b %ERRORLEVEL%
)

pause
