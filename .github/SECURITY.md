# 🛡️ Security Policy

We take the security and privacy of **ClipFarm Studio** and its users seriously. This document outlines our supported versions, vulnerability reporting procedures, and security best practices.

---

## 📦 Supported Versions

Only the latest major and active minor releases receive active security updates and vulnerability patches:

| Version | Supported | Status |
| :--- | :---: | :--- |
| **2.0.x** (ClipFarm Studio) | ✅ | **Active Support & Security Patches** |
| 1.x (Legacy AutoClip) | ❌ | End of Life / Unsupported |
| < 1.0 | ❌ | End of Life |

---

## 🚨 Reporting a Vulnerability

**Please DO NOT report security vulnerabilities via public GitHub Issues, Discussions, or social media.**

If you discover a potential security flaw or vulnerability in ClipFarm, please report it privately:

### 1. GitHub Private Security Advisory (Preferred)
Submit a private report directly via GitHub:
👉 **[Report a Security Vulnerability](https://github.com/santimacorp-droid/ClipFarm/security/advisories/new)**

This allows our maintainers to collaborate with you on a private fix and coordinate a public advisory before disclosure.

### 2. What to Include in Your Report
To help us triage and resolve the issue quickly, please provide:
- **Type of vulnerability** (e.g., Command injection, Path traversal, SSRF, XSS, Secret leak).
- **Component affected** (e.g., Video processor, Subtitle parser, Settings API, WebSocket gateway).
- **Step-by-step reproduction instructions** with minimal proof-of-concept (PoC) code or inputs.
- **Potential impact** and attack scenarios.
- **Affected environment** (Operating System, Python version, Node.js version, deployment mode: Docker, Desktop, or Native).

### Response Timeline
- **Initial Acknowledgement**: Within 48 hours.
- **Preliminary Triage & Assessment**: Within 5 business days.
- **Patch Release & Advisory Publication**: Coordinated responsibly based on severity (typically 7–30 days).

---

## 🔒 Privacy & Security Architecture

ClipFarm is built from the ground up to respect creator privacy and safeguard sensitive data:

### 1. 100% Offline Local AI Mode
- When using **Ollama** or **LM Studio** for LLM reasoning and local **Faster-Whisper** for speech recognition, **zero video bytes, audio recordings, or transcript texts leave your host machine**.
- The entire transcription, analysis, framing, and video rendering pipeline executes strictly on your local hardware.

### 2. API Key Protection
- Cloud provider API keys (OpenAI, Anthropic Claude, DeepSeek, Groq, OpenRouter, Google Gemini, DashScope) entered in the Settings UI are stored locally on your machine in `data/settings.json`.
- **API keys are NEVER sent to ClipFarm maintainers, servers, or telemetry services.**
- All API keys are excluded from git commits via `.gitignore`.

### 3. Subprocess & Media Pipeline Sanitization
- Video slicing and rendering run through `ffmpeg` and `ffprobe` subprocess calls using explicit argument lists (avoiding shell string interpolation `shell=True` to prevent command injection).
- User inputs and video filenames are sanitized before being passed to filesystem operations.

---

## 🛠️ Security Best Practices for Users

### 1. Environment & Secret Hygiene
- Never commit `.env` or configuration files containing real API keys to version control.
- Ensure `.env` is listed in your `.gitignore` (ClipFarm includes this by default).
- Periodically rotate third-party API keys if working in shared or multi-user environments.

### 2. Network & Port Exposure
- By default, ClipFarm binds services to `0.0.0.0` for local Docker and dev server access.
- When running on a remote server or VPS, **do not expose port 8001 (Backend API) or port 3001 (Frontend UI) directly to the open internet without authentication**.
- Place ClipFarm behind a reverse proxy (e.g., **Nginx**, **Caddy**, or **Cloudflare Tunnel**) with HTTPS/TLS encryption and basic HTTP auth or OAuth.

```nginx
# Example Nginx Reverse Proxy with Security Headers
server {
    listen 443 ssl http2;
    server_name clipfarm.yourdomain.com;

    ssl_certificate /etc/ssl/certs/clipfarm.crt;
    ssl_certificate_key /etc/ssl/private/clipfarm.key;

    # Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    location / {
        proxy_pass http://127.0.0.1:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket Support for real-time progress
    location /ws {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### 3. Dependency Updates
Regularly update both backend and frontend dependencies to receive upstream security fixes:
```bash
# Update Python dependencies
pip install --upgrade -r requirements.txt

# Audit and update frontend dependencies
cd frontend && npm audit && npm update
```

---

## 📄 License & Attribution

ClipFarm is distributed under the [MIT License](LICENSE). While we strive to maintain a secure and robust codebase, the software is provided "AS IS" without warranty of any kind. Users are responsible for evaluating security requirements for their specific deployment environments.
