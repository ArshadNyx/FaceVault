#!/bin/bash
# Face Unlock System — Launch Script
# Starts the FastAPI server on http://localhost:8000

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo ""
echo "  ┌──────────────────────────────────────────┐"
echo "  │       Face Unlock System v2.0             │"
echo "  │       http://localhost:8000                │"
echo "  └──────────────────────────────────────────┘"
echo ""

python -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload
