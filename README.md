# 🎬 ClipFarm Studio

<div align="center">

**AI-Powered Short-Form Video Studio: Turn long-form podcasts, interviews, and streams into high-engagement 9:16 vertical clips with smart face tracking, karaoke subtitles, and 100% offline local AI.**

[![Python](https://img.shields.io/badge/Python-3.10+-green?style=flat&logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-Latest-red?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18+-blue?style=flat&logo=react)](https://reactjs.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-blue?style=flat&logo=typescript)](https://www.typescriptlang.org)
[![Tauri](https://img.shields.io/badge/Tauri-2.0-24C8D5?style=flat&logo=tauri)](https://tauri.app)
[![Ollama Ready](https://img.shields.io/badge/Local_LLM-Ollama_Ready-22c55e?style=flat&logo=ollama)](https://ollama.com)
[![Support on Ko-fi](https://img.shields.io/badge/Ko--fi-Support_Development-FF5E5B?style=flat&logo=ko-fi&logoColor=white)](https://ko-fi.com/santima)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[Features](#-key-features) • [Supported AI Engines](#-universal-ai-engine-support) • [Quick Start](#-quick-start) • [Support](#-support-the-project) • [Attribution](#-acknowledgments--prior-art)

</div>

---

## 🎯 Overview

**ClipFarm** is an open-source, full-stack video clipping application designed for content creators, agencies, and podcasters. It automates the entire short-form production pipeline:
1. **Ingest** long-form video files, YouTube links, or streams.
2. **Transcribe** dialogue with high-speed local Whisper speech recognition.
3. **Analyze** natural highlights, calculate viral scores, and generate punchy social hooks using any local or cloud LLM.
4. **Smart Frame** widescreen footage into vertical 9:16 videos with real-time OpenCV neural face tracking.
5. **Burn** dynamic word-level karaoke animated subtitles, custom badges, and background audio.
6. **Organize** smart collections ready for export to TikTok, Instagram Reels, and YouTube Shorts.

---

## ✨ Key Features

- 🏠 **100% Offline Local AI (Zero API Cost)**: Native one-click support for **Ollama** and **LM Studio**. Run models like `llama3.2`, `qwen2.5`, `mistral`, and `deepseek-r1` on your own machine with zero data sent to third-party servers.
- 🌐 **Universal Cloud LLM Support**: Connect OpenAI, Anthropic Claude, DeepSeek, Groq, OpenRouter, Google Gemini, or Alibaba DashScope. Includes dynamic 1-click model auto-discovery via `/v1/models`.
- 📱 **Smart 9:16 Framing & Face Tracking**: Automatically detects speaker faces using neural vision (`yunet.onnx`) and dynamically centers crops so subjects are never cut off.
- 🎨 **Dynamic Styled Subtitles**: Word-level karaoke highlighting (ASS/SRT), customizable font colors, emojis, animated hook headers, and auto-ducking background music tracks.
- 💼 **Creator Campaigns & Monetization**: Parse sponsor briefs, auto-detect brand mentions, and stitch campaign call-to-actions directly into the video flow.
- ⚡ **Real-Time Task Queue**: Asynchronous processing queue with live stage-by-stage WebSocket progress updates and token tracking.
- 🖥️ **Cross-Platform**: Run as a standalone desktop app powered by Tauri or as a browser-based web application with Docker.

---

## 🤖 Universal AI Engine Support

ClipFarm works with virtually every modern LLM inference engine. Configure your provider in the **Settings** page:

| Provider | Type | Default Endpoint | Popular Models |
| :--- | :--- | :--- | :--- |
| **Ollama** | Local / Free | `http://localhost:11434/v1` | `llama3.2`, `qwen2.5:7b`, `deepseek-r1:8b`, `mistral:7b` |
| **LM Studio** | Local / Free | `http://localhost:1234/v1` | Any local GGUF model loaded in LM Studio |
| **DeepSeek Direct** | Cloud | `https://api.deepseek.com/v1` | `deepseek-chat` (V3), `deepseek-reasoner` (R1) |
| **Anthropic Claude** | Cloud | `https://api.anthropic.com/v1` | `claude-3-5-sonnet-20241022`, `claude-3-5-haiku-20241022` |
| **Groq** | Cloud / Ultra-Fast | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile`, `qwen-2.5-32b` |
| **OpenRouter** | Cloud / Gateway | `https://openrouter.ai/api/v1` | Access 200+ models with a single API key |
| **OpenAI** | Cloud | `https://api.openai.com/v1` | `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo` |
| **Google Gemini** | Cloud | Google GenAI SDK | `gemini-2.0-flash`, `gemini-1.5-pro` |
| **Alibaba Qwen** | Cloud | DashScope Compatible | `qwen-max`, `qwen-plus`, `qwen-turbo` |
| **SiliconFlow** | Cloud | `https://api.siliconflow.cn/v1` | `Qwen/Qwen2.5-7B-Instruct`, `DeepSeek-V2.5` |
| **Custom OpenAI-Compatible** | Any | Your custom base URL | LocalAI, vLLM, SGLang, Together AI, Mistral |

> 💡 **Dynamic Auto-Discovery**: In the Settings tab, click **"Fetch available models from endpoint"** to automatically query your local Ollama/LM Studio or custom server and populate selectable models.

---

## 💻 Hardware Guide

| Mode | Minimum Spec | Recommended Spec | Cost & Privacy |
| :--- | :--- | :--- | :--- |
| **Cloud AI + Whisper Base** | 8 GB RAM, Any modern CPU | 8–16 GB RAM, Dual-core CPU | Cents per hour / Cloud keys |
| **Local AI (Ollama 3B) + Whisper Small** | 16 GB RAM, 4-core CPU | Apple Silicon M1/M2/M3 or 6GB+ NVIDIA GPU | **100% Free & Private** |
| **Heavy Local (Whisper Large + 7B/14B LLM)** | 16–32 GB RAM | RTX 3060/4060 (8GB+ VRAM) or Apple M-Pro | **100% Free & Studio Quality** |

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.10+**
- **Node.js 18+** & npm
- **FFmpeg** & **FFprobe** installed and accessible in `PATH`

### 1. Clone the Repository
```bash
git clone https://github.com/santimacorp-droid/ClipFarm.git
cd ClipFarm
```

### 2. Configure Environment
```bash
cp .env.example .env
```
*(By default, `.env` is configured for local Ollama. If running cloud models, enter your respective API key).*

### 3. Quick Launch (Automated Script)
```bash
chmod +x start_clipfarm.sh stop_clipfarm.sh run_all.sh
./start_clipfarm.sh
```
This script initializes the Python virtual environment, installs requirements, sets up the frontend, and launches:
- **Backend API**: `http://localhost:8001`
- **Frontend Studio UI**: `http://localhost:3001`

### 4. Running with Docker
```bash
docker compose up -d
```

---

## 📁 Repository Architecture

```
ClipFarm/
├── backend/                  # FastAPI Application
│   ├── api/v1/               # REST API Endpoints (Campaigns, Settings, Subtitles, Watermarks)
│   ├── core/                 # LLM Providers, Model Router, Token Tracking, Config
│   ├── models/               # Database ORM Models & Neural Weights (yunet.onnx)
│   ├── pipeline/             # Multi-stage video analysis & clipping pipeline
│   ├── services/             # Campaign & Video business logic
│   └── utils/                # Smart framing, caption styling, audio enhancer, silence detector
├── frontend/                 # React 18 + TypeScript + Ant Design
│   ├── src/
│   │   ├── components/       # Video upload, watermark editor, caption modal, compliance
│   │   ├── pages/            # Home, Settings, Campaigns, Subtitle Editor
│   │   └── services/         # Axios API clients & WebSocket listeners
├── src-tauri/                # Tauri 2.0 Rust Desktop Application Wrapper
├── docker-compose.yml        # Multi-container orchestration
└── .env.example              # Environment configuration template
```

---

## ☕ Support the Project

If ClipFarm saves you hours of video editing, powers your creator workflow, or helps grow your channels, please consider supporting ongoing development:

<div align="center">

[![Buy Me a Coffee at ko-fi.com](https://img.shields.io/badge/Support_on-Ko--fi-FF5E5B?style=for-the-badge&logo=ko-fi&logoColor=white)](https://ko-fi.com/santima)

👉 **[Support ClipFarm on Ko-fi (ko-fi.com/santima)](https://ko-fi.com/santima)**

</div>

Your support directly helps fund:
- 🧪 Continuous testing, bug fixes, and library upgrades
- 🧠 Integration of new open-source models (ASR, LLM, face-tracking)
- 🚀 Community feature requests and documentation

---

## 📞 Community & Contributing

- **Issues**: Found a bug or need an improvement? Open an issue in [GitHub Issues](https://github.com/santimacorp-droid/ClipFarm/issues).
- **Discussions**: Have an idea or want to share workflows? Join [GitHub Discussions](https://github.com/santimacorp-droid/ClipFarm/discussions).
- **Contributing**: Contributions are welcome! Check out [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

---

## 🙏 Acknowledgments & Prior Art

ClipFarm adapts foundational clipping and task workflow patterns from the open-source [autoclip](https://github.com/zhouxiaoka/autoclip) project under the **MIT License**.

ClipFarm heavily redesigns and expands upon this foundation with:
- Dedicated Creator Campaigns & Affiliate Stitching
- Dynamic OpenCV face-tracking 9:16 smart framing (`yunet.onnx`)
- Word-level animated karaoke styling & hook title overlays
- Full universal local/cloud LLM provider matrix (Ollama, LM Studio, Claude, DeepSeek, Groq, OpenRouter)

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
