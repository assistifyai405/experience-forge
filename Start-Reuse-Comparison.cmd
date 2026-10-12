@echo off
setlocal
cd /d "%~dp0"
set "REUSE_RUN_DIR=runs\reuse-%RANDOM%-%RANDOM%"
python -X utf8 -m experience_forge reuse-benchmark --seed 60701 --trials 5 --output "%REUSE_RUN_DIR%"
if errorlevel 1 goto failed
python -X utf8 -m experience_forge reuse-verify --output "%REUSE_RUN_DIR%"
if errorlevel 1 goto failed
echo Report: %REUSE_RUN_DIR%\report.html
pause
exit /b 0
:failed
echo The run or verification stopped. Inspect existing logs; no automatic retry is performed.
pause
exit /b 1
