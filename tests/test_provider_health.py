"""Tests for provider_health LLM/TTS connectivity checks."""

from unittest.mock import MagicMock, patch


from provider_health import check_providers, check_llm_provider, check_tts_provider, _status


# ---------------------------------------------------------------------------
# _status helper
# ---------------------------------------------------------------------------
def test_status_basic():
    s = _status(True, "all good")
    assert s["ok"] is True
    assert s["message"] == "all good"
    assert "detail" not in s


def test_status_with_detail():
    s = _status(False, "bad", detail="verbose")
    assert s["ok"] is False
    assert s["detail"] == "verbose"


# ---------------------------------------------------------------------------
# check_llm_provider
# ---------------------------------------------------------------------------
@patch("provider_health.is_provider_configured", return_value=False)
def test_check_llm_not_configured(mock_configured):
    result = check_llm_provider("openai")
    assert result["ok"] is False
    assert "not configured" in result["message"]


@patch("provider_health.is_provider_configured", return_value=True)
@patch("provider_health.setup_llm_client")
@patch("provider_health.complete_llm", return_value="OK")
def test_check_llm_success(mock_complete, mock_setup, mock_configured):
    mock_setup.return_value = {"client": MagicMock(), "provider": "openai", "model": "gpt-4o"}
    result = check_llm_provider("openai")
    assert result["ok"] is True
    assert "Ready" in result["message"]


@patch("provider_health.is_provider_configured", return_value=True)
@patch("provider_health.setup_llm_client")
@patch("provider_health.complete_llm", return_value="")
def test_check_llm_empty_response(mock_complete, mock_setup, mock_configured):
    mock_setup.return_value = {"client": MagicMock(), "provider": "openai", "model": "gpt-4o"}
    result = check_llm_provider("openai")
    assert result["ok"] is False
    assert "Empty response" in result["message"]


@patch("provider_health.is_provider_configured", return_value=True)
@patch("provider_health.setup_llm_client", side_effect=ValueError("bad key"))
def test_check_llm_exception(mock_setup, mock_configured):
    result = check_llm_provider("openai")
    assert result["ok"] is False
    assert "bad key" in result["message"]


# ---------------------------------------------------------------------------
# check_tts_provider
# ---------------------------------------------------------------------------
@patch("provider_health.get_available_tts_providers", return_value=[])
def test_check_tts_auto_none_configured(mock_get):
    result = check_tts_provider("auto")
    assert result["ok"] is False
    assert "No TTS provider" in result["message"]


@patch("provider_health.get_available_tts_providers", return_value=["openai"])
@patch("provider_health.setup_tts_config")
def test_check_tts_auto_selects_first(mock_setup, mock_get):
    mock_setup.return_value = {"provider": "openai", "voice": "alloy"}
    result = check_tts_provider("auto")
    assert result["ok"] is True
    assert "alloy" in result["message"]


@patch("provider_health.setup_tts_config")
def test_check_tts_openai_ready(mock_setup):
    mock_setup.return_value = {"provider": "openai", "voice": "alloy"}
    result = check_tts_provider("openai")
    assert result["ok"] is True


@patch("provider_health.setup_tts_config")
def test_check_tts_elevenlabs_ready(mock_setup):
    mock_setup.return_value = {"provider": "elevenlabs", "voice_name": "Alice", "voice_id": "abc"}
    result = check_tts_provider("elevenlabs")
    assert result["ok"] is True
    assert "Alice" in result["message"]


@patch("provider_health.setup_tts_config", side_effect=ValueError("no key"))
def test_check_tts_exception(mock_setup):
    result = check_tts_provider("openai")
    assert result["ok"] is False
    assert "no key" in result["message"]


# ---------------------------------------------------------------------------
# check_providers (aggregate)
# ---------------------------------------------------------------------------
@patch("provider_health.get_configured_llm_providers", return_value=[])
@patch("provider_health.check_tts_provider")
def test_check_providers_auto_no_llm_configured(mock_tts, _mock_get):
    mock_tts.return_value = {"ok": False, "message": "no tts"}
    result = check_providers()
    assert result["ready"] is False
    assert result["llm"]["setup"]["ok"] is False
    assert ".env" in result["llm"]["setup"]["message"]


@patch("provider_health.get_configured_llm_providers", return_value=["ollama"])
@patch("provider_health.check_llm_provider")
@patch("provider_health.check_tts_provider")
def test_check_providers_auto(mock_tts, mock_llm, mock_get):
    mock_llm.return_value = {"ok": True, "message": "ready"}
    mock_tts.return_value = {"ok": True, "message": "ready"}
    result = check_providers()
    assert result["ready"] is True
    assert result["llm_ready"] is True
    assert result["tts_ready"] is True
    assert "ollama" in result["llm"]


@patch("provider_health.check_llm_provider")
@patch("provider_health.check_tts_provider")
def test_check_providers_specific(mock_tts, mock_llm):
    mock_llm.return_value = {"ok": False, "message": "down"}
    mock_tts.return_value = {"ok": True, "message": "ready"}
    result = check_providers(llm_provider="openai", enable_tts=True)
    assert result["ready"] is False
    assert result["llm_ready"] is False
    assert result["tts_ready"] is True


@patch("provider_health.check_llm_provider")
def test_check_providers_no_tts(mock_llm):
    mock_llm.return_value = {"ok": True, "message": "ready"}
    result = check_providers(enable_tts=False)
    assert result["ready"] is True
    assert result["tts"] is None
    assert result["tts_ready"] is True
