import os
import sys
import subprocess
from pathlib import Path

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "start":
        # Check if lobster needs to be downloaded
        setup_script = Path(__file__).parent / "setup_lobster.py"
        subprocess.run([sys.executable, str(setup_script)], check=True)

        # Start streamlit
        app_script = Path(__file__).parent / "app.py"
        print(f"Starting SentinelGate via Streamlit from {app_script}...")

        # Run streamlit from the sentinelgate directory
        current_env = os.environ.copy()
        current_dir = Path(__file__).parent
        subprocess.run(["streamlit", "run", "app.py"], cwd=str(current_dir), env=current_env)
    else:
        print("Usage: sentinelgate start")

if __name__ == "__main__":
    main()
