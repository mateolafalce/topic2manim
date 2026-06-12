# Agent Instructions for Topic2Manim

## Project Overview

AI-powered educational video generator using Manim. Multi-LLM, multi-TTS, parallel rendering with checkpointing and frame critic.

## Environment

- **Python**: 3.14.2 via `uv` (venv at `.venv/`)
- **OS**: Windows primary, Docker Linux for rendering
- **Test runner**: pytest 9.0.3
- **Linting**: ruff 0.15.15, black

## Key Commands

```bash
# Run tests
.venv/Scripts/python -m pytest tests/ -v

# Lint / format
.venv/Scripts/ruff check src/ tests/
.venv/Scripts/black src/ tests/

# Run Flask server
.venv/Scripts/python src/main.py

# Docker (recommended on Windows)
docker compose up --build
# Or on Windows PowerShell:
.\restart.ps1
```

## Architecture Notes

- `jobs = {}` and `jobs_lock = threading.RLock()` in `video_generator.py` — ALWAYS lock when touching `jobs`
- `video_generator.py` is the API surface; `render_pipeline.py` does the actual work
- `_job_threads` tracks running daemon threads so tests can join them
- `llm_providers.py` handles OpenAI, Claude, Kimi, MiniMax, Ollama
- `llm_chat.py` has `complete_llm()` and `complete_llm_vision()` — vision falls back to text when no images
- `concat_video.py` validates `class_name` against `^[A-Za-z_][A-Za-z0-9_]*$` and uses `tempfile` for ffmpeg list files
- `frame_critic.py` extracts frames with ffmpeg, calls vision LLM

## Testing Conventions

- New tests go in `tests/test_<module>.py`
- Use `@patch` for external API calls (LLM, TTS, ffmpeg)
- The `clean_jobs` fixture in `test_video_generator_integration.py` cancels threads and joins them — copy pattern if you add thread-spawning tests
- Flask endpoint tests use `app.test_client()` in `tests/test_api_endpoints.py`

## Common Pitfalls

1. **Manim on Windows**: Requires MSVC 14.0. If missing, use Docker. Don't try to `pip install manim` on Windows without Visual C++ Build Tools.
2. **JSON serialization**: Never put non-serializable objects (Thread, Lock, etc.) into job dicts returned by Flask. Use `_job_threads` for thread storage.
3. **LLM provider return format**: `generate_script_json` returns `(video_data, error)` tuple. Unpack it.
4. **Ollama vision**: `images_base64` are passed as strings directly to Ollama's `/api/chat` — do NOT `base64.b64decode` them before JSON serialization.

## CI/CD

GitHub Actions runs ruff, black, mypy, pytest on Python 3.11/3.12. See `.github/workflows/ci.yml`.
