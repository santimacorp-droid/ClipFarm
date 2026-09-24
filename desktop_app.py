#!/usr/bin/env python3
"""
ClipFarm Studio - Pure Native Desktop Software
Cross-platform standalone desktop application for Linux (Ubuntu), Windows, and macOS.
Prioritizes efficiency, smooth GPU-accelerated video editing, and native OS windowing.
"""
import sys
import os
import time
import socket
import signal
import atexit
import argparse
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
ICON_PATH = PROJECT_ROOT / "app_icon.png"
OUTPUT_DIR = PROJECT_ROOT / "output"

# Ensure environment is configured for desktop mode
os.environ.setdefault("CLIPFARM_MODE", "desktop")
os.environ.setdefault("CLIPFARM_STANDALONE", "true")
os.environ.setdefault("CLIPFARM_DESKTOP_MODE", "true")
os.environ.setdefault("USE_CELERY", "false")

def get_worker_log_file() -> Path:
    from backend.core.path_utils import get_log_file_path
    log_file = get_log_file_path().parent / "worker.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    return log_file

def is_backend_ready(host: str, port: int) -> bool:
    """Check if the internal backend service is healthy."""
    url = f"http://{host}:{port}/health"
    try:
        with urllib.request.urlopen(url, timeout=0.8) as resp:
            return resp.status == 200
    except Exception:
        return False

def find_available_port(host: str = "127.0.0.1", preferred_port: int = 8765) -> int:
    """Find a dedicated local loopback port, avoiding any external collisions."""
    if is_backend_ready(host, preferred_port):
        return preferred_port

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, preferred_port))
            return preferred_port
        except OSError:
            pass

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]

def get_python_interpreter() -> str:
    """Ensure the project's virtualenv Python interpreter is prioritized."""
    candidates = [
        os.environ.get("CLIPFARM_PYTHON"),
        PROJECT_ROOT / "venv" / "bin" / "python",
        Path.home() / ".local" / "share" / "clipfarm" / "venv" / "bin" / "python",
        PROJECT_ROOT / "venv" / "Scripts" / "python.exe",
    ]
    for c in candidates:
        if c and Path(c).is_file() and os.access(c, os.X_OK):
            return str(c)
    return sys.executable

def start_backend_process(host: str, port: int) -> subprocess.Popen:
    """Start the standalone backend engine in an isolated high-performance worker process."""
    env = os.environ.copy()
    env["CLIPFARM_MODE"] = "desktop"
    env["CLIPFARM_STANDALONE"] = "true"
    env["CLIPFARM_DESKTOP_MODE"] = "true"
    env["USE_CELERY"] = "false"
    env["PYTHONPATH"] = str(PROJECT_ROOT)

    python_bin = get_python_interpreter()
    cmd = [
        python_bin,
        "-m",
        "uvicorn",
        "backend.app_factory:create_app",
        "--factory",
        "--host",
        host,
        "--port",
        str(port),
        "--log-level",
        "warning",
    ]

    log_file = get_worker_log_file()
    log_fp = open(log_file, "a", encoding="utf-8")
    popen_kwargs = {
        "cwd": str(PROJECT_ROOT),
        "env": env,
        "stdout": log_fp,
        "stderr": log_fp,
    }
    if sys.platform != "win32":
        popen_kwargs["start_new_session"] = True
    backend_proc = subprocess.Popen(cmd, **popen_kwargs)
    return backend_proc, log_fp

