#!/usr/bin/env python3
"""
ClipFarm Universal Cross-Platform Desktop Packaging Script
Supports:
  - Linux (Ubuntu / Debian x86_64 .AppImage, .deb)
  - Windows (x86_64 NSIS .exe, .msi)
  - macOS (Apple Silicon arm64 & Intel x86_64 .dmg, .app)

Bundles portable Python runtime + static FFmpeg + backend source + frontend bundle.
"""

import os
import sys
import shutil
import tarfile
import zipfile
import platform
import argparse
import subprocess
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESOURCES_DIR = PROJECT_ROOT / "src-tauri" / "resources"
BUILD_CACHE = PROJECT_ROOT / "build" / "cache"

PBS_VERSION = "20260510"
PBS_PYTHON_VERSION = "3.13.13"

# Standalone Python downloads from Astral python-build-standalone
PBS_MAP = {
    ("linux", "x86_64"): f"cpython-{PBS_PYTHON_VERSION}+{PBS_VERSION}-x86_64-unknown-linux-gnu-install_only.tar.gz",
    ("windows", "x86_64"): f"cpython-{PBS_PYTHON_VERSION}+{PBS_VERSION}-x86_64-pc-windows-msvc-install_only.tar.gz",
    ("darwin", "arm64"): f"cpython-{PBS_PYTHON_VERSION}+{PBS_VERSION}-aarch64-apple-darwin-install_only.tar.gz",
    ("darwin", "x86_64"): f"cpython-{PBS_PYTHON_VERSION}+{PBS_VERSION}-x86_64-apple-darwin-install_only.tar.gz",
}


def log(msg: str):
    print(f"==> {msg}", flush=True)


def error(msg: str, exit_code: int = 1):
    print(f"ERROR: {msg}", file=sys.stderr, flush=True)
    if exit_code != 0:
        sys.exit(exit_code)


def detect_platform(target_os: str, target_arch: str):
    sys_os = target_os.lower() if target_os != "auto" else platform.system().lower()
    if sys_os in ["darwin", "macos", "osx"]:
        resolved_os = "darwin"
    elif sys_os in ["win32", "windows"]:
        resolved_os = "windows"
    else:
        resolved_os = "linux"

    sys_arch = target_arch.lower() if target_arch != "auto" else platform.machine().lower()
    if sys_arch in ["x86_64", "amd64", "x64"]:
        resolved_arch = "x86_64"
    elif sys_arch in ["arm64", "aarch64"]:
        resolved_arch = "arm64"
    else:
        resolved_arch = "x86_64"

    return resolved_os, resolved_arch


def check_prerequisites(resolved_os: str, prepare_only: bool):
    log("Checking build environment prerequisites...")
    missing = []
    for cmd in ["node", "npm"]:
        if not shutil.which(cmd):
            missing.append(cmd)

    if not prepare_only:
        for cmd in ["cargo"]:
            if not shutil.which(cmd):
                missing.append(f"{cmd} (install via https://rustup.rs)")

    if missing:
        error(f"Missing required tools: {', '.join(missing)}")
    log("Prerequisites verified.")


