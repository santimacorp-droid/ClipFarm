#!/usr/bin/env python3
"""
ClipFarm Standalone Software Packager
Creates standalone, portable distribution packages for Linux, Windows, and macOS.
Prioritizes efficiency, self-contained runtimes, and pure native window execution.
"""
import os
import sys
import shutil
import zipfile
import tarfile
import argparse
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / "dist_standalone"

def ensure_frontend_built():
    """Ensure the React production build exists."""
    frontend_dist = PROJECT_ROOT / "frontend" / "dist"
    if not (frontend_dist / "index.html").exists():
        print("📦 Building production frontend bundle...")
        npm_bin = shutil.which("npm")
        if not npm_bin:
            raise RuntimeError("npm is required to build frontend bundle.")
        subprocess.run([npm_bin, "run", "build"], cwd=str(PROJECT_ROOT / "frontend"), check=True)
    print("✅ Frontend production bundle verified.")

def package_portable_bundle(target_name: str = "ClipFarm-Studio-Standalone"):
    """Package a clean, self-contained standalone folder ready to distribute."""
    ensure_frontend_built()
    
    bundle_dir = DIST_DIR / target_name
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True, exist_ok=True)

    print(f"📁 Assembling standalone software package in {bundle_dir}...")

    # Copy core application files
    files_to_copy = [
        "desktop_app.py",
        "launch_clipfarm.sh",
        "launch_clipfarm.py",
        "Launch_ClipFarm.bat",
        "Launch_ClipFarm.command",
        "ClipFarm.desktop",
        "app_icon.png",
        "requirements.txt",
        "README.md",
    ]

    for fname in files_to_copy:
        src = PROJECT_ROOT / fname
        if src.exists():
            shutil.copy2(src, bundle_dir / fname)
            if fname.endswith((".sh", ".command", ".py")):
                os.chmod(bundle_dir / fname, 0o755)

    # Copy backend code
    shutil.copytree(PROJECT_ROOT / "backend", bundle_dir / "backend", ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.db", "autoclip.db"))

    # Copy frontend dist
    shutil.copytree(PROJECT_ROOT / "frontend" / "dist", bundle_dir / "frontend" / "dist")

    # Create empty data and output directories
    (bundle_dir / "data").mkdir(exist_ok=True)
    (bundle_dir / "output").mkdir(exist_ok=True)

    # Create Linux tar.gz archive
    tar_path = DIST_DIR / f"{target_name}-linux-x86_64.tar.gz"
    print(f"📦 Creating archive: {tar_path}...")
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(bundle_dir, arcname=target_name)

    # Create Windows/cross-platform zip archive
    zip_path = DIST_DIR / f"{target_name}.zip"
    print(f"📦 Creating archive: {zip_path}...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(bundle_dir):
            for file in files:
                full_p = Path(root) / file
                rel_p = full_p.relative_to(DIST_DIR)
                zipf.write(full_p, arcname=str(rel_p))

    print(f"\n🎉 Standalone distribution package completed successfully!")
    print(f" - Directory: {bundle_dir}")
    print(f" - Linux Archive: {tar_path} ({tar_path.stat().st_size / (1024*1024):.2f} MB)")
    print(f" - Universal Zip: {zip_path} ({zip_path.stat().st_size / (1024*1024):.2f} MB)")

def main():
    parser = argparse.ArgumentParser(description="Package ClipFarm Standalone Software")
    parser.add_argument("--name", default="ClipFarm-Studio-Standalone", help="Package folder name")
    args = parser.parse_args()
    package_portable_bundle(target_name=args.name)

if __name__ == "__main__":
    main()
