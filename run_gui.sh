#!/bin/bash

echo ""
echo "================================"
echo "  Chess Master GUI"
echo "================================"
echo ""
echo "Checking dependencies..."

if ! python -c "import flask_socketio" 2>/dev/null; then
    echo "Installing Flask dependencies..."
    pip install -q -r requirements-gui.txt
fi

echo ""
echo "Starting server on http://localhost:5000"
echo ""
echo "Press Ctrl+C to stop"
echo ""

python app.py
