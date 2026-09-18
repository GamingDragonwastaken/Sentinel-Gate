#!/usr/bin/env bash
# SentinelGate Quick Start Script

if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Please run ./install.sh first."
    return 1 2>/dev/null || exit 1
fi

source venv/bin/activate

if [ -z "$GEMINI_API_KEY" ] && [ -z "$GOOGLE_API_KEY" ]; then
    echo "WARNING: GEMINI_API_KEY is not set."
    echo "The app will start in Offline Demo mode."
    echo "To use real inspections, set it like: export GEMINI_API_KEY=..."
fi

echo "Starting SentinelGate..."
cd sentinelgate && streamlit run app.py
