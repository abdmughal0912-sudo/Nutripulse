@echo off
setlocal
cd /d "%~dp0"
title NutriPulse AI Nutrition Analyzer

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
  python -c "import sys; raise SystemExit(0 if (3,11) <= sys.version_info[:2] <= (3,12) else 1)" >nul 2>nul
  if errorlevel 1 goto :pythonversion
  set "PYTHON_CMD=python"
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating a private Python environment...
  %PYTHON_CMD% -m venv .venv
  if errorlevel 1 goto :error
)

".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if (3,11) <= sys.version_info[:2] <= (3,12) else 1)" >nul 2>nul
if errorlevel 1 (
  echo Existing .venv uses an unsupported Python version.
  echo Rename the .venv folder, then run START_APP.bat again with Python 3.12 installed.
  goto :error
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
if errorlevel 1 goto :error
python -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo.
echo Starting NutriPulse AI...
echo Your browser should open automatically.
python -m streamlit run app.py
goto :end

:pythonversion
echo.
echo NutriPulse requires Python 3.11 or 3.12. Python 3.14 is not used by this launcher.
echo Install Python 3.12, then run START_APP.bat again.
pause
goto :end

:error
echo.
echo Setup could not finish. Confirm that Python 3.11 or 3.12 is installed.
pause

:end
endlocal
