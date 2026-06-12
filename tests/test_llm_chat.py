"""Tests for llm_chat completion helpers across providers."""

from unittest.mock import MagicMock, patch

import pytest

from llm_chat import (
    complete_llm,
    complete_llm_vision,
    ollama_chat_complete,
)


# ---------------------------------------------------------------------------
# complete_llm — OpenAI-compatible
# ---------------------------------------------------------------------------
@patch("llm_chat.create_chat_completion")
def test_complete_llm_openai(mock_create):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "  Hello world  "
    mock_create.return_value = mock_response

    client = MagicMock()
    result = complete_llm(client, "openai", "gpt-4o", "sys", "user")
    assert result == "Hello world"
    mock_create.assert_called_once()


@patch("llm_chat.create_chat_completion")
def test_complete_llm_openai_empty_content(mock_create):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = None
    mock_response.choices[0].finish_reason = "stop"
    mock_create.return_value = mock_response

    client = MagicMock()
    with pytest.raises(Exception, match="empty content"):
        complete_llm(client, "openai", "gpt-4o", "sys", "user")


@patch("llm_chat.create_chat_completion")
def test_complete_llm_no_choices(mock_create):
    mock_response = MagicMock()
    mock_response.choices = []
    mock_create.return_value = mock_response

    client = MagicMock()
    with pytest.raises(Exception, match="No choices"):
        complete_llm(client, "kimi", "moonshot", "sys", "user")


# ---------------------------------------------------------------------------
# complete_llm — Claude
# ---------------------------------------------------------------------------
def test_complete_llm_claude():
    client = MagicMock()
    client.messages.create.return_value.content = [MagicMock(text="  Claude reply  ")]

    result = complete_llm(client, "claude", "claude-3", "sys", "user")
    assert result == "Claude reply"
    client.messages.create.assert_called_once()


# ---------------------------------------------------------------------------
# complete_llm — Ollama
# ---------------------------------------------------------------------------
@patch("llm_chat.ollama_chat_complete")
def test_complete_llm_ollama(mock_ollama):
    mock_ollama.return_value = "Ollama says hi"
    client = MagicMock()
    result = complete_llm(client, "ollama", "llama3", "sys", "user")
    assert result == "Ollama says hi"


# ---------------------------------------------------------------------------
# ollama_chat_complete
# ---------------------------------------------------------------------------
@patch("llm_chat.json.dumps")
@patch("llm_chat.urllib.request.urlopen")
def test_ollama_chat_success(mock_urlopen, mock_json_dumps):
    mock_json_dumps.return_value = '{"x":1}'
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"message": {"content": "  hi  "}}'
    mock_urlopen.return_value.__enter__.return_value = mock_response

    client = MagicMock()
    client.base_url = "http://localhost:11434"
    client.api_key = None

    result = ollama_chat_complete(client, "llama3", "sys", "user")
    assert result == "hi"


@patch("llm_chat.json.dumps")
@patch("llm_chat.urllib.request.urlopen")
def test_ollama_chat_thinking_fallback(mock_urlopen, mock_json_dumps):
    mock_json_dumps.return_value = '{"x":1}'
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"message": {"thinking": "  thought  "}}'
    mock_urlopen.return_value.__enter__.return_value = mock_response

    client = MagicMock()
    client.base_url = "http://localhost:11434"
    client.api_key = "key"

    result = ollama_chat_complete(client, "llama3", "sys", "user")
    assert result == "thought"


@patch("llm_chat.json.dumps")
@patch(
    "llm_chat.urllib.request.urlopen",
    side_effect=__import__("urllib.error", fromlist=["HTTPError"]).HTTPError(
        url="http://x", code=500, msg="err", hdrs={}, fp=None
    ),
)
def test_ollama_chat_http_error(mock_urlopen, mock_json_dumps):
    mock_json_dumps.return_value = '{"x":1}'
    client = MagicMock()
    client.base_url = "http://localhost:11434"
    client.api_key = None

    with pytest.raises(Exception, match="Ollama HTTP 500"):
        ollama_chat_complete(client, "llama3", "sys", "user")


@patch("llm_chat.json.dumps")
@patch(
    "llm_chat.urllib.request.urlopen",
    side_effect=__import__("urllib.error", fromlist=["URLError"]).URLError("refused"),
)
def test_ollama_chat_url_error(mock_urlopen, mock_json_dumps):
    mock_json_dumps.return_value = '{"x":1}'
    client = MagicMock()
    client.base_url = "http://localhost:11434"

    with pytest.raises(Exception, match="Ollama connection failed"):
        ollama_chat_complete(client, "llama3", "sys", "user")


# ---------------------------------------------------------------------------
# complete_llm_vision
# ---------------------------------------------------------------------------
@patch("llm_chat.complete_llm")
def test_vision_no_images_fallback(mock_complete):
    mock_complete.return_value = "text only"
    client = MagicMock()
    result = complete_llm_vision(client, "openai", "gpt-4o", "sys", "user", [])
    assert result == "text only"
    mock_complete.assert_called_once()


@patch("llm_chat.create_chat_completion")
def test_vision_openai(mock_create):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "vision result"
    mock_create.return_value = mock_response

    client = MagicMock()
    result = complete_llm_vision(client, "openai", "gpt-4o", "sys", "user", ["b64img"])
    assert result == "vision result"


@patch("llm_chat.create_chat_completion")
def test_vision_openai_compatible(mock_create):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "kimi vision"
    mock_create.return_value = mock_response

    client = MagicMock()
    result = complete_llm_vision(client, "kimi", "moonshot", "sys", "user", ["b64img"])
    assert result == "kimi vision"


def test_vision_claude():
    client = MagicMock()
    client.messages.create.return_value.content = [MagicMock(text="claude vision")]

    result = complete_llm_vision(client, "claude", "claude-3", "sys", "user", ["b64img"])
    assert result == "claude vision"
    call_kwargs = client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-3"


@patch("llm_chat.urllib.request.urlopen")
def test_vision_ollama(mock_urlopen):
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"message": {"content": "ollama vision"}}'
    mock_urlopen.return_value.__enter__.return_value = mock_response

    client = MagicMock()
    client.base_url = "http://localhost:11434"
    client.api_key = None

    result = complete_llm_vision(client, "ollama", "llama3", "sys", "user", ["b64img"])
    assert result == "ollama vision"


@patch("llm_chat.uses_openai_compatible_api", return_value=False)
def test_vision_unsupported_provider(mock_compat):
    client = MagicMock()
    with pytest.raises(Exception, match="not supported"):
        complete_llm_vision(client, "minimax", "model", "sys", "user", ["b64img"])
