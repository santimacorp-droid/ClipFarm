#!/usr/bin/env python3
"""
ClipFarm Studio - Release Package Builder
Generates production-ready distribution packages for Ubuntu/Linux, Windows, and macOS:
  - Ubuntu/Debian native package: clipfarm_2.0.0_amd64.deb
  - Universal Linux self-extracting installer: ClipFarm-Studio-Linux-x86_64.run
  - Universal Linux archive: ClipFarm-Studio-Linux-x86_64.tar.gz
  - Windows standalone package: ClipFarm-Studio-Windows-x64.zip
  - macOS standalone package: ClipFarm-Studio-macOS.zip
  - Download page artifact & manifest: release/DOWNLOADS.md and release/index.html
"""
import os
import sys
import shutil
import zipfile
import tarfile
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RELEASE_DIR = PROJECT_ROOT / "release"
BUILD_DIR = Path("/tmp/clipfarm_release_staging")
APP_NAME = "clipfarm"
APP_DISPLAY_NAME = "ClipFarm Studio"
VERSION = "2.0.0"

def log(msg: str):
    print(f"==> {msg}", flush=True)

def ensure_frontend_built():
    """Verify that frontend/dist exists with compiled assets."""
    dist_dir = PROJECT_ROOT / "frontend" / "dist"
    if not (dist_dir / "index.html").exists():
        log("Compiling production frontend bundle...")
        npm_bin = shutil.which("npm")
        if not npm_bin:
            raise RuntimeError("npm is required to build the frontend bundle.")
        subprocess.run([npm_bin, "run", "build"], cwd=str(PROJECT_ROOT / "frontend"), check=True)
    log("Frontend production assets verified.")

def assemble_base_files(target_dir: Path):
    """Assemble all core software files into target_dir."""
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    # Core executables and scripts
    files = [
        "desktop_app.py",
        "launch_clipfarm.sh",
        "launch_clipfarm.py",
        "installer_wizard.py",
        "install.sh",
        "Launch_ClipFarm.bat",
        "Install_ClipFarm.bat",
        "Launch_ClipFarm.command",
        "Install_ClipFarm.command",
        "ClipFarm.desktop",
        "app_icon.png",
        "requirements.txt",
        "README.md",
    ]

    for f in files:
        src = PROJECT_ROOT / f
        if src.exists():
            shutil.copy2(src, target_dir / f)
            if f.endswith((".sh", ".command", ".py")):
                os.chmod(target_dir / f, 0o755)

    # Backend
    shutil.copytree(
        PROJECT_ROOT / "backend",
        target_dir / "backend",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.db", "autoclip.db")
    )

    # Frontend dist
    shutil.copytree(PROJECT_ROOT / "frontend" / "dist", target_dir / "frontend" / "dist")

    # Local storage placeholders
    (target_dir / "data").mkdir(exist_ok=True)
    (target_dir / "output").mkdir(exist_ok=True)
    (target_dir / "logs").mkdir(exist_ok=True)

