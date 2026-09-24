#!/usr/bin/env python3
"""
ClipFarm Desktop Application Launcher
Provides a seamless one-click desktop app experience for Linux, Windows, and macOS.
Starts the backend service and opens a dedicated native desktop window.
"""
import sys
import os
import time
import shutil
import signal
import socket
import atexit
import argparse
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
PROFILE_DIR = Path.home() / ".cache" / "clipfarm" / "app_profile"

def is_backend_ready(host: str, port: int) -> bool:
    """Check if the backend is already up and healthy."""
    url = f"http://{host}:{port}/health"
    try:
        with urllib.request.urlopen(url, timeout=1.0) as resp:
            return resp.status == 200
    except Exception:
        return False

def find_available_port(host: str = "127.0.0.1", preferred_port: int = 8765) -> int:
    """Find an available port, preferring 8765 or reusing an already-running ClipFarm."""
    if is_backend_ready(host, preferred_port):
        return preferred_port

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, preferred_port))
            return preferred_port
        except OSError:
            pass

    # Preferred port occupied by another service; find any free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]

def find_chromium_browser():
    """Find a Chromium-based browser that supports --app mode for a native window feel."""
    if sys.platform.startswith("linux"):
        candidates = [
            "google-chrome",
            "google-chrome-stable",
            "chromium",
            "chromium-browser",
            "msedge",
            "brave-browser",
        ]
        for name in candidates:
            path = shutil.which(name)
            if path:
                return path

    elif sys.platform == "darwin":
        mac_paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
        for p in mac_paths:
            if os.path.exists(p):
                return p

    elif sys.platform == "win32":
        win_paths = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        ]
        for p in win_paths:
            if os.path.exists(p):
                return p
        for name in ["chrome.exe", "msedge.exe"]:
            path = shutil.which(name)
            if path:
                return path

    return None

def start_backend(host: str, port: int) -> subprocess.Popen:
    """Start the FastAPI backend with uvicorn in desktop mode."""
    env = os.environ.copy()
    env["CLIPFARM_MODE"] = "desktop"
    env["CLIPFARM_STANDALONE"] = "true"
    env["CLIPFARM_DESKTOP_MODE"] = "true"
    env["USE_CELERY"] = "false"
    env["PYTHONPATH"] = str(PROJECT_ROOT)

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.app_factory:create_app",
        "--factory",
        "--host",
        host,
        "--port",
        str(port),
        "--log-level",
        "info",
    ]

    print(f"🚀 Starting ClipFarm backend on http://{host}:{port}...")
    backend_proc = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return backend_proc

def main():
    parser = argparse.ArgumentParser(description="ClipFarm Desktop Application Launcher")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=None, help="Port to bind (default: 8765 or auto-assigned)")
    parser.add_argument("--no-window", action="store_true", help="Start server only without launching desktop window")
    args = parser.parse_args()

    host = args.host
    port = args.port if args.port is not None else find_available_port(host, preferred_port=8765)
    app_url = f"http://{host}:{port}/"

    backend_proc = None

    def cleanup():
        if backend_proc and backend_proc.poll() is None:
            print("\n🛑 Shutting down ClipFarm backend service...")
            try:
                backend_proc.terminate()
                backend_proc.wait(timeout=3)
            except Exception:
                backend_proc.kill()
            print("👋 ClipFarm exited cleanly.")

    atexit.register(cleanup)

    def signal_handler(signum, frame):
        cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Check if already running
    if is_backend_ready(host, port):
        print(f"ℹ️  ClipFarm is already running on {app_url}")
    else:
        backend_proc = start_backend(host, port)
        # Wait for backend to be ready
        ready = False
        start_time = time.time()
        while time.time() - start_time < 20:
            if backend_proc.poll() is not None:
                # Backend failed to start
                out, _ = backend_proc.communicate()
                print("❌ Failed to start backend:\n", out)
                sys.exit(1)
            if is_backend_ready(host, port):
                ready = True
                break
            time.sleep(0.3)

        if not ready:
            print("❌ Backend startup timed out after 20 seconds.")
            cleanup()
            sys.exit(1)

        print(f"✅ ClipFarm backend is healthy and ready!")

    if args.no_window:
        print(f"\n✨ ClipFarm is running at {app_url}")
        print("Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        return

    # Prefer pure native PyQt6 desktop software if available
    try:
        from PyQt6 import QtWidgets
        import desktop_app
        desktop_app.main()
        return
    except ImportError:
        pass

    # Fallback: Launch standalone desktop window via Chromium app mode
    browser_bin = find_chromium_browser()
    window_proc = None

    if browser_bin:
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        print(f"🖥️  Launching dedicated desktop window via {Path(browser_bin).name}...")
        browser_cmd = [
            browser_bin,
            f"--app={app_url}",
            f"--user-data-dir={PROFILE_DIR}",
            "--class=ClipFarm",
            "--name=ClipFarm",
            "--app-id=ClipFarm",
            "--window-size=1366,880",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-sync",
            "--disable-background-networking",
            "--disable-default-apps",
        ]
        window_proc = subprocess.Popen(browser_cmd)
    else:
        print(f"🌐 Opening {app_url} in your default browser...")
        import webbrowser
        webbrowser.open(app_url)

    # If we have a dedicated window process, wait until it closes
    if window_proc:
        try:
            window_proc.wait()
            print("🚪 Desktop window closed.")
        except KeyboardInterrupt:
            pass
    elif backend_proc:
        try:
            print(f"\n✨ ClipFarm running at {app_url} — Press Ctrl+C to close.")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    main()
