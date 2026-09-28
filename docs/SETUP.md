# Installation and configuration

## Supported setup

Validated on Windows with Python **3.12**, PowerShell, Git, and [Ollama](https://ollama.com/download/windows). The tested CPU host has 16 GB RAM; keep sufficient memory available and expect some local answers to take minutes. A GPU is optional. Node.js is required only for JavaScript tests. Linux/macOS launch and packaging are not validated for this release.

```powershell
git clone https://github.com/MohamedZakkaria2004/Threadline.git
cd Threadline
.\setup.ps1
ollama pull qwen3:4b-instruct-2507-q4_K_M
ollama pull nomic-embed-text:latest
.\start.ps1 -Seed
```

Keep Ollama running. Model pulls are one-time downloads if the exact tags are absent. Setup uses `uv sync --frozen --group dev` when uv is available, or creates a Python 3.12 environment and installs `requirements.lock.txt` with pip. Initial downloads need internet; inference, embeddings and UI assets run locally afterward. Startup never downloads a model automatically.

Open **http://127.0.0.1:8765**. Credentials are generated for `employee`, `hr`, `manager`, and `admin` and written to `demo-credentials.txt` at the **exact path printed by the server**. Normally this is `%LOCALAPPDATA%\EnterpriseCopilot`; packaged terminals may resolve LocalAppData differently. Fresh clones do not inherit the presenter's local demo passwords.

Use `.\start.ps1` or **Start Threadline.cmd** on later runs. The legacy **Start Atlas.cmd** is retained for compatibility. Stop foreground execution with Ctrl+C. `stop.ps1` verifies the saved PID and command before stopping a background instance on the default port.

## Alternative setup

If a Python launcher cannot find an installed 3.12 interpreter:

```powershell
.\setup.ps1 -PythonExecutable '<full path to Python 3.12 python.exe>'
```

This explicitly selects the pip fallback and validates the interpreter. If PowerShell blocks scripts, with uv installed use:

```powershell
uv sync --frozen --group dev
.\.venv\Scripts\python.exe -m scripts.seed
.\.venv\Scripts\python.exe -m app
```

Stop the server before seeding, backend updates, or offline backups. One process owns Qdrant's embedded store. There is no hot reload; restart after code/configuration changes. The machine must remain awake for inference to continue.

## Environment variables

The app reads the **process environment**; it does not automatically load `.env`. [`.env.example`](../.env.example) documents supported variables and contains no credentials.

| Variable | Default | Meaning |
|---|---|---|
| `COPILOT_MODEL` | `qwen3:4b-instruct-2507-q4_K_M` | Installed local generation model |
| `COPILOT_EMBED_MODEL` | `nomic-embed-text:latest` | Installed local embedding model |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Loopback HTTP only |
| `COPILOT_DATA_DIR` | LocalAppData / `EnterpriseCopilot` on Windows | Persistent data location; keep outside cloud sync |
| `COPILOT_PORT` | `8765` | Loopback web port |
| `COPILOT_PROMPT_VERSION` | `v4` | Versioned prompt directory (`v1`–`v4`) |
| `COPILOT_POWER_WATTS` | `100` | Assumed generation power for estimated electricity |
| `COPILOT_ELECTRICITY_USD_KWH` | `0.15` | Assumed electricity tariff; not a measured price |

```powershell
$env:COPILOT_PORT = '8765'
$env:COPILOT_MODEL = 'qwen3:4b-instruct-2507-q4_K_M'
.\start.ps1
```

Hosted model names containing `cloud` and non-loopback Ollama URLs are rejected. Changing an embedding model requires reseeding/re-uploading for that model's collection. Keep installed model contents stable for an active index. Use a separate `COPILOT_DATA_DIR` for disposable demonstrations; never point two running processes at the same store.

## Verify startup

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/health
```

Confirm `status: ready`, the intended model names, and no missing model. The response includes a startup source fingerprint, not a Git commit SHA. Check the UI's **Local models ready** indicator. Sign in and ask the [known annual-leave question](USAGE.md).

## Troubleshooting

| Symptom | Check / recovery |
|---|---|
| Cannot open the website | Keep the server terminal running; confirm loopback health and the configured port |
| Model unavailable | Start Ollama; run `ollama list`; install the exact configured tags |
| Empty knowledge / no evidence | Complete first-run seeding; inspect Document library status and audience |
| Vector storage lock | Stop the existing server/seed task; do not run multiple workers |
| Busy response | Wait for active ingestion, answer generation or benchmark to finish |
| Long answer latency | Free RAM; run tasks sequentially; avoid benchmarks during the demonstration |
| Incorrect login | Use the credentials file from the active data directory, not another store |
| Replaced benchmark policies | Quality lab requires unchanged seeded annual-leave, procurement and travel policies; use a fresh disposable store |
| Interrupted request after restart | Inspect failed state; submit a new request deliberately rather than replaying an action automatically |

For backup/restore, retention and capacity procedures, read the [operations runbook](OPERATIONS_RUNBOOK.md). Keep the app on loopback; publishing source does not authorize public hosting.