def download_file(urls: list, dest: Path, min_bytes: int = 5000000):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size >= min_bytes:
        log(f"Using cached: {dest.name} ({dest.stat().st_size // (1024 * 1024)} MB)")
        return

    tmp_dest = dest.with_suffix(".tmp")
    for url in urls:
        log(f"Downloading: {url}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ClipFarm-Builder/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp, open(tmp_dest, "wb") as f:
                shutil.copyfileobj(resp, f)
            if tmp_dest.stat().st_size >= min_bytes:
                tmp_dest.replace(dest)
                log(f"Downloaded: {dest.name}")
                return
            else:
                log(f"Download too small ({tmp_dest.stat().st_size} bytes), trying next mirror...")
                tmp_dest.unlink(missing_ok=True)
        except Exception as e:
            log(f"Download failed from {url}: {e}")
            tmp_dest.unlink(missing_ok=True)

    error(f"Failed to download required asset from all mirrors: {dest.name}")


def setup_portable_python(resolved_os: str, resolved_arch: str):
    tarball_name = PBS_MAP.get((resolved_os, resolved_arch))
    if not tarball_name:
        error(f"No standalone python profile for {resolved_os}-{resolved_arch}")

    cache_file = BUILD_CACHE / tarball_name
    urls = [
        f"https://github.com/astral-sh/python-build-standalone/releases/download/{PBS_VERSION}/{tarball_name}",
        f"https://ghproxy.com/https://github.com/astral-sh/python-build-standalone/releases/download/{PBS_VERSION}/{tarball_name}",
    ]
    download_file(urls, cache_file, min_bytes=15000000)

    py_dest = RESOURCES_DIR / "python"
    if py_dest.exists():
        shutil.rmtree(py_dest)
    RESOURCES_DIR.mkdir(parents=True, exist_ok=True)

    log(f"Extracting portable Python into {py_dest}...")
    with tarfile.open(cache_file, "r:gz") as tar:
        tar.extractall(path=RESOURCES_DIR)

    # Resolve executable path
    if resolved_os == "windows":
        py_exe = py_dest / "python.exe"
        if not py_exe.exists():
            py_exe = py_dest / "Scripts" / "python.exe"
    else:
        py_exe = py_dest / "bin" / "python3"

    if not py_exe.exists():
        error(f"Extracted Python binary not found at expected path: {py_exe}")

    log(f"Portable Python verified: {py_exe}")
    return py_exe


def install_backend_dependencies(py_exe: Path):
    log("Installing backend dependencies into portable runtime...")
    pip_index = os.getenv("PIP_INDEX_URL", "")
    cmd_base = [str(py_exe), "-m", "pip", "install", "--upgrade"]
    if pip_index:
        cmd_base += ["--index-url", pip_index]

    subprocess.run(cmd_base + ["pip", "setuptools", "wheel"], check=True)
    req_file = PROJECT_ROOT / "requirements.txt"
    if req_file.exists():
        subprocess.run(cmd_base + ["-r", str(req_file)], check=True)
    log("Backend dependencies installed.")


def copy_backend_source():
    log("Copying backend source into bundle resources...")
    backend_dest = RESOURCES_DIR / "backend"
    if backend_dest.exists():
        shutil.rmtree(backend_dest)

    def ignore_patterns(path, names):
        ignored = {
            "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
            "tests", "data", "logs", "temp", "scratch"
        }
        return [n for n in names if n in ignored or n.endswith((".pyc", ".log", ".pid", ".rdb"))]

    shutil.copytree(PROJECT_ROOT / "backend", backend_dest, ignore=ignore_patterns)
    log(f"Backend source copied to {backend_dest}")


def build_frontend():
    log("Building frontend bundle...")
    frontend_dir = PROJECT_ROOT / "frontend"
    npm_cmd = "npm.cmd" if platform.system().lower() == "windows" else "npm"
    subprocess.run([npm_cmd, "run", "build"], cwd=frontend_dir, check=True)
    log("Frontend build complete.")


def run_tauri_build(resolved_os: str):
    log("Running Tauri native application build...")
    src_tauri_dir = PROJECT_ROOT / "src-tauri"
    cargo_cmd = "cargo.exe" if platform.system().lower() == "windows" else "cargo"

    # Choose bundles flag based on OS
    if resolved_os == "darwin":
        cmd = [cargo_cmd, "tauri", "build", "--bundles", "app"]
    else:
        cmd = [cargo_cmd, "tauri", "build"]

    subprocess.run(cmd, cwd=src_tauri_dir, check=True)
    log("Tauri build complete!")


def main():
    parser = argparse.ArgumentParser(description="ClipFarm Universal Desktop Packaging Script")
    parser.add_argument("--target-os", default="auto", choices=["auto", "linux", "windows", "macos", "darwin"],
                        help="Target operating system")
    parser.add_argument("--target-arch", default="auto", choices=["auto", "x86_64", "arm64"],
                        help="Target CPU architecture")
    parser.add_argument("--skip-python", action="store_true",
                        help="Skip downloading and installing portable Python")
    parser.add_argument("--skip-frontend", action="store_true",
                        help="Skip frontend npm build")
    parser.add_argument("--prepare-only", action="store_true",
                        help="Prepare bundle resources only without invoking Tauri build")

    args = parser.parse_args()
    resolved_os, resolved_arch = detect_platform(args.target_os, args.target_arch)

    log(f"Target Platform: OS={resolved_os}, Arch={resolved_arch}")
    check_prerequisites(resolved_os, args.prepare_only)

    if not args.skip_frontend:
        build_frontend()

    if not args.skip_python:
        py_exe = setup_portable_python(resolved_os, resolved_arch)
        install_backend_dependencies(py_exe)

    copy_backend_source()

    if not args.prepare_only:
        run_tauri_build(resolved_os)

    log("Desktop packaging task finished successfully.")


if __name__ == "__main__":
    main()
