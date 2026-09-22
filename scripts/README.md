# scripts/

Build and operations scripts. The desktop client only**one**bundling routes(python-build-standalone, referred to as PBS), 
historical PyInstaller / prepare_resources Routes and scripts removed. 

## script inventory

| script | purpose |
|------|------|
| `build_macos_arm.sh` | **This is the only desktop packaging script**(macOS Apple Silicon). end-to-end output `.app` + `.dmg`.  |
| `verify_desktop.sh` | Backend smoke test: `cargo check` + Start the backend, verify `/health` with `/api/v1/video-categories`. being `nightly-desktop-smoke.yml` invoke.  |
| `monitor_whisper.py` | at run time Whisper Task monitoring moved to the root directory `start_autoclip.sh` / `check_whisper_status.sh` invoke.  |

## Package desktop client(macOS arm64)

```bash
./scripts/build_macos_arm.sh
```

artifact: 
```
src-tauri/target/release/bundle/macos/
├── AutoClip Desktop.app
└── AutoClip Desktop_1.0.0_aarch64.dmg
```

### What does this script do?

1. portable download Python runtime(python-build-standalone, caching in `build/pbs-cache/`)
2. portable using Python install `requirements.txt` all dependencies included
3. **Dependency integrity check**: AST Scan all third-party backends import, Fail the build without any of them 500")
4. rsync Copy backend source code to `src-tauri/resources/backend/`
5. download**static** ffmpeg + ffprobe(arm64, self-contained, zero homebrew Dependencies cached in `build/ffmpeg-cache/`)
6. build front end(`npm ci && npm run build`)
7. `cargo tauri build --bundles app`
8. put `python/`, `backend/`, `ffmpeg/` inject `.app/Contents/Resources/resources/`
9. ad-hoc signature + `hdiutil` manually built DMG

### prerequisite dependencies

- Node.js 18+, Rust(carry `aarch64-apple-darwin` target), cargo-tauri (`cargo install tauri-cli`)
- system **unnecessary** pre-installed Python / ffmpeg —— The script comes with a portable edition

### environment variables

- `PIP_INDEX_URL`: pip Source defaults to Tsinghua Mirror; CI set in there `https://pypi.org/simple`

## CI

`.github/workflows/desktop-build.yml` in `workflow_dispatch` and `v*` tag run on the same
`build_macos_arm.sh`, open tag when DMG attach to GitHub Release. 

> current only macOS arm64. PBS static and ffmpeg against Intel/Windows/Linux Each has a corresponding version, 
> subsequent integration runner, download URL, tauri target Make it parameterized for generalization. 

## Development mode (non-packaged) Tauri Development mode, hot reload: 
```bash
cd src-tauri && cargo tauri dev
```
(front-end :3000 + Backend dynamic port assigned by `backend_manager.rs` pull up)
