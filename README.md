<div align="center">

<img width="489" height="162" alt="image" src="https://github.com/user-attachments/assets/8a61c5a0-d1e6-4de5-a261-6897c18c2830" />

# Topic2Manim

</div>

Automatic educational video generator using AI and Manim. Converts any topic into a professional animated video with narration and mathematical visualizations.

<div align="center">

## User Interface

![video](./public/output6.gif)

</div>

<div align="center">

## Examples

</div>

> prompt: How do machines learn to recognize MNIST dataset numbers?
>
> model: claude-sonnet-4-5-20250929
>
> response:

<div align="center">

![video](./public/output5.gif)

</div>

> prompt: What is a Markov chain and how are they related to LLMs?
>
> model: claude-sonnet-4-5-20250929
>
> response:

<div align="center">

![video](./public/output4.gif)

</div>

> prompt: How does Cramer's rule work for system of linear equations?
>
> model: claude-sonnet-4-5-20250929
>
> response:

<div align="center">

![video](./public/output3.gif)

</div>

> prompt: how chat gpt works?
>
> model: gpt-5.2
>
> response:

<div align="center">

![video](./public/output.gif)

</div>

> prompt: how tokenization works in chat gpt?
>
> model: gpt-5.2
>
> response:

<div align="center">

![video](./public/output2.gif)

</div>

## Features

- **Multi-LLM Support** — OpenAI, Claude, Kimi (Moonshot), MiniMax, Ollama (cloud + local)
- **Multi-TTS Support** — OpenAI TTS, ElevenLabs
- **Script import** — Paste scripts in JSON, markdown, or loose scene format
- **Script review** — Pause after script generation to edit before rendering
- **Parallel scene rendering** — Compile multiple scenes concurrently with checkpointing
- **Visual frame critic** — LLM reviews rendered frames for alignment with narration
- **Automatic code fixing** — REPL loop compiles Manim code, fixes errors with LLM
- **Scene retry & preview** — Re-render individual scenes or preview before full run
- **Job persistence** — Resume interrupted renders from last checkpoint

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  User Topic │────▶│  Script Generation│────▶│  Script Review  │
└─────────────┘     │  (Multi-LLM)      │     │  (Optional)     │
                    └──────────────────┘     └─────────────────┘
                                                       │
                    ┌──────────────────┐              ▼
                    │  TTS Generation  │◄────┌─────────────────┐
                    │  (OpenAI/Eleven) │     │  Scene Rendering│
                    └──────────────────┘     │  (Parallel)     │
                           │                 └─────────────────┘
                           ▼                           │
                    ┌──────────────────┐              ▼
                    │  Video Assembly  │◄────┌─────────────────┐
                    │  (concat + merge)│     │  Frame Critic   │
                    └──────────────────┘     │  (Optional)     │
                           │                 └─────────────────┘
                           ▼
                    ┌──────────────────┐
                    │  Final Video     │
                    └──────────────────┘
```

### Key Modules

| Module | Purpose |
|--------|---------|
| `video_generator.py` | Job orchestration, thread-safe state, API surface |
| `render_pipeline.py` | Parallel scene compilation, checkpointing, REPL fixing |
| `llm_providers.py` | Multi-provider LLM client setup (OpenAI, Claude, Kimi, MiniMax, Ollama) |
| `tts_generator.py` | TTS with OpenAI and ElevenLabs, audio fragmentation |
| `frame_critic.py` | Vision-based quality critique of rendered frames |
| `script_import.py` | Parse pasted scripts from JSON, markdown, or loose format |
| `concat_video.py` | Manim compilation, ffmpeg concat/merge with input validation |
| `main.py` | Flask API with CORS, config endpoints, job management |

## Prerequisites

- **Python 3.11+** (developed on 3.14)
- **[uv](https://github.com/astral-sh/uv)** for dependency management
- **Docker Desktop** (strongly recommended, especially on Windows)
- **At least one LLM API key** (or use local Ollama)

> **Windows Note:** Manim requires a C++ compiler (MSVC 14.0) to build its dependencies natively. The easiest path on Windows is **Docker** — the Dockerfile already installs Manim and all system dependencies.

## Installation

### 1. Clone and setup

```bash
git clone https://github.com/mateolafalce/topic2manim.git
cd topic2manim

