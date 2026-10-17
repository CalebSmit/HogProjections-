@echo off
REM Hog Projections launcher (Windows). Installs uv if needed, then starts the app.
cd /d "%~dp0"

set "PATH=%USERPROFILE%\.local\bin;%PATH%"
where uv >nul 2>nul
if errorlevel 1 (
  echo First run: installing uv ^(Python manager^)...
  powershell -NoProfile -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)

if not exist .env copy .env.example .env >nul

echo Starting Hog Projections at http://localhost:8501  (close this window to stop)
uv run --locked --no-dev streamlit run app.py
pause
