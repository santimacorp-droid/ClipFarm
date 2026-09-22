# 🤝 Contributing to ClipFarm Studio

Thank you for your interest in contributing to **ClipFarm Studio**! We welcome contributions from developers, designers, content creators, and AI enthusiasts of all experience levels.

---

## 📋 Table of Contents
- [Ways to Contribute](#-ways-to-contribute)
- [Development Setup](#-development-setup)
- [Branching & Workflow](#-branching--workflow)
- [Coding Standards](#-coding-standards)
- [Testing & Quality Assurance](#-testing--quality-assurance)
- [Submitting a Pull Request](#-submitting-a-pull-request)
- [Reporting Issues](#-reporting-issues)
- [Community Code of Conduct](#-community-code-of-conduct)

---

## 💡 Ways to Contribute

You can contribute to ClipFarm in several ways:
- 🐛 **Bug Fixes**: Resolve open issues on GitHub or fix edge-case bugs.
- ✨ **New Features**: Add support for new local/cloud LLMs, caption animations, or export formats.
- 🎨 **UI/UX Polish**: Enhance the React frontend, improve responsiveness, or refine typography.
- 📚 **Documentation**: Write tutorials, improve guides, or document advanced workflows.
- 🧪 **Test Coverage**: Add unit, integration, or end-to-end tests.
- ☕ **Sponsorship**: Support ongoing open-source maintenance via [Ko-fi](https://ko-fi.com/santima).

---

## 🛠️ Development Setup

### 1. Fork & Clone
Fork the repository to your GitHub account and clone it locally:

```bash
git clone https://github.com/santimacorp-droid/ClipFarm.git
cd ClipFarm

# Add your fork as origin if needed, and keep main updated:
git remote add upstream https://github.com/santimacorp-droid/ClipFarm.git
```

### 2. Environment Setup

```bash
# 1. Create and activate Python virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install backend Python dependencies
pip install -r requirements.txt

# 3. Install frontend Node dependencies
cd frontend
npm install
cd ..

# 4. Create local environment configuration
cp .env.example .env
```

### 3. Launch Development Servers

```bash
# Option A: One-command foreground launch (recommended)
./run_all.sh

# Option B: Manual service launch
# Terminal 1 - Backend:
python -m uvicorn backend.main:app --reload --port 8001

# Terminal 2 - Celery Task Queue:
celery -A backend.core.celery_app worker --loglevel=info -Q processing,upload,notification,maintenance

# Terminal 3 - Frontend:
cd frontend && npm run dev
```

- **Frontend Interface**: [http://localhost:3001](http://localhost:3001)
- **Backend API Docs**: [http://localhost:8001/docs](http://localhost:8001/docs)

---

## 🌿 Branching & Workflow

Always create a dedicated feature branch from `main`:

```bash
# Ensure local main is up to date
git checkout main
git pull upstream main

# Create a feature branch
git checkout -b feat/your-feature-name
```

### Commit Message Conventions
We follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat`: A new user-facing feature
- `fix`: A bug fix
- `docs`: Documentation updates
- `style`: Formatting, missing semicolons, etc. (no code change)
- `refactor`: Code refactoring without feature or bug changes
- `perf`: Performance optimizations
- `test`: Adding or correcting tests
- `chore`: Build tasks, dependency updates, or configuration

**Examples:**
```bash
git commit -m "feat(llm): add streaming responses for Ollama models"
git commit -m "fix(framing): prevent bounding box overflow on edge-standing subjects"
git commit -m "docs(readme): clarify CUDA acceleration requirements"
```

---

## 📐 Coding Standards

### Python (Backend)
- Follow **PEP 8** style guidelines.
- Add type annotations (`typing`) to all public functions and methods.
- Document functions and classes using clean Google-style docstrings.
- Ensure all database models inherit from `backend.core.database.Base`.
- Use Pydantic schemas for all API request/response models.

### TypeScript / React (Frontend)
- Write modular functional components with React Hooks.
- Ensure strict TypeScript typing (avoid `any` where possible).
- Adhere to the Ant Design 5 & Tailwind CSS styling architecture.
- Verify `npm run typecheck` passes with **0 errors**.
- Verify `npm run lint` passes with **0 warnings**.

---

## 🧪 Testing & Quality Assurance

Before opening a pull request, run the test suites locally to ensure no regressions:

```bash
# Run backend pytest suite
./venv/bin/pytest backend/tests -q -W ignore

# Run specific test module
./venv/bin/pytest backend/tests/test_smart_framing.py -v

# Run frontend typecheck & linter
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
2. Open a Pull Request against the `main` branch of [santimacorp-droid/ClipFarm](https://github.com/santimacorp-droid/ClipFarm/pulls).
3. Provide a clear PR description detailing:
   - What changed and why.
   - Any manual or automated verification steps taken.
   - Screenshots or video recordings for UI changes.
4. Maintainers will review your PR and provide constructive feedback.

---

## 🐛 Reporting Issues

- **Bug Reports**: Open an issue at [GitHub Issues](https://github.com/santimacorp-droid/ClipFarm/issues) using the bug report format. Include reproduction steps, OS details, and logs.
- **Security Vulnerabilities**: Please **do not** submit security flaws publicly. Refer to our [SECURITY.md](SECURITY.md) to report security issues privately.
- **Feature Requests & Ideas**: Join the conversation in [GitHub Discussions](https://github.com/santimacorp-droid/ClipFarm/discussions).

---

## 📜 Community Code of Conduct

ClipFarm is committed to providing an open, welcoming, diverse, and harassment-free environment. All participants are expected to treat others with respect, kindness, and professionalism.

---

<div align="center">
  <sub>Thank you for making ClipFarm better for creators worldwide! 🎬</sub>
</div>