# Create virtual environment and install dependencies
uv sync

# On Windows: .venv\Scripts\activate
source .venv/bin/activate

cp .env.example .env
```

### 2. Configure providers

Edit `.env` with your API keys:

```bash
# Pick at least one LLM provider
OPENAI_API_KEY=sk-...
CLAUDE_API_KEY=sk-ant-...
KIMI_API_KEY=...
MINIMAX_API_KEY=...
OLLAMA_API_KEY=...          # Optional for Ollama Cloud; local Ollama needs no key

# Pick at least one TTS provider
OPENAI_API_KEY=sk-...       # Reused for OpenAI TTS
ELEVENLABS_API_KEY=...
```

### 3. Run

#### Option A: Native Python (macOS / Linux / WSL)

```bash
python src/main.py
```

#### Option B: Docker (recommended for Windows)

```bash
docker compose up --build
```

On Windows, use the provided helper:

```powershell
.\restart.ps1
```

Then open [http://localhost:5000](http://localhost:5000).

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web UI |
| `/api/health` | GET | Health check |
| `/api/config` | GET | Available providers, models, voices, settings |
| `/api/generate` | POST | Start video generation |
| `/api/progress/<job_id>` | GET | Job status and progress |
| `/api/jobs` | GET | List recent jobs |
| `/api/jobs/<id>/cancel` | POST | Cancel running job |
| `/api/jobs/<id>/script` | PUT | Edit script during review |
| `/api/jobs/<id>/continue` | POST | Approve script and continue rendering |
| `/api/jobs/<id>/resume` | POST | Resume interrupted render |
| `/api/jobs/<id>/scenes/<idx>/retry` | POST | Re-render a specific scene |
| `/api/preview-scene` | POST | Render a single scene at preview quality |
| `/api/script/parse` | POST | Parse pasted script without rendering |
| `/api/script/prompt-template` | GET | Get a copy-paste prompt for ChatGPT/Claude |
| `/api/providers/health` | GET/POST | Check provider connectivity before generating |

## Development

### Run tests

```bash
pytest tests/ -v
```

### Lint and format

```bash
ruff check src/ tests/
black src/ tests/
```

### Project structure

```
topic2manim/
├── src/
│   ├── main.py                 # Flask API
│   ├── video_generator.py      # Job orchestration
│   ├── render_pipeline.py      # Parallel compilation + checkpointing
│   ├── llm_providers.py        # Multi-provider LLM setup
│   ├── llm_chat.py             # Chat completion helpers
│   ├── tts_generator.py        # TTS generation
│   ├── animations.py           # Script generation
│   ├── manim_generator.py      # Manim code generation
│   ├── concat_video.py         # Video compilation
│   ├── frame_critic.py         # Visual quality critique
│   ├── script_import.py        # Script parsing
│   ├── video_settings.py       # Length/style/quality presets
│   └── frontend/               # Web UI
├── tests/                      # pytest suite
├── .github/workflows/ci.yml    # GitHub Actions CI
├── docker-compose.yml
├── Dockerfile
└── README.md
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `No API key found` | Configure at least one LLM key in `.env` |
| `MSVC 14.0 is required` on Windows | Use Docker instead of native Python |
| Manim compilation timeout | Increase `RENDER_PARALLEL_WORKERS` or reduce scene count |
| Empty LLM response | Check provider health at `/api/providers/health`; switch provider |
| Ollama connection failed | Verify `OLLAMA_BASE_URL` and that Ollama is running |

## License

MIT