def run_native_qt_app(host: str, port: int, backend_proc: subprocess.Popen):
    """Run the 100% native PyQt6 desktop application window."""
    from PyQt6 import QtWidgets, QtCore, QtGui
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings

    app = QtWidgets.QApplication(sys.argv)
    QtCore.QCoreApplication.setApplicationName("ClipFarm")
    QtCore.QCoreApplication.setOrganizationName("ClipFarm")
    app.setApplicationDisplayName("ClipFarm Studio")
    if hasattr(QtGui.QGuiApplication, "setDesktopFileName"):
        QtGui.QGuiApplication.setDesktopFileName("ClipFarm.desktop")

    # Set application icon
    if ICON_PATH.exists():
        app_icon = QtGui.QIcon(str(ICON_PATH))
        app.setWindowIcon(app_icon)
    else:
        app_icon = None

    class MainWindow(QtWidgets.QMainWindow):
        def __init__(self, app_url: str):
            super().__init__()
            self.app_url = app_url
            self.setWindowTitle("ClipFarm Studio")
            self.resize(1366, 850)
            self.setMinimumSize(1024, 680)

            if app_icon:
                self.setWindowIcon(app_icon)

            # Center on screen
            screen = QtGui.QGuiApplication.primaryScreen()
            if screen:
                geo = screen.availableGeometry()
                x = (geo.width() - self.width()) // 2
                y = (geo.height() - self.height()) // 2
                self.move(x, y)

            # Create native WebEngine View
            self.browser = QWebEngineView(self)
            
            # Configure high-performance WebEngine settings
            settings = self.browser.settings()
            settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
            settings.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)

            self.setCentralWidget(self.browser)
            # Completely hide and disable the menubar for a sleek, modern desktop appearance
            mb = self.menuBar()
            if mb:
                mb.clear()
                mb.setVisible(False)
                mb.hide()
            self._create_shortcuts()

            # Keep window title locked cleanly to ClipFarm Studio
            self.browser.titleChanged.connect(lambda _: self.setWindowTitle("ClipFarm Studio"))

            # Load the local standalone application
            self.browser.setUrl(QtCore.QUrl(self.app_url))

        def _create_shortcuts(self):
            # Output folder shortcut
            open_output_action = QtGui.QAction(self)
            open_output_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+O"))
            open_output_action.triggered.connect(self._open_output_folder)
            self.addAction(open_output_action)

            # Exit shortcut
            exit_action = QtGui.QAction(self)
            exit_action.setShortcut(QtGui.QKeySequence("Ctrl+Q"))
            exit_action.triggered.connect(self.close)
            self.addAction(exit_action)

            # Reload shortcut
            reload_action = QtGui.QAction(self)
            reload_action.setShortcut(QtGui.QKeySequence("Ctrl+R"))
            reload_action.triggered.connect(self.browser.reload)
            self.addAction(reload_action)

            # Zoom shortcuts
            zoom_in = QtGui.QAction(self)
            zoom_in.setShortcut(QtGui.QKeySequence("Ctrl+="))
            zoom_in.triggered.connect(lambda: self.browser.setZoomFactor(self.browser.zoomFactor() + 0.1))
            self.addAction(zoom_in)

            zoom_out = QtGui.QAction(self)
            zoom_out.setShortcut(QtGui.QKeySequence("Ctrl+-"))
            zoom_out.triggered.connect(lambda: self.browser.setZoomFactor(max(0.5, self.browser.zoomFactor() - 0.1)))
            self.addAction(zoom_out)

            zoom_reset = QtGui.QAction(self)
            zoom_reset.setShortcut(QtGui.QKeySequence("Ctrl+0"))
            zoom_reset.triggered.connect(lambda: self.browser.setZoomFactor(1.0))
            self.addAction(zoom_reset)

            # Fullscreen shortcut
            fs_action = QtGui.QAction(self)
            fs_action.setShortcut(QtGui.QKeySequence("F11"))
            fs_action.triggered.connect(self._toggle_fullscreen)
            self.addAction(fs_action)

            # About shortcut
            about_action = QtGui.QAction(self)
            about_action.setShortcut(QtGui.QKeySequence("F1"))
            about_action.triggered.connect(self._show_about)
            self.addAction(about_action)

        def _open_output_folder(self):
            try:
                from backend.core.path_utils import reveal_in_file_manager, get_output_directory
                reveal_in_file_manager(get_output_directory())
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Error", f"Could not open output folder: {e}")

        def _toggle_fullscreen(self):
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()

        def _show_about(self):
            QtWidgets.QMessageBox.about(
                self,
                "About ClipFarm Studio",
                "<h3>ClipFarm Studio</h3>"
                "<p>Version 2.0.0 (Native Desktop Edition)</p>"
                "<p>High-efficiency AI Short-Form Video Processing & Clipping Software.</p>"
                "<p>Hardware-accelerated native standalone application.</p>"
            )

        def closeEvent(self, event):
            event.accept()

    window = MainWindow(f"http://{host}:{port}/")
    window.show()

    # Clean exit handler
    exit_code = app.exec()
    return exit_code

