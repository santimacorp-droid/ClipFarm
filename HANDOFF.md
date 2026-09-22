# AutoClip — Project status / Progress / Schedule

> Update: 2026-05-30 · Branch `main`(Leading origin Several commit, Unstarted push)

AutoClip It's a AI Video slice tool: Input BStation/YouTube Links or local videos, automatically recognize highlight clips,. 

---

## I. Architecture & Delivery Form

| layer | Technology | Directory |
|----|------|------|
| Backend | FastAPI + Celery(Desktop mode uses local queue)+ SQLite | `backend/` |
| Frontend | React + TypeScript + Ant Design + Vite | `frontend/` |
| Desktop shell | Tauri 2 + Rust | `src-tauri/` |
| LLM | OpenAI / Gemini(google-genai) / Tongyi Qianwen(dashscope) / Silicon flow | `backend/core/llm_providers.py` |

Three delivery forms: **Docker Deployment**, **Local script launcher**(`start_autoclip.sh`), **Desktop client**(macOS DMG). 
Recent efforts focused on the desktop client. 

---

## II. Current Progress (Completed & Verified)**End-to-end installable and usable**: 

1. **Unified packaging route** —— Cut off historically conflicting PyInstaller / prepare_resources Removed two dead build routes, python-build-standalone(PBS): Portable Python + Backend source code + Static ffmpeg/ffprobe Flush all
   `.app`, User machine zero dependencies. Script: `scripts/build_macos_arm.sh`. 

2. **Fix a series of deployment blocking bugs bug**(All tested and verified): 
   - **ffmpeg Not available**: Previously packaged was homebrew Dynamic version(57 one `/opt/homebrew` Dependencies), switch to static
     arm64 ffmpeg+ffprobe(Zero non-system dependencies), and make Rust Launcher passes through `AUTOCLIP_FFMPEG_PATH`/
     `AUTOCLIP_FFPROBE_PATH` Pointing to built-in binary. 
   - **Black screen**: Vite Place/Put/Turn React/antd Split into two vendor chunk, antd Prior to React Initialized → `createContext`
     Error/Error encountered, React Frontend fix: eliminated manual bundling, ensuring normal rendering. 
   - **Project list keeps spinning**: `/api/v1/projects/` Because of lack `pytz` Report 500. Fill in/Pad/Complete `pytz` Both…and/Together with/Also LLM SDK
     (`openai`/`google-genai`/`dashscope`) Reached/Arrived at `requirements.txt`. 
   - **Dependency drift guardrail**: Build time AST Scan backend import, Missing any one directly fail, Eliminate the "development works, packaging fails" cycle 500". 

3. **CI Standardize** —— 7 Seventeen never-succeeded legacy desktop builds → 1 one `desktop-build.yml`(Ran PBS Script, 
   `v*` tag Auto attached Release). Retain/Keep `ci.yml`(Test/Test mode), `i18n-sync.yml`(Documentation), 
   `nightly-desktop-smoke.yml`(Backend smoke test). 

4. **Repository cleanup** —— Remove about 30 Three obsolete scripts, one nested temporary directory,, 94M Old PyInstaller Backup and so on; 
   `scripts/` Only/Just left/Spare 4 One active script; Rewrite `scripts/README.md` And/With `BUILD_GUIDE.md`. 

5. **Gemini SDK Migrate** —— From discontinued `google-generativeai` Migrated to unified `google-genai`. 

**Product**: `src-tauri/target/release/bundle/macos/AutoClip Desktop_1.0.0_aarch64.dmg`(~260M). 

---

## Three, missed / Not yet verified (by priority))

> Already closed (no longer missed): **Complete slicing workflow**On packaged app End-to-end run-through (sticky) BSite link → Download →
> Subtitles → DashScope Analysis → Score → Title → Trim → Out/Export 5 One slice, 79s Completed); **Video without subtitles**Now available
> in「Set → Speech transcription」On-demand install faster-whisper Automatic transcription (actual installation test results show 214MB, Converted out SRT). 

### Between/Middle
- **Signature/Notarize**: Currently ad-hoc Signature, not done Apple Developer ID Signature + Mandatory first-time user right-click confirmation. 
- **Only/Limit to arm64**: None/Non-existent Intel mac / Windows / Linux Within/Contained by. 
- **Dependency with unsaved version**: `requirements.txt` Most packages lack fixed version numbers, making time-based dependency matching difficult/Cross-machine builds risk divergence. 
- **Slow build**: Each build re-installs all pip Dependency(PBS python Failed/Break `rm -rf` Updated Dockerfile (recreating from scratch). Can cache already-installed runtime. 
- **Gemini Migrated not aligned with real API Verify**: Code and new version google-genai SDK Interface aligned and functional import, But doesn't have
  Gemini key Actually called more than(DashScope Path verified through actual run). 

### low
- **Frontend single bundle ~1.5MB**: After removing splits, it's a large chunk, Desktop side doesn't matter here; if future backend runs, Web May consider lazy loading by route. 
- **Single-step retry `submit_single_step_task`** Still routed through Redis send_task(Main desktop script (no modifications needed for worker),; 
  Entire pipeline of `.delay()` Already by DesktopAwareTask Take over local execution. 

---

## IV. Future Plan (Roadmap))

1. **Official signature and notarization**: Request/Apply Apple Developer ID, Signature + notarize, Remove "right-click open". 
2. **Multiplatform packaging**: Place/Put/Turn `build_macos_arm.sh` of runner / PBS URL / ffmpeg URL / tauri target Parametric, Intel mac, Windows, Linux(PBS And static ffmpeg Each has a corresponding platform version; faster-whisper Cross-platform by nature). 
3. **Dependency lock**: Fixed `requirements.txt` Version (or imported lock Cleaned build artifacts (including package-lock files) to ensure reproducible builds. 
4. **Build acceleration**: Cache PBS python + Installed dependencies to avoid reinstallation on every run. 
5. **Automatic UI Smoke test**: in CI Added an intermediate step to verify that the packaged frontend can mount). 
6. Product towards: BBackend features: deployment, subtitle editing, batch processing, cloud sync (see separate doc) RELEASE_CHECKLIST.md Next plan). 

---

## V. Key Files: `scripts/build_macos_arm.sh`(See description `scripts/README.md`, `BUILD_GUIDE.md`)
- Backend launcher(Rust): `src-tauri/src/backend_manager.rs`
- Desktop backend entry: `backend/desktop_main.py`
- ffmpeg Path resolution: `backend/utils/ffmpeg_utils.py`
- LLM Supplier: `backend/core/llm_providers.py`
- Desktop pipeline local execution: `backend/core/celery_app.py`(DesktopAwareTask), `backend/utils/task_submission_utils.py`
- Whisper Runtime (on-demand install): `backend/services/whisper_runtime.py`, `whisper_model_manager.py`, 
  Frontend `frontend/src/components/SpeechRecognitionConfig.tsx`
- Frontend API Configuration: `frontend/src/utils/apiConfig.ts`
- CI: `.github/workflows/desktop-build.yml`

## VI. Installation (for users)

1. Double click DMG → Drag `AutoClip Desktop` Reached/Arrived at Applications
2. **First right-click application → Open**(ad-hoc Signature, bypassed Gatekeeper)
3. Enter settings page and fill in LLM API key Command-line diagnostics for backend: 
```bash
'/Applications/AutoClip Desktop.app/Contents/MacOS/autoclip-desktop'
# Should see Backend started on port: XXXXX / Application startup complete
```
