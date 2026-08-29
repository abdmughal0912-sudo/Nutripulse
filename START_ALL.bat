@echo off
setlocal
cd /d "%~dp0"
title NutriPulse v4.3 Full Stack Launcher
set "STARTUP_LOG=%CD%\NUTRIPULSE_STARTUP_LOG.txt"
set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"

>"%STARTUP_LOG%" echo NutriPulse v4.3 startup diagnostic
>>"%STARTUP_LOG%" echo Project: %CD%
>>"%STARTUP_LOG%" echo Started: %DATE% %TIME%

if not exist "app.py" goto :wrongfolder
if not exist "api.py" goto :wrongfolder
if not exist "requirements.txt" goto :wrongfolder

where py >nul 2>nul
if %errorlevel%==0 (
  py -V:3.12 -c "import sys" >nul 2>nul
  if not errorlevel 1 (
    set "PYTHON_CMD=py -V:3.12"
  ) else (
    py -V:3.11 -c "import sys" >nul 2>nul
    if errorlevel 1 goto :pythonversion
    set "PYTHON_CMD=py -V:3.11"
  )
) else (
  python -c "import sys; raise SystemExit(0 if sys.version_info[:2] in ((3,11),(3,12)) else 1)" >nul 2>nul
  if errorlevel 1 goto :pythonversion
  set "PYTHON_CMD=python"
)

if not exist "%PYTHON_EXE%" (
  echo Creating a private Python environment...
  >>"%STARTUP_LOG%" echo Creating .venv with %PYTHON_CMD%
  %PYTHON_CMD% -m venv .venv >>"%STARTUP_LOG%" 2>&1
  if errorlevel 1 goto :setup_error
)

"%PYTHON_EXE%" -c "import sys; raise SystemExit(0 if sys.version_info[:2] in ((3,11),(3,12)) else 1)" >nul 2>nul
if errorlevel 1 (
  >>"%STARTUP_LOG%" echo ERROR: Existing .venv uses an unsupported Python version.
  echo Existing .venv uses an unsupported Python version.
  echo Rename the .venv folder, then run START_ALL.bat again with Python 3.12.
  goto :setup_error
)

"%PYTHON_EXE%" scripts\runtime_check.py >>"%STARTUP_LOG%" 2>&1
if errorlevel 1 (
  echo Installing or repairing NutriPulse packages. This may take several minutes...
  "%PYTHON_EXE%" -m pip install --disable-pip-version-check --no-cache-dir -r requirements.txt >>"%STARTUP_LOG%" 2>&1
  if errorlevel 1 goto :setup_error
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem -LiteralPath '.venv' -Recurse -File | Unblock-File" >nul 2>nul
)

"%PYTHON_EXE%" scripts\runtime_check.py >>"%STARTUP_LOG%" 2>&1
if errorlevel 1 goto :runtime_error

echo Starting FastAPI in a second window...
start "NutriPulse FastAPI" "%PYTHON_EXE%" -m uvicorn api:app --host 127.0.0.1 --port 8000
timeout /t 2 >nul

echo Starting Streamlit at http://127.0.0.1:8501
"%PYTHON_EXE%" -m streamlit run app.py
goto :end

:pythonversion
echo.
echo NutriPulse requires Python 3.11 or 3.12.
echo Install Python 3.12, then run START_ALL.bat again.
>>"%STARTUP_LOG%" echo ERROR: Python 3.11 or 3.12 was not found.
pause
goto :end

:wrongfolder
echo.
echo NutriPulse files were not found beside this launcher.
echo Extract the complete ZIP before running START_ALL.bat.
>>"%STARTUP_LOG%" echo ERROR: app.py, api.py or requirements.txt is missing.
pause
goto :end

:setup_error
echo.
echo NutriPulse package setup could not finish.
echo Open this diagnostic file and send its contents:
echo %STARTUP_LOG%
pause
goto :end

:runtime_error
echo.
echo NutriPulse installed packages but the runtime check failed.
echo Open this diagnostic file and send its contents:
echo %STARTUP_LOG%
pause

:end
endlocal
