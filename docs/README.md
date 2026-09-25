# 📚 ClipFarm Studio — Documentation Center

Welcome to the ClipFarm Studio documentation directory. Here you will find architecture specifications, setup guides, and technical reference manuals for video clipping, ASR speech recognition, and multi-model LLM integration.

---

## 🚀 Getting Started

- **[Quick Start Guide](QUICK_START_GUIDE.md)**: 5-minute setup and quick launch instructions.
- **[User Installation Guide](USER_INSTALLATION_GUIDE.md)**: Detailed platform instructions for Linux, macOS, and Windows.
- **[User Guide](USER_GUIDE.md)**: Complete walkthrough of importing videos, scoring highlights, and burning captions.
- **[Quick Reference](QUICK_REFERENCE.md)**: Cheat sheet for keyboard shortcuts, common commands, and pipeline configurations.

---

## 🧠 AI, Speech & Computer Vision

- **[Multi-LLM Provider Guide](MULTI_LLM_PROVIDER_GUIDE.md)**: Configuring Ollama, LM Studio, DeepSeek, Claude, OpenAI, Groq, Gemini, and custom vLLM endpoints.
- **[Speech Recognition Setup](SPEECH_RECOGNITION_SETUP.md)**: Faster-Whisper GPU/CPU setup, model tiers (`tiny` through `large-v3`), and compute types.
- **[Whisper Subtitle Strategy](WHISPER_SUBTITLE_STRATEGY.md)**: Word-level alignment and anti-hallucination configuration.
- **[Whisper Strategy Implementation](WHISPER_STRATEGY_IMPLEMENTATION.md)**: Technical details on non-overlapping interval calculations.
- **[Optional SRT Upload Guide](OPTIONAL_SRT_UPLOAD_GUIDE.md)**: How to bypass Whisper transcription with external SRT files.

---

## 🏗️ Architecture & Development

- **[System Architecture](SYSTEM_ARCHITECTURE.md)**: Full-stack overview of FastAPI, Celery, Redis, React, and FFmpeg filtergraphs.
- **[Backend Architecture](BACKEND_ARCHITECTURE.md)**: Service modules, database schemas, and background task pipelines.
- **[Developer Guide](DEVELOPER_GUIDE.md)**: Local development environment setup, unit testing, and contributing practices.
- **[Progress System Guide](PROGRESS_SYSTEM_GUIDE.md)**: Real-time WebSocket event dispatching and task status tracking.
- **[Error Handling Guide](ERROR_HANDLING_GUIDE.md)**: Standardized exception hierarchies and fallback strategies.
- **[Analytics Guide](ANALYTICS.md)**: Tracking virality metrics, duration distributions, and export statistics.
- **[Technical Roadmap](TECHNICAL_ROADMAP.md)**: Engineering milestones, planned features, and upcoming capabilities.

---

## 🛡️ Privacy, Support & Troubleshooting

- **[Privacy Policy (English)](PRIVACY.en.md)**: Complete offline privacy and local data handling policies.
- **[Privacy Policy (Bilingual)](PRIVACY.md)**: Privacy documentation and security principles.
- **[FAQ & Troubleshooting](FAQ.md)**: Answers to common questions regarding CUDA, FFmpeg, and model downloads.
- **[YouTube Download Issues](youtube_download_issues.md)**: Troubleshooting yt-dlp rate limits, bot detection, and cookie passing.
- **[Internationalization (i18n)](i18n.md)**: Multi-language support and localization guidelines.

---

<div align="center">
  <sub>Back to main project: <a href="../README.md">ClipFarm Studio README</a></sub>
</div>
