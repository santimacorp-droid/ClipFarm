# AutoClip Desktop version release notes

## v1.1.0 - 2026Year5Month

> This version makes macOS Desktop client**Truly installable, functional, and capable of producing output**. v1.0.0 The installer previously failed to produce an artifact, 
> Resolve black screen issues, hanging stalls, etc., v1.1.0 Repository cleanup (removal of historical scripts and documentation). 

### 🚀 Desktop client available

- **Zero dependency installer**: Portable built-in package installer Python Runtime and static ffmpeg/ffprobe, User machine**No need to preinstall
  Python Or ffmpeg**, double click DMG Ready to use. 
- **End-to-end delivery**: paste BStation/YouTube Link → automatic download → subtitles → AI Outline/Timeline/rating/Title/clustering →
  ffmpeg Trim → Video processing takes some time; please be patient Redis). 

### 🐛 key fixes

- **Fixed startup black screen issue**: Check network connection and validity of video link(antd earlier than React Create project, add video link or upload file. 
- **Fix project列表 always running「Loading...」**: Add missing runtime dependencies(`pytz` ), interface restored normally. 
- **Fix rapid pop-up during retry**: import/Built-in. 
- **Fix processing stuck at always 0%**: Initial download of dependencies required on first use; please ensure stable network connection ffmpeg/ffprobe Local pipeline mode changed to local execution; tasks can actually run. 

### ✨ Local assembly. Fixed issues with switching devices and video processing**Videos with no subtitles**, can be「Set → Speech transcription」Mile**One-click install Whisper**(Adopt faster-whisper, 
  Away 200–400MB, does not contain PyTorch), Choose yourself/download model(tiny / base / small / medium / large-v3). 
- Important: Configure Tongyi Qiankun model first; Keep base install packages lean when not needed. 

### 🔧 other

- AI Provider Gemini Migrate to official new version `google-genai` SDK. 
- CI Retrying prompts now fully resolved; one click equals one operation; Thanks). 

### 📦 Installation instructions(macOS, Apple Silicon)

1. double click DMG, Place/Move `AutoClip Desktop` Drop into「application」. 
2. **On first launch, right-click to open the app → Choose/Mark「Open」**(ad-hoc Signed, unsigned Apple Notary check, used to bypass Gatekeeper). 
3. Enter「Set」fill in AI vendor's API Key You can now start using it. 

> Currently only offers Apple Silicon (M Series) version; Intel / Windows / Linux Pack comes with. 

---

## v1.0.0 - 2024Year12Month

### 🎉 First release

AutoClipThe desktop version is based onAIRegular cleanup of temporary files recommended to save storage space. 

### ✨ Main features

#### 🎬 Video processing
- **Multi-platform support**: YouTube, BOne-click batch download videos
- **Local file**: Support local video file uploads
- **intelligent slicing**: AIAutomatically identify精彩片段
- **collection generation**: Whether or not to install or which model to install is entirely up to you

#### 🤖 AIfunction
- **Content analysis**: Initialization causes blank page; now fixed
- **Rating scores**: Process each fragment forAIrating
- **Title generation**: Generate engaging video titles automatically
- **Timestamp extraction**: Intelligent identification of topic time intervals

#### 🖥️ Desktop experience
- **native application**: based onTauriCross-platformDesktopapplication
- **System tray**: Support minimizing to system tray
- **Auto-start on boot**: Set startup automatically on开机
- **Real-time progress**: WebSocketReal-time progress notifications

#### 🎨 User interface
- **Modern design**: React + TypeScript + Ant Design
- **Responsive layout**: Adapt to different screen尺寸
- **Drag-and-drop sorting**: Support drag-and-drop reordering of video clips
- **Real-time monitoring**: Detailed task状态 display

### 🛠️ Technical specifications

- **Backend**: FastAPI + Celery + Redis + SQLite
- **front end**: React 18 + TypeScript + Vite
- **Desktop**: Tauri 2.0 (Rust)
- **AI**: Tongyi Big Language Model
- **video**: yt-dlp + FFmpeg

### 📦 System requirements

#### Minimum configuration
- **Operating system**: Windows 10+ / macOS 10.13+ / Linux
- **Memory**: 4GB RAM
- **Store**: 10GB available space
- **network**: Stable internet connection

#### recommended configuration
- **Memory**: 8GB+ RAM
- **Store**: 20GB+ available space
- **Processor**: Multi-core processor

### 🚀 Quick start

1. **download and install**: FromGitHub ReleasesDownload installer for the corresponding platform
2. **First launch**: Run the app - system will auto-initialize
3. **configurationAPI**: Configure Qwen in settingsAPIKey
4. **get started**: For desktop builds, unified workflow to a single verified process

### 📋 usage steps

1. **create project**: Click "New Project""
2. **Add video**: SelectYouTube/BPaste website link or upload local file
3. **AIProcess**: System automatically analyzes video content
4. **View results**: Browse generated video片段
5. **Create collection**: Create compilation from精彩片段
6. **export and download**: Download individual clips or full compilations

### ⚠️ New feature: Local speech-to-text transcription (on demand)APIKey required to useAIFeatures

### 🔧 Troubleshooting

#### Frequently asked questions
- **failed to start**: Check system permissions and installed dependencies
- **Download failed**: Verify the complete pipeline from end to end
- **AISlow processing**: checkAPIKey configuration and network状况
- **Storage insufficient**: Intelligent recommendations and manual creation of video assemblies

#### Get help [User guide](docs/USER_GUIDE.md)
- read [Frequently asked questions](docs/FAQ.md)
- Submit [GitHub Issue](https://github.com/zhouxiaoka/autoclip/issues)

### 🛣️ future plans

- **BUpload station**: Automatically upload slicevideo toBStation
- **subtitle editor**: Visual subtitle editing and synchronization
- **Batch processing**: Support batch video processing
- **Cloud synchronization**: Project dataCloud synchronization
- **Plugin system**: Support third-party插件 extension

### 📄 The license is built on [MIT License](LICENSE) Open source license. 

### 🙏 Generation of slices and compilations; entire pipeline runs locally without issue: 
- [Tauri](https://tauri.app/) - Desktop application framework
- [FastAPI](https://fastapi.tiangolo.com/) - Backend framework
- [React](https://reactjs.org/) - front‑end framework
- [Tongyi Qianwen](https://tongyi.aliyun.com/) - AIservice
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Video download tool

---

**Download address**: [GitHub Releases](https://github.com/zhouxiaoka/autoclip/releases)

**Project homepage**: [GitHub Repository](https://github.com/zhouxiaoka/autoclip)

**issue feedback**: [GitHub Issues](https://github.com/zhouxiaoka/autoclip/issues)