def build_ubuntu_deb():
    """Build native Debian / Ubuntu .deb package using dpkg-deb."""
    log(f"Building Ubuntu/Debian .deb package (clipfarm_{VERSION}_amd64.deb)...")
    deb_root = BUILD_DIR / "deb"
    if deb_root.exists():
        shutil.rmtree(deb_root)

    # Directory layout according to FHS
    opt_dir = deb_root / "opt" / "clipfarm"
    bin_dir = deb_root / "usr" / "bin"
    apps_dir = deb_root / "usr" / "share" / "applications"
    icons_dir = deb_root / "usr" / "share" / "icons" / "hicolor" / "512x512" / "apps"
    debian_dir = deb_root / "DEBIAN"

    bin_dir.mkdir(parents=True, exist_ok=True)
    apps_dir.mkdir(parents=True, exist_ok=True)
    icons_dir.mkdir(parents=True, exist_ok=True)
    debian_dir.mkdir(parents=True, exist_ok=True)

    # 1. Copy app to /opt/clipfarm
    assemble_base_files(opt_dir)

    # 2. Symlink /usr/bin/clipfarm -> /opt/clipfarm/launch_clipfarm.sh
    launcher_symlink = bin_dir / "clipfarm"
    if launcher_symlink.exists():
        launcher_symlink.unlink()
    # Relative symlink inside the deb package
    os.symlink("/opt/clipfarm/launch_clipfarm.sh", str(launcher_symlink))

    # 3. Desktop shortcut in /usr/share/applications/clipfarm.desktop
    desktop_content = """[Desktop Entry]
Version=1.0
Type=Application
Name=ClipFarm Studio
GenericName=AI Video Clipping Studio
Comment=AI Short-Form Video Clipping & Studio
Exec=/opt/clipfarm/launch_clipfarm.sh
Icon=clipfarm
Terminal=false
StartupNotify=true
StartupWMClass=ClipFarm
Categories=AudioVideo;Video;AudioVideoEditing;
Keywords=video;clips;ai;shortform;tiktok;reels;youtube;
"""
    (apps_dir / "clipfarm.desktop").write_text(desktop_content, encoding="utf-8")
    os.chmod(apps_dir / "clipfarm.desktop", 0o644)

    # 4. App Icon in /usr/share/icons/hicolor/512x512/apps/clipfarm.png
    if (PROJECT_ROOT / "app_icon.png").exists():
        shutil.copy2(PROJECT_ROOT / "app_icon.png", icons_dir / "clipfarm.png")

    # 5. DEBIAN/control
    control_content = f"""Package: clipfarm
Version: {VERSION}
Section: video
Priority: optional
Architecture: amd64
Maintainer: ClipFarm Team <contact@clipfarm.app>
Depends: python3 (>= 3.10), ffmpeg
Homepage: https://clipfarm.app
Description: ClipFarm Studio - AI Video Clipping & Studio
 High-efficiency native standalone desktop software for automated viral video
 clipping, AI scoring, Whisper speech-to-text, and vertical video rendering.
 Zero web servers, zero external browser tabs, 100% private local processing.
"""
    (debian_dir / "control").write_text(control_content, encoding="utf-8")

    # 6. DEBIAN/postinst
    postinst_content = """#!/bin/sh
set -e
chmod +x /opt/clipfarm/*.sh /opt/clipfarm/*.py 2>/dev/null || true
mkdir -p /opt/clipfarm/data /opt/clipfarm/logs /opt/clipfarm/output 2>/dev/null || true
chmod -R 777 /opt/clipfarm/data /opt/clipfarm/logs /opt/clipfarm/output 2>/dev/null || true
ln -sf /opt/clipfarm/launch_clipfarm.sh /usr/bin/clipfarm
update-desktop-database /usr/share/applications 2>/dev/null || true
gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true
exit 0
"""
    postinst_path = debian_dir / "postinst"
    postinst_path.write_text(postinst_content, encoding="utf-8")
    os.chmod(postinst_path, 0o755)

    # 7. DEBIAN/prerm
    prerm_content = """#!/bin/sh
set -e
rm -f /usr/bin/clipfarm 2>/dev/null || true
exit 0
"""
    prerm_path = debian_dir / "prerm"
    prerm_path.write_text(prerm_content, encoding="utf-8")
    os.chmod(prerm_path, 0o755)

    # 8. Build package
    os.chmod(deb_root, 0o755)
    os.chmod(debian_dir, 0o755)
    deb_output = RELEASE_DIR / f"clipfarm_{VERSION}_amd64.deb"
    subprocess.run([
        "dpkg-deb",
        "--build",
        "--root-owner-group",
        str(deb_root),
        str(deb_output)
    ], check=True)

    size_mb = deb_output.stat().st_size / (1024 * 1024)
    log(f"✅ Created Ubuntu package: {deb_output.name} ({size_mb:.2f} MB)")
    return deb_output

def build_linux_run_installer():
    """Build universal self-extracting Linux .run installer."""
    log("Building universal Linux self-extracting package (ClipFarm-Studio-Linux-x86_64.run)...")
    payload_dir = BUILD_DIR / "run_payload"
    assemble_base_files(payload_dir)

    # Create temporary tar.gz archive of payload
    temp_tar = BUILD_DIR / "payload.tar.gz"
    with tarfile.open(temp_tar, "w:gz") as tar:
        tar.add(payload_dir, arcname="clipfarm-studio")

    # Installer shell header script
    header = f"""#!/bin/bash
# ==============================================================================
# ClipFarm Studio - Universal Linux Self-Extracting Installer
# ==============================================================================
set -e

echo "============================================================"
echo "         ClipFarm Studio v{VERSION} - Setup Installer       "
echo "============================================================"

# Default install target: ~/.local/share/clipfarm or specified path
INSTALL_DIR="${{CLIPFARM_INSTALL_DIR:-$HOME/.local/share/clipfarm}}"

echo "==> Extracting ClipFarm Studio files to: $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"

# Find payload offset
PAYLOAD_LINE=$(awk '/^__PAYLOAD_ARCHIVE_BELOW__/ {{print NR + 1; exit 0; }}' "$0")

# Extract archive
tail -n +$PAYLOAD_LINE "$0" | tar -xz -C "$INSTALL_DIR" --strip-components=1

echo "==> Configuring permissions and shortcuts..."
cd "$INSTALL_DIR"
chmod +x *.sh *.py 2>/dev/null || true

# Run setup wizard or installation script
if [ -x "./install.sh" ]; then
    ./install.sh "$@"
else
    ./launch_clipfarm.sh "$@"
fi

exit 0

__PAYLOAD_ARCHIVE_BELOW__
"""

    run_output = RELEASE_DIR / "ClipFarm-Studio-Linux-x86_64.run"
    with open(run_output, "wb") as f_out:
        f_out.write(header.encode("utf-8"))
        with open(temp_tar, "rb") as f_tar:
            shutil.copyfileobj(f_tar, f_out)

    os.chmod(run_output, 0o755)
    size_mb = run_output.stat().st_size / (1024 * 1024)
    log(f"✅ Created Universal Linux installer: {run_output.name} ({size_mb:.2f} MB)")
    return run_output

