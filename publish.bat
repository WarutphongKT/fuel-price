@echo off
setlocal
cd /d "%~dp0"

rem Publish the generated dashboard to the git remote (e.g. GitHub Pages).
rem Safe with no remote configured: it prints a note and exits 0.

where git >nul 2>nul || (echo git not found - skip publish & exit /b 0)
git rev-parse --git-dir >nul 2>nul || (echo not a git repo - skip publish & exit /b 0)
git rev-parse --abbrev-ref "@{u}" >nul 2>nul || (echo no upstream remote - skip publish & exit /b 0)

git add dashboard.html index.html reports >nul
git diff --cached --quiet && (echo no changes to publish & exit /b 0)

git commit -q -m "Update dashboard %date% %time%"
if errorlevel 1 (echo commit failed & exit /b 1)

git push
if errorlevel 1 (echo push failed & exit /b 1)

echo published
endlocal
