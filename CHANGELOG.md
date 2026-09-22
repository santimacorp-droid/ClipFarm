# ChangelogAutoClipAll major changes to the project. [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/), 
Project follows [Semantic versioning](https://semver.org/lang/zh-CN/). 

## [Not published]

## [1.2.0] - 2026-06-03

> Integrated product analytics, for后续 account functionality / Building data foundation for commercialization. 

### Added - integrated PostHog Anonymous product analytics: covered install/Startup/Update, import assets, output creation, failed workflow, settings API key Event, each event automatically carries app version information/System/Architecture-wide global attributes「Privacy and data」Toggle, can be disabled at any time to disable anonymous usage statistics (disabled immediately stops reporting, effective after restart) `docs/ANALYTICS.md` Updated privacy policies (Chinese/English) `docs/PRIVACY.md` / `docs/PRIVACY.en.md`
- Add video title edit featureBMultiaccount managementDockerDeployment support - addedDockerManagement script

### Under development
- BSite upload feature (to be released in the next version))

## [1.1.0] - 2026-05-31

> Let/make... macOS Desktop client truly installable, usable, and capable of creating outputs. 

### Added
- 🖥️ Desktop client zero-dependency installer: portable included Python Runtime + Static ffmpeg/ffprobe, User does not need to preinstall Python/ffmpeg
- 🗣️ Local subtitle transcribing (install as needed): No subtitles video in「Settings → Speech transcription」One-click install faster-whisper And self-select models

### Fix vendor chunk Loading sequence causing error React Not mounted)「Loading...」(Runtime missing pytz Dependency issues caused by interface 500)
- Fix import/On retry「Retry failed / Started retrying」Prompt pop-up loop 0%「Initializing」(Desktop mode pipeline changed to local execution, no longer dependent on Redis)
- Fixed video processing failure after device switch (built-in) ffmpeg Change to static self-contained version and correctly integrate backend)

### Improved
- AI Provider Gemini Migrated to official new version `google-genai` SDK
- CI Unified desktop build to one validated process(python-build-standalone)
- Repository cleanup: remove numerous historical scripts and one-time documentation, organize project structure

## [1.0.0] - 2024-01-15

### Added
- 🎬 SupportYouTubeVideo download
- 🎬 SupportBSite video download
- 🎬 Supported local file upload
- 🤖 AIIntelligent video analysis
- ✂️ Automatic video segmentation
- 📚 Intelligent collection generation
- 🎨 ModernizationWebInterface
- 🚀 Asynchronous task processing
- 📊 Real-time progress monitoring
- 🔐 BSite account management
- 📱 Responsive design
- 🛠️ One-click startup script

### Technical features
- FastAPIBackend framework
- React + TypeScriptFrontend
- CeleryAsynchronous task queue
- RedisMessage broker
- SQLiteDatabase
- WebSocketReal-time communication - Tongyi QianwenAIIntegration

## [0.9.0] - 2024-01-01

### AddAPIInterface
- AIAnalysis service

### Technology stack
- Python 3.8+
- React 18
- FastAPI
- Celery
- Redis
- SQLite

---

## Version notes

### Version number format (SemVer): 

- **Major version number**: IncompatibleAPIModify
- **Minor version number**: Functional enhancements with backward compatibility
- **Revision number**: Backward compatibility bug fixes

### Change type

- **Added**: New feature
- **Improved**: Improved existing functionality
- **Fix/Resolved**: BugFix/Resolved
- **Remove**: Removed features
- **Security**: Security-related fixes

### Link

- [Unreleased]: https://github.com/your-username/autoclip/compare/v1.0.0...HEAD
- [1.0.0]: https://github.com/your-username/autoclip/releases/tag/v1.0.0
- [0.9.0]: https://github.com/your-username/autoclip/releases/tag/v0.9.0