def build_linux_tarball():
    """Build portable Linux tarball."""
    log("Building portable Linux archive (ClipFarm-Studio-Linux-x86_64.tar.gz)...")
    staging = BUILD_DIR / "tarball"
    assemble_base_files(staging)

    tar_output = RELEASE_DIR / "ClipFarm-Studio-Linux-x86_64.tar.gz"
    with tarfile.open(tar_output, "w:gz") as tar:
        tar.add(staging, arcname="ClipFarm-Studio")

    size_mb = tar_output.stat().st_size / (1024 * 1024)
    log(f"✅ Created Linux tarball: {tar_output.name} ({size_mb:.2f} MB)")
    return tar_output

def build_windows_zip():
    """Build portable Windows package with 1-click batch launcher."""
    log("Building Windows standalone package (ClipFarm-Studio-Windows-x64.zip)...")
    staging = BUILD_DIR / "windows"
    assemble_base_files(staging)

    zip_output = RELEASE_DIR / "ClipFarm-Studio-Windows-x64.zip"
    with zipfile.ZipFile(zip_output, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(staging):
            for file in files:
                p = Path(root) / file
                rel = p.relative_to(staging)
                zipf.write(p, arcname=f"ClipFarm-Studio/{rel}")

    size_mb = zip_output.stat().st_size / (1024 * 1024)
    log(f"✅ Created Windows package: {zip_output.name} ({size_mb:.2f} MB)")
    return zip_output

def build_windows_exe():
    """Build native Windows ClipFarm-Studio-Setup.exe installer via NSIS."""
    log("Building Windows .exe setup installer (ClipFarm-Studio-Setup.exe)...")
    staging_dir = BUILD_DIR / "windows_exe_staging"
    assemble_base_files(staging_dir)

    makensis = PROJECT_ROOT / "build" / "tools" / "nsis-3.10" / "makensis.exe"
    nsi_script = PROJECT_ROOT / "scripts" / "installer.nsi"
    icon_file = PROJECT_ROOT / "app_icon.ico"
    out_exe = RELEASE_DIR / "ClipFarm-Studio-Setup.exe"

    if makensis.exists() and shutil.which("wine"):
        try:
            def to_wine(p: Path) -> str:
                res = subprocess.run(["winepath", "-w", str(p)], capture_output=True, text=True, check=True)
                return res.stdout.strip()

            w_out = to_wine(out_exe)
            w_icon = to_wine(icon_file)
            w_stage = to_wine(staging_dir)
            w_script = to_wine(nsi_script)

            subprocess.run([
                "wine",
                str(makensis),
                f"/DOUT_EXE={w_out}",
                f"/DAPP_VERSION={VERSION}",
                f"/DAPP_ICON={w_icon}",
                f"/DSTAGING_DIR={w_stage}",
                w_script
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            size_mb = out_exe.stat().st_size / (1024 * 1024)
            log(f"✅ Created Windows installer: {out_exe.name} ({size_mb:.2f} MB)")
            return out_exe
        except Exception as e:
            log(f"Notice: Wine makensis execution: {e}")
    return None

def build_macos_zip():
    """Build portable macOS package with clickable .command launcher."""
    log("Building macOS standalone package (ClipFarm-Studio-macOS.zip)...")
    staging = BUILD_DIR / "macos"
    assemble_base_files(staging)

    zip_output = RELEASE_DIR / "ClipFarm-Studio-macOS.zip"
    with zipfile.ZipFile(zip_output, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(staging):
            for file in files:
                p = Path(root) / file
                rel = p.relative_to(staging)
                zipf.write(p, arcname=f"ClipFarm-Studio/{rel}")

    size_mb = zip_output.stat().st_size / (1024 * 1024)
    log(f"✅ Created macOS package: {zip_output.name} ({size_mb:.2f} MB)")
    return zip_output

def generate_downloads_page(artifacts: list):
    """Generate modern HTML and Markdown download manifests for websites."""
    md_path = RELEASE_DIR / "DOWNLOADS.md"
    html_path = RELEASE_DIR / "index.html"

    # Markdown manifest
    md_lines = [
        f"# ClipFarm Studio v{VERSION} - Official Downloads",
        "",
        "High-efficiency AI Short-Form Video Processing & Clipping Native Desktop Software.",
        "",
        "## Available Downloads",
        "",
        "| Platform | Package Format | File Name | Size | Recommended For |",
        "| :--- | :--- | :--- | :--- | :--- |"
    ]

    for item in artifacts:
        md_lines.append(f"| **{item['platform']}** | `{item['format']}` | [{item['name']}](./{item['name']}) | {item['size']} | {item['rec']} |")

    md_lines.extend([
        "",
        "### Quick Installation Guide",
        "",
        "#### 🐧 Ubuntu / Debian Linux (.deb)",
        "```bash",
        "# Double-click the .deb in file manager, or run:",
        f"sudo dpkg -i clipfarm_{VERSION}_amd64.deb",
        "```",
        "",
        "#### 🐧 Universal Linux (.run)",
        "```bash",
        "chmod +x ClipFarm-Studio-Linux-x86_64.run",
        "./ClipFarm-Studio-Linux-x86_64.run",
        "```",
        "",
        "#### 🪟 Windows (.zip)",
        "1. Extract `ClipFarm-Studio-Windows-x64.zip`.",
        "2. Double-click `Install_ClipFarm.bat` (Setup Wizard) or `Launch_ClipFarm.bat`.",
        "",
        "#### 🍏 macOS (.zip)",
        "1. Extract `ClipFarm-Studio-macOS.zip`.",
        "2. Double-click `Install_ClipFarm.command` or `Launch_ClipFarm.command`.",
        ""
    ])

    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    # Modern HTML Download Page with Cards and Buttons
    html_cards = ""
    for item in artifacts:
        btn_class = "btn-primary" if item.get("featured") else "btn-secondary"
        html_cards += f"""
        <div class="card {'featured' if item.get('featured') else ''}">
            <div class="card-header">
                <span class="platform-icon">{item['icon']}</span>
                <div>
                    <h3>{item['platform']}</h3>
                    <span class="badge">{item['format']}</span>
                </div>
            </div>
            <p class="desc">{item['rec']}</p>
            <div class="file-info">
                <span>{item['size']}</span>
                <span class="sep">•</span>
                <span class="ver">v{VERSION}</span>
            </div>
            <a href="{item['name']}" class="btn {btn_class}" download>
                Download {item['format']}
            </a>
        </div>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Download ClipFarm Studio v{VERSION}</title>
    <style>
        :root {{
            --bg: #0B0E14;
            --card-bg: #121722;
            --card-border: #1E2638;
            --text-main: #F8FAFC;
            --text-muted: #94A3B8;
            --accent: #2563EB;
            --accent-glow: #3B82F6;
            --green: #10B981;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
        body {{ background-color: var(--bg); color: var(--text-main); min-height: 100vh; padding: 48px 24px; display: flex; flex-direction: column; align-items: center; }}
        .header {{ text-align: center; max-width: 680px; margin-bottom: 48px; }}
        .header h1 {{ font-size: 38px; font-weight: 800; letter-spacing: -1px; margin-bottom: 12px; }}
        .header h1 span {{ background: linear-gradient(135deg, #60A5FA, #2563EB); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
        .header p {{ color: var(--text-muted); font-size: 16px; line-height: 1.5; }}
        .cards-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 24px; width: 100%; max-width: 1080px; margin-bottom: 48px; }}
        .card {{ background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 14px; padding: 24px; display: flex; flex-direction: column; transition: transform 0.2s, border-color 0.2s; }}
        .card:hover {{ transform: translateY(-3px); border-color: var(--accent-glow); }}
        .card.featured {{ border-color: var(--accent-glow); box-shadow: 0 0 24px rgba(59, 130, 246, 0.15); }}
        .card-header {{ display: flex; align-items: center; gap: 14px; margin-bottom: 14px; }}
        .platform-icon {{ font-size: 32px; }}
        .card-header h3 {{ font-size: 18px; font-weight: 700; }}
        .badge {{ font-size: 11px; font-weight: 700; color: #38BDF8; background: #0F2038; padding: 3px 8px; border-radius: 6px; display: inline-block; margin-top: 2px; }}
        .desc {{ font-size: 13px; color: var(--text-muted); line-height: 1.5; margin-bottom: 20px; flex-grow: 1; }}
        .file-info {{ display: flex; align-items: center; gap: 8px; font-size: 12px; color: #64748B; margin-bottom: 16px; font-weight: 600; }}
        .btn {{ display: block; text-align: center; text-decoration: none; padding: 12px; border-radius: 8px; font-weight: 700; font-size: 14px; transition: background 0.2s; }}
        .btn-primary {{ background: linear-gradient(135deg, #2563EB, #3B82F6); color: white; }}
        .btn-primary:hover {{ background: linear-gradient(135deg, #1D4ED8, #2563EB); }}
        .btn-secondary {{ background: #1B2232; color: #CBD5E1; border: 1px solid #2B364E; }}
        .btn-secondary:hover {{ background: #232C40; color: white; }}
        .footer {{ text-align: center; color: #475569; font-size: 13px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Download <span>ClipFarm Studio</span></h1>
        <p>AI Short-Form Video Clipping & Studio Desktop Application. 100% standalone, hardware-accelerated, and private on your machine.</p>
    </div>

    <div class="cards-grid">
        {html_cards}
    </div>

    <div class="footer">
        <p>ClipFarm Studio v{VERSION} • Standalone Native Desktop Edition</p>
    </div>
</body>
</html>"""

    html_path.write_text(html_content, encoding="utf-8")
    log("✅ Generated release manifests: DOWNLOADS.md and index.html")

def main():
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    ensure_frontend_built()

    artifacts = []

    # 1. Ubuntu / Debian .deb
    deb_file = build_ubuntu_deb()
    artifacts.append({
        "platform": "Ubuntu / Debian",
        "format": ".deb",
        "name": deb_file.name,
        "size": f"{deb_file.stat().st_size / (1024*1024):.1f} MB",
        "rec": "Official 1-click install for Ubuntu, Debian, Linux Mint, Pop!_OS",
        "icon": "🐧",
        "featured": True
    })

    # 2. Universal Linux .run Installer
    run_file = build_linux_run_installer()
    artifacts.append({
        "platform": "Universal Linux",
        "format": ".run Installer",
        "name": run_file.name,
        "size": f"{run_file.stat().st_size / (1024*1024):.1f} MB",
        "rec": "Self-extracting installer for Fedora, Arch, openSUSE, etc.",
        "icon": "🐧",
        "featured": False
    })

    # 3. Portable Linux Tarball
    tar_file = build_linux_tarball()
    artifacts.append({
        "platform": "Linux (Portable)",
        "format": ".tar.gz",
        "name": tar_file.name,
        "size": f"{tar_file.stat().st_size / (1024*1024):.1f} MB",
        "rec": "Portable archive with zero installation required",
        "icon": "📦",
        "featured": False
    })

    # 4. Windows .exe Setup Installer
    win_exe = build_windows_exe()
    if win_exe and win_exe.exists():
        artifacts.append({
            "platform": "Windows 10 / 11",
            "format": ".exe Installer",
            "name": win_exe.name,
            "size": f"{win_exe.stat().st_size / (1024*1024):.1f} MB",
            "rec": "Official 1-Click Setup Wizard for 64-bit Windows",
            "icon": "🪟",
            "featured": True
        })

    # 5. Windows Standalone Zip Package
    win_zip = build_windows_zip()
    artifacts.append({
        "platform": "Windows (Portable)",
        "format": ".zip Package",
        "name": win_zip.name,
        "size": f"{win_zip.stat().st_size / (1024*1024):.1f} MB",
        "rec": "Setup Wizard (.bat) & 1-Click Launch for 64-bit Windows",
        "icon": "🪟",
        "featured": False
    })

    # 5. macOS Standalone Package
    mac_zip = build_macos_zip()
    artifacts.append({
        "platform": "macOS",
        "format": ".zip Package",
        "name": mac_zip.name,
        "size": f"{mac_zip.stat().st_size / (1024*1024):.1f} MB",
        "rec": "Setup Wizard (.command) & 1-Click Launch for macOS",
        "icon": "🍏",
        "featured": True
    })

    generate_downloads_page(artifacts)

    print("\n" + "=" * 64)
    print(f"🎉 ALL RELEASE PACKAGES CREATED IN: {RELEASE_DIR}")
    for item in artifacts:
        print(f"  - [{item['platform']:<16}] {item['name']:<42} ({item['size']})")
    print("=" * 64)

if __name__ == "__main__":
    main()
