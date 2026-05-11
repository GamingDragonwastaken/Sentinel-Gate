"""Probe the Lobster Trap binary's CLI surface.

Ensures the binary is installed (via setup_lobster), then runs it with
`--help` and prints stdout/stderr verbatim. The captured output is what we
need to learn the real flag names, default port, config-file convention,
etc. before wiring up `security/inspector.py`.

Usage:
    python test_lobster.py
"""

from __future__ import annotations

import subprocess
import sys

from setup_lobster import ensure_binary


def main() -> int:
    binary = ensure_binary()

    print("\n" + "=" * 60)
    print(f"Running: {binary} --help")
    print("=" * 60)

    try:
        result = subprocess.run(
            [str(binary), "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError:
        print(f"[test_lobster] Binary not found or not executable: {binary}")
        return 2
    except subprocess.TimeoutExpired:
        print("[test_lobster] --help did not return within 10s; the binary "
              "may not support --help. Try -h or no args.")
        return 3

    print(f"\nexit code: {result.returncode}")
    print("\n--- stdout ---")
    print(result.stdout or "(empty)")
    print("--- stderr ---")
    print(result.stderr or "(empty)")
    print("--- end ---")

    return 0 if result.returncode == 0 else result.returncode


if __name__ == "__main__":
    sys.exit(main())
