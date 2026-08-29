@echo off
setlocal
cd /d "%~dp0"
title NutriPulse Vision Model Restore

set "MODEL=models\food_classifier.onnx"
set "PART1=models\food_classifier.onnx.part1"
set "PART2=models\food_classifier.onnx.part2"
set "PART3=models\food_classifier.onnx.part3"
set "EXPECTED=87b73d4d635e9f5cf611021cbf6db1b1d7d4b1965b19fe383abaf0aee3617f09"

if not exist "%PART1%" goto :missing
if not exist "%PART2%" goto :missing
if not exist "%PART3%" goto :missing

echo Rebuilding the verified Food Vision model...
copy /b "%PART1%"+"%PART2%"+"%PART3%" "%MODEL%" >nul
if errorlevel 1 goto :error

for /f %%H in ('powershell -NoProfile -Command "(Get-FileHash -Algorithm SHA256 '%MODEL%').Hash.ToLowerInvariant()"') do set "ACTUAL=%%H"
if /I not "%ACTUAL%"=="%EXPECTED%" goto :integrity

echo.
echo Food Vision model restored and verified successfully.
echo You can now double-click START_ALL.bat.
pause
goto :end

:missing
echo.
echo One or more Vision model parts are missing.
echo Extract Vision Part 1, Part 2 and Part 3 into the same NutriPulse_App folder.
pause
goto :end

:integrity
echo.
echo The rebuilt model did not pass its integrity check.
echo Download all three Vision parts again, then rerun this file.
pause
goto :end

:error
echo.
echo Windows could not rebuild the model. Confirm that all parts are in the models folder.
pause

:end
endlocal
