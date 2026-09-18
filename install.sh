#!/usr/bin/env bash
# SentinelGate Quick Install Script

echo "Welcome to SentinelGate Installer!"
echo "This will install SentinelGate on your local machine."

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "python3 could not be found. Please install Python 3.10+."
    # We don't exit in this script directly, we just return if we can't find python.
    return 1 2>/dev/null || exit 1
fi

# Check for Pip
if ! command -v pip3 &> /dev/null; then
    echo "pip3 could not be found. Please install pip for Python 3."
    return 1 2>/dev/null || exit 1
fi

echo "Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "Installing dependencies..."
pip install -r sentinelgate/requirements.txt

echo "Setting up Lobster Trap binary..."
python sentinelgate/setup_lobster.py

echo ""
echo "Installation Complete!"
echo "To run SentinelGate:"
echo "  1) source venv/bin/activate"
echo "  2) export GEMINI_API_KEY=your_key_here"
echo "  3) cd sentinelgate && streamlit run app.py"
