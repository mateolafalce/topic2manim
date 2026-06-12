"""Tests for LLM error message formatting."""

from llm_errors import format_llm_error, _guess_provider_from_error


def test_format_insufficient_balance():
    msg = format_llm_error("Error: insufficient_balance")
    assert "insufficient balance" in msg.lower()
    assert "Ollama" in msg


def test_format_kimi_suspended():
    msg = format_llm_error("suspended due to insufficient balance for kimi")
    assert "Kimi" in msg
    assert "kimi.ai" in msg


def test_format_invalid_auth():
    msg = format_llm_error("Invalid Authentication")
    assert "Invalid API key" in msg
    assert ".env" in msg


def test_format_401():
    msg = format_llm_error("HTTP 401 from API")
    assert "Authentication failed" in msg


def test_format_402():
    msg = format_llm_error("HTTP 402 payment required")
    assert "billing error" in msg


def test_format_ollama_connection():
    msg = format_llm_error("Ollama connection failed: refused")
    assert "Ollama connection failed" in msg


def test_format_ollama_http():
    msg = format_llm_error("Ollama HTTP 500: error")
    assert "Ollama HTTP" in msg


def test_format_json_error():
    msg = format_llm_error("Could not parse JSON: trailing comma")
    assert "invalid JSON" in msg


def test_format_unknown_passthrough():
    msg = format_llm_error("Something weird happened")
    assert msg == "Something weird happened"


# ---------------------------------------------------------------------------
# _guess_provider_from_error
# ---------------------------------------------------------------------------
def test_guess_kimi():
    assert "Kimi" in _guess_provider_from_error("moonshot error")
    assert "Kimi" in _guess_provider_from_error("kimi failure")


def test_guess_minimax():
    assert "MiniMax" in _guess_provider_from_error("minimax timeout")


def test_guess_openai():
    assert "OpenAI" in _guess_provider_from_error("openai rate limit")


def test_guess_claude():
    assert "Claude" in _guess_provider_from_error("anthropic error")
    assert "Claude" in _guess_provider_from_error("claude timeout")


def test_guess_fallback():
    assert "selected LLM provider" in _guess_provider_from_error("unknown")