def main():
    parser = argparse.ArgumentParser(description="ClipFarm Studio Native Desktop Software")
    parser.add_argument("--host", default="127.0.0.1", help="Loopback host interface (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=None, help="Port to bind (default: 8765 or auto-assigned)")
    parser.add_argument("--headless", "--no-window", action="store_true", help="Run backend worker only in headless mode")
    args = parser.parse_args()

    host = args.host
    port = args.port if args.port is not None else find_available_port(host, preferred_port=8765)
    app_url = f"http://{host}:{port}/"

    backend_proc = None
    _log_fp = None

    def cleanup():
        nonlocal backend_proc, _log_fp
        if backend_proc and backend_proc.poll() is None:
            try:
                if sys.platform != "win32":
                    import os, signal
                    os.killpg(os.getpgid(backend_proc.pid), signal.SIGTERM)
                else:
                    backend_proc.terminate()
                backend_proc.wait(timeout=2)
            except Exception:
                try:
                    if sys.platform != "win32":
                        import os, signal
                        os.killpg(os.getpgid(backend_proc.pid), signal.SIGKILL)
                    else:
                        backend_proc.kill()
                except Exception:
                    pass
            backend_proc = None
        if _log_fp is not None:
            try:
                _log_fp.close()
            except Exception:
                pass
            _log_fp = None

    atexit.register(cleanup)

    def signal_handler(signum, frame):
        cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start internal backend worker if not already running
    if not is_backend_ready(host, port):
        backend_proc, _log_fp = start_backend_process(host, port)
        # Wait up to 15s for ready
        ready = False
        start_time = time.time()
        while time.time() - start_time < 15:
            if backend_proc.poll() is not None:
                print("❌ Internal worker exited unexpectedly during startup.")
                log_file = get_worker_log_file()
                if log_file.exists():
                    tail = log_file.read_text(errors="ignore").splitlines()[-20:]
                    print("\n--- Worker Error Log Tail ---")
                    print("\n".join(tail))
                sys.exit(1)
            if is_backend_ready(host, port):
                ready = True
                break
            time.sleep(0.2)

        if not ready:
            print("❌ Backend initialization timed out.")
            log_file = get_worker_log_file()
            if log_file.exists():
                tail = log_file.read_text(errors="ignore").splitlines()[-20:]
                print("\n--- Worker Timeout Log Tail ---")
                print("\n".join(tail))
            cleanup()
            sys.exit(1)

    if args.headless:
        print(f"✨ ClipFarm internal worker running on {app_url} (Headless Mode)")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            cleanup()
        return

    # Check if PyQt6 is available for pure native mode
    try:
        from PyQt6 import QtWidgets
        # Run native Qt application
        exit_code = run_native_qt_app(host, port, backend_proc)
        cleanup()
        sys.exit(exit_code)
    except ImportError:
        # Fallback to Chromium app mode window if PyQt6 is not installed on system
        print("ℹ️  Running in standalone window mode...")
        from launch_clipfarm import find_chromium_browser, PROFILE_DIR
        browser_bin = find_chromium_browser()
        if browser_bin:
            cmd = [
                browser_bin,
                f"--app={app_url}",
                f"--user-data-dir={PROFILE_DIR}",
                "--class=ClipFarm",
                "--name=ClipFarm",
                "--app-id=ClipFarm",
                "--window-size=1366,850",
                "--no-first-run",
                "--no-default-browser-check",
            ]
            win_proc = subprocess.Popen(cmd)
            win_proc.wait()
        else:
            import webbrowser
            webbrowser.open(app_url)
        cleanup()

if __name__ == "__main__":
    main()
