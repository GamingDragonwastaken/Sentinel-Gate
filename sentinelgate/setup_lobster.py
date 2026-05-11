"""Download Veea's Lobster Trap binary into bin/ for the current platform.

Idempotent: skips the download if the binary is already present. Designed to
be safe to run before `pip install` — uses only the standard library.

Usage:
    python setup_lobster.py
"""

from __future__ import annotations

import os
import platform
import stat
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_RELEASE_URL = "https://github.com/veeainc/lobstertrap/releases/latest/download"

PROJECT_ROOT = Path(__file__).resolve().parent
BIN_DIR = PROJECT_ROOT / "bin"


def _detect_target() -> tuple[str, str]:
    """Return (asset_name, local_filename) for the current platform.

    Exits with an explanatory message on unsupported OS / architecture.
    """
    system = platform.system().lower()
    machine = platform.machine().lower()

    if machine in ("arm64", "aarch64") and system in ("darwin", "linux"):
        print(
            f"[setup_lobster] WARNING: detected {system}/{machine}; "
            f"only *-amd64 assets are published. Falling back to amd64 "
            f"(may run under emulation)."
        )

    if system == "linux":
        return "lobstertrap-linux-amd64", "lobstertrap"
    if system == "darwin":
        return "lobstertrap-darwin-amd64", "lobstertrap"
    if system == "windows":
        return "lobstertrap-windows-amd64.exe", "lobstertrap.exe"

    sys.exit(f"[setup_lobster] Unsupported OS: {system!r}")


def _download(url: str, dest: Path) -> None:
    """Download `url` to `dest`, streaming so we don't OOM on large binaries."""
    print(f"[setup_lobster] Downloading {url}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        with urllib.request.urlopen(url) as resp, open(tmp, "wb") as out:
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                out.write(chunk)
    except urllib.error.HTTPError as exc:
        if tmp.exists():
            tmp.unlink()
        sys.exit(
            f"[setup_lobster] HTTP {exc.code} fetching {url}\n"
            f"  Check that the release asset exists and the repo is public."
        )
    except urllib.error.URLError as exc:
        if tmp.exists():
            tmp.unlink()
        sys.exit(f"[setup_lobster] Network error fetching {url}: {exc.reason}")

    tmp.replace(dest)


def _make_executable(path: Path) -> None:
    if platform.system().lower() == "windows":
        return
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def ensure_binary() -> Path:
    """Ensure the Lobster Trap binary exists in bin/; return its path."""
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    asset, local_name = _detect_target()
    dest = BIN_DIR / local_name

    if dest.exists():
        print(f"[setup_lobster] Already present: {dest}")
        return dest

    url = f"{REPO_RELEASE_URL}/{asset}"
    _download(url, dest)
    _make_executable(dest)
    print(f"[setup_lobster] Installed: {dest}")
    return dest


def main() -> None:
    path = ensure_binary()
    print(f"\nBinary path: {path}")


if __name__ == "__main__":
    main()
