#!/usr/bin/env bash
# Hog Projections launcher (Mac / Linux). Installs uv if needed, then starts the app.
set -e
cd "$(dirname "$0")"

export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  echo "First run: installing uv (Python manager)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

[ -f .env ] || cp .env.example .env

echo "Starting Hog Projections at http://localhost:8501  (close this window to stop)"
exec uv run --locked --no-dev streamlit run app.py
