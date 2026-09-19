import os
import sys
import subprocess
from pathlib import Path
import uvicorn

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "start":
        # Check if lobster needs to be downloaded
        setup_script = Path(__file__).parent / "setup_lobster.py"
        subprocess.run([sys.executable, str(setup_script)], check=True)

        # Start uvicorn
        print(f"Starting SentinelGate Backend API...")
        uvicorn.run("sentinelgate.api.server:app", host="0.0.0.0", port=8501, reload=False)
    else:
        print("Usage: sentinelgate start")

if __name__ == "__main__":
    main()
