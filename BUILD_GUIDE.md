# 🚀 AutoClip Desktop Build instructions**one**Packaging route: python-build-standalone(PBS). It makes portable Python Command line directly run - Command line directly run ffmpeg/ffprobe Bundled completely `.app`, User machine**No prior installation required Python or ffmpeg**. 

> Historical PyInstaller / prepare_resources Manual trigger: repository page 6+ count CI Workflow never successfully produced a usable package, all removed. 

## Local build(macOS Apple Silicon)

```bash
./scripts/build_macos_arm.sh
```

product: 
```
src-tauri/target/release/bundle/macos/
├── AutoClip Desktop.app                    # app package(~550M)
└── AutoClip Desktop_1.0.0_aarch64.dmg      # DMG installer package(~260M)
```

Route(s) and corresponding [`scripts/README.md`](scripts/README.md). 

### Prerequisite dependencies

| tool | version | description |
|------|------|------|
| Node.js | 18+ | Frontend build |
| Rust | stable | with `aarch64-apple-darwin` target |
| cargo-tauri | 2.x | `cargo install tauri-cli` |

system **unnecessary** pre-installed Python / ffmpeg —— Script自with便携版 (first build will download and cache to) - Script includes portable version (first build will download and cache to) `build/`). 

## CI / release(GitHub Actions)

`.github/workflows/desktop-build.yml` Running on the same `build_macos_arm.sh`: 

```bash
# Only → Actions → "Desktop Build (macOS arm64)" → Run workflow

# or press tag Trigger, and automatically copies DMG attach to GitHub Release: 
git tag v1.0.0
git push origin v1.0.0
```

## Installation and first run

DMG is ad-hoc Signing (not performed) Apple Notarized), so: 

1. double click DMG, remove `AutoClip Desktop` drag into Applications
2. **First time open right-click app → select「open」** To circumvent Gatekeeper
3. Backend will automatically start and `~/Library/Application Support/AutoClip` Create data directory

## Troubleshooting app See backend output: 
```bash
'/Applications/AutoClip Desktop.app/Contents/MacOS/autoclip-desktop'
```
Should see `Backend started on port: XXXXX` and `Application startup complete`. 

| symptoms | troubleshoot |
|------|------|
| `ModuleNotFoundError: No module named 'X'` | remove `X` add to `requirements.txt` Rebuilding (dependency checks during build should have already caught this, normally shouldn't happen))|
| Black screen window | Front end not mounted, see WebView Console; Usually packaging/Resource issues |
| Video processing failed | confirm `Contents/Resources/resources/ffmpeg/{ffmpeg,ffprobe}` Exists and is executable |
| Build failed want to redo | `rm -rf src-tauri/target build/pbs-cache build/ffmpeg-cache` Runtime, backend source code, static)|

## Known limitations Apple Silicon (arm64), none available Intel / Windows / Linux package
- ad-hoc Signed, unsigned, first time requires right-click to open
