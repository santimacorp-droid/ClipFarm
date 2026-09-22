# 🤝 Contributing to ClipFarm Studio

Thank you for your interest in contributing to **ClipFarm Studio**! ClipFarm is an open-source, community-driven project built for video creators, editors, agencies, and developers.

Whether you are fixing a typo in the documentation, optimizing FFmpeg GPU encoding, adding a new local AI model, or designing a fresh UI component, we are excited to collaborate with you!

---

## 📋 Table of Contents
- [Code of Conduct](#-code-of-conduct)
- [How Can I Contribute?](#-how-can-i-contribute)
- [Development Setup](#-development-setup)
- [Codebase Architecture Walkthrough](#-codebase-architecture-walkthrough)
- [Extending ClipFarm](#-extending-clipfarm)
  - [Adding a New LLM Provider](#adding-a-new-llm-provider)
  - [Adding a New Caption Style](#adding-a-new-caption-style)
- [Branching & Commit Guidelines](#-branching--commit-guidelines)
- [Coding Standards](#-coding-standards)
- [Running Tests](#-running-tests)
- [Submitting a Pull Request](#-submitting-a-pull-request)
- [Support the Project](#-support-the-project)

---

## 📜 Code of Conduct

All contributors, maintainers, and community members are expected to follow our [Code of Conduct](CODE_OF_CONDUCT.md). Please treat everyone with respect, kindness, and empathy.

---

## 💡 How Can I Contribute?

- 🐛 **Fix Bugs**: Browse [GitHub Issues](https://github.com/santimacorp-droid/ClipFarm/issues) with the `bug` tag.
- ✨ **Build Features**: Explore issues tagged `enhancement` or propose new capabilities in [GitHub Discussions](https://github.com/santimacorp-droid/ClipFarm/discussions).
- 🎨 **UI/UX Polish**: Improve accessibility, responsive layouts, or component animations in the React/Tailwind frontend.
- 📚 **Documentation**: Expand setup guides, hardware benchmarks, and troubleshooting tips.
- 🧪 **Testing**: Write unit or integration tests for edge cases in video processing or model parsing.
- ☕ **Sponsorship**: If you cannot contribute code, you can support development via [Ko-fi](https://ko-fi.com/santima).

---

## 🛠️ Development Setup

### 1. Fork & Clone
```bash
# Fork on GitHub, then clone your fork:
git clone https://github.com/santimacorp-droid/ClipFarm.git
cd ClipFarm

# Add upstream repository to keep your local branch synced:
git remote add upstream https://github.com/santimacorp-droid/ClipFarm.git
```

### 2. Environment Setup
```bash
# Create and activate a Python 3.10+ virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install backend Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend && npm install && cd ..

# Copy default environment configuration
cp .env.example .env
```

### 3. Launch Development Servers

You can start all services with a single command:
```bash
chmod +x run_all.sh
./run_all.sh
```

Or launch services in separate terminal windows:
- **Backend API**: `python -m uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload`
- **Celery Worker**: `celery -A backend.core.celery_app worker --loglevel=info -Q processing,upload,notification,maintenance`
- **Frontend Dev Server**: `cd frontend && npm run dev`

Access the UI at [http://localhost:3001](http://localhost:3001) and API docs at [http://localhost:8001/docs](http://localhost:8001/docs).

---

## 🏛️ Codebase Architecture Walkthrough

```
ClipFarm/
├── backend/
│   ├── api/v1/                   # REST API routes (campaigns, settings, projects, health)
│   ├── core/                     # LLM providers, model router, Celery app, database engine
│   ├── models/                   # SQLAlchemy database entities & YuNet neural weights
│   ├── pipeline/                 # 6-step video clipping pipeline
│   │   ├── step1_download.py     # yt-dlp video ingestion
│   │   ├── step2_transcribe.py   # Faster-Whisper ASR & word timestamps
│   │   ├── step3_outline.py      # LLM content outline extraction
│   │   ├── step4_moments.py      # Highlight selection & virality scoring
│   │   ├── step5_title.py        # Social title & hook generation
│   │   └── step6_video.py        # FFmpeg cutting, smart framing, and subtitle burning
│   ├── services/                 # Video processing and campaign orchestration logic
│   └── utils/                    # Smart framing (YuNet), karaoke subtitles, audio enhancer
├── frontend/
│   ├── src/
│   │   ├── components/           # UI components (Header, UploadModal, WatermarkManager)
│   │   ├── pages/                # Views (HomePage, SettingsPage, CampaignsPage)
│   │   ├── services/             # Axios REST clients and WebSocket adapters
│   │   └── context/              # Theme and global state providers
└── src-tauri/                    # Rust Tauri 2.0 desktop shell
```

---

## 🔌 Extending ClipFarm

### Adding a New LLM Provider

ClipFarm uses a modular provider factory pattern in `backend/core/llm_providers.py`:

1. **Add to `ProviderType`**:
   ```python
   class ProviderType(str, Enum):
       MY_PROVIDER = "my_provider"
   ```
2. **Implement `LLMProvider`**:
   ```python
   class MyProvider(LLMProvider):
       def call(self, prompt: str, **kwargs) -> str:
           # Call your provider's API
           ...
       def get_available_models(self) -> List[str]:
           return ["model-1", "model-2"]
   ```
3. **Register in `LLMProviderFactory`**:
   ```python
   LLMProviderFactory._providers[ProviderType.MY_PROVIDER] = MyProvider
   ```
4. **Expose in Settings UI** (`frontend/src/pages/SettingsPage.tsx`) under `providerConfig`.

### Adding a New Caption Style

Subtitles are generated in `backend/utils/caption_styles.py`:
- Each style defines font family, primary color, highlight karaoke color, outline width, and shadow.
- New styles can be added to `CAPTION_STYLES` dictionary and exposed in `CaptionEditorModal.tsx`.

---

## 🌿 Branching & Commit Guidelines

1. Always branch from `main`:
   ```bash
   git checkout main
   git pull upstream main
   git checkout -b feat/your-feature-name
   ```
2. Follow **Conventional Commits**:
   - `feat(scope): short description` (New feature)
   - `fix(scope): short description` (Bug fix)
   - `docs(scope): short description` (Documentation change)
   - `refactor(scope): short description` (Code reorganization)
   - `perf(scope): short description` (Performance improvement)
   - `test(scope): short description` (Adding or updating tests)

---

## 📐 Coding Standards

### Backend (Python)
- Format with **PEP 8** standards.
- Use explicit type hints (`typing.List`, `typing.Optional`, etc.).
- Avoid `shell=True` in `subprocess` executions to protect against command injection.
- Validate all incoming API payloads using Pydantic schemas in `backend/schemas/`.

### Frontend (TypeScript / React)
- Use functional components with hooks.
- Keep components typed; avoid `any`.
- Adhere to the Ant Design 5 and Tailwind CSS design patterns.
- Ensure `npm run typecheck` passes with **0 errors**.
- Ensure `npm run lint` passes with **0 warnings**.

---

## 🧪 Running Tests

Ensure all automated tests pass before opening a PR:

```bash
# Run backend pytest suite (266 tests)
./venv/bin/pytest backend/tests -q -W ignore

# Run custom provider tests
./venv/bin/pytest backend/tests/test_llm_custom_providers.py -v

# Run frontend typecheck & lint
cd frontend
npm run typecheck
npm run lint
cd ..
```

---

## 🚀 Submitting a Pull Request

1. Push your branch to your fork:
   ```bash
   git push origin feat/your-feature-name
   ```
2. Open a Pull Request on GitHub against `santimacorp-droid/ClipFarm` (`main` branch).
3. Fill out the PR template, referencing any related issue numbers (e.g., `Fixes #12`).
4. Ensure CI tests pass. Maintainers will review your PR and provide feedback promptly!

---

## ☕ Support the Project

If you love ClipFarm, you can also support development directly:
👉 **[Support on Ko-fi (https://ko-fi.com/santima)](https://ko-fi.com/santima)**

<div align="center">
  <sub>Thank you for contributing to ClipFarm Studio! 🚀</sub>
</div>
