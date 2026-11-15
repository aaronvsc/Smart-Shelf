#!/bin/bash
# Starts Smart-Shelf (Architecture A: Pipe-and-Filter) in your web browser.
# The first run creates a private Python environment (.venv) and installs packages.
cd "$(dirname "$0")" || exit 1
PY=""
for candidate in python3.14 python3.13 python3.12 python3; do   # newest Python 3.12+ found
  if command -v "$candidate" >/dev/null 2>&1 &&
     "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 12))' 2>/dev/null; then
    PY=$candidate
    break
  fi
done
if [ -z "$PY" ]; then
  echo "Smart-Shelf needs Python 3.12 or newer: https://www.python.org/downloads/"
  exit 1
fi
if [ ! -x .venv/bin/python ]; then
  echo "First run: setting up Python packages (about a minute)..."
  "$PY" -m venv .venv && .venv/bin/python -m pip install -r requirements.txt || exit 1
fi
echo "Smart-Shelf is starting at http://localhost:8501  (press Ctrl+C here to stop it)"
(sleep 4; xdg-open http://localhost:8501 >/dev/null 2>&1) &
.venv/bin/python -m streamlit run smart_shelf/ui/app.py --server.headless true --server.port 8501
