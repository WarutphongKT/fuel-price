@echo off
setlocal
cd /d "%~dp0"

set PYTHON=python
where python >nul 2>nul || set PYTHON=py -3

echo [%date% %time%] fetch oil prices
%PYTHON% scripts\fetch.py
if errorlevel 1 echo [%date% %time%] !! fetch failed

echo [%date% %time%] build report
%PYTHON% scripts\report.py
if errorlevel 1 echo [%date% %time%] !! report failed

echo [%date% %time%] save history snapshot
%PYTHON% scripts\snapshot.py export data\history.json
if errorlevel 1 echo [%date% %time%] !! snapshot failed

echo [%date% %time%] publish
call publish.bat

echo [%date% %time%] done
endlocal
