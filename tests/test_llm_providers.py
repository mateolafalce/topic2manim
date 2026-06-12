"""Tests for LLM provider configuration and client setup."""

from unittest.mock import patch

import pytest

from llm_providers import (
    LLM_PROVIDER_IDS,
    LLM_PROVIDERS,
    get_all_llm_providers,
    get_configured_llm_providers,
    get_default_models,
    is_provider_configured,
    list_provider_models,
    setup_llm_client,
    uses_openai_compatible_api,
    _provider_spec,
)


def test_get_all_llm_providers():
    providers = get_all_llm_providers()
    assert set(providers) == set(LLM_PROVIDER_IDS)
    assert "claude" in providers
    assert "openai" in providers


def test_provider_spec_known():
    spec = _provider_spec("openai")
    assert spec["label"] == "OpenAI"
    assert spec["api_style"] == "openai"


def test_provider_spec_unknown():
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        _provider_spec("not_a_provider")


@pytest.mark.parametrize(
    "provider_id,expected",
    [
        ("openai", True),
        ("claude", False),
        ("kimi", True),
        ("minimax", True),
        ("ollama", False),
    ],
)
def test_uses_openai_compatible_api(provider_id, expected):
    assert uses_openai_compatible_api(provider_id) == expected


def _make_read_env_mock(mapping):
    """Return a mock for _read_env that looks up values in mapping."""

    def mock_read_env(name):
        return mapping.get(name)

    return mock_read_env


@patch("llm_providers._read_env")
def test_is_provider_configured_openai(mock_read_env):
    mock_read_env.side_effect = _make_read_env_mock({"OPENAI_API_KEY": "sk-test"})
    assert is_provider_configured("openai") is True


@patch("llm_providers._read_env")
def test_is_provider_configured_openai_missing(mock_read_env):
    mock_read_env.side_effect = _make_read_env_mock({})
    assert is_provider_configured("openai") is False


@patch("llm_providers._read_env")
def test_is_provider_configured_ollama_local(mock_read_env):
    mock_read_env.side_effect = _make_read_env_mock({"OLLAMA_BASE_URL": "http://localhost:11434"})
    assert is_provider_configured("ollama") is True


@patch("llm_providers._read_env")
def test_is_provider_configured_ollama_cloud(mock_read_env):
    mock_read_env.side_effect = _make_read_env_mock({"OLLAMA_API_KEY": "ollama-test"})
    assert is_provider_configured("ollama") is True


@patch("llm_providers._read_env")
def test_is_provider_configured_ollama_missing(mock_read_env):
    # Local Ollama at localhost:11434 is considered configured by default
    mock_read_env.side_effect = _make_read_env_mock({})
    assert is_provider_configured("ollama") is True


@patch("llm_providers._read_env")
def test_get_configured_llm_providers(mock_read_env):
    mock_read_env.side_effect = _make_read_env_mock(
        {
            "OPENAI_API_KEY": "sk-test",
            "CLAUDE_API_KEY": "claude-test",
        }
    )
    configured = get_configured_llm_providers()
    assert "openai" in configured
    assert "claude" in configured
    assert "kimi" not in configured


@patch("llm_providers._read_env")
def test_get_configured_llm_providers_none(mock_read_env):
    # Local Ollama is always considered configured
    mock_read_env.side_effect = _make_read_env_mock({})
    assert get_configured_llm_providers() == ["ollama"]


@patch("llm_providers._read_env")
def test_get_default_models(mock_read_env):
    mock_read_env.side_effect = _make_read_env_mock({})
    models = get_default_models()
    assert "openai" in models
    assert "claude" in models
    assert models["openai"] == LLM_PROVIDERS["openai"]["default_model"]


@patch("llm_providers._read_env")
def test_get_default_models_env_override(mock_read_env):
    mock_read_env.side_effect = _make_read_env_mock({"OPENAI_MODEL": "gpt-4o-mini"})
    models = get_default_models()
    assert models["openai"] == "gpt-4o-mini"


@patch("llm_providers._read_env")
def test_list_provider_models_non_ollama(mock_read_env):
    mock_read_env.side_effect = _make_read_env_mock({})
    models = list_provider_models("openai")
    assert len(models) == 1
    assert models[0] == LLM_PROVIDERS["openai"]["default_model"]


def test_list_provider_models_unknown():
    assert list_provider_models("unknown_provider") == []


@patch("llm_providers._read_env")
def test_setup_llm_client_explicit_provider(mock_read_env):
    mock_read_env.side_effect = _make_read_env_mock({"OPENAI_API_KEY": "sk-test"})
    config = setup_llm_client(provider_preference="openai")
    assert config["provider"] == "openai"
    assert config["api_style"] == "openai"


@patch("llm_providers._read_env")
def test_setup_llm_client_model_override(mock_read_env):
    mock_read_env.side_effect = _make_read_env_mock({"OPENAI_API_KEY": "sk-test"})
    config = setup_llm_client(provider_preference="openai", model_override="gpt-3.5-turbo")
    assert config["model"] == "gpt-3.5-turbo"


@patch("llm_providers._read_env")
def test_setup_llm_client_auto_priority(mock_read_env):
    mock_read_env.side_effect = _make_read_env_mock({"OPENAI_API_KEY": "sk-test"})
    config = setup_llm_client(provider_preference="auto")
    assert config["provider"] == "openai"


@patch("llm_providers._read_env")
def test_setup_llm_client_no_providers(mock_read_env):
    # With no API keys and no local Ollama, auto falls back to Ollama (local default)
    mock_read_env.side_effect = _make_read_env_mock({})
    config = setup_llm_client(provider_preference="auto")
    assert config["provider"] == "ollama"
    assert config["api_style"] == "ollama"


@patch("llm_providers._read_env")
def test_setup_llm_client_unconfigured_provider(mock_read_env):
    mock_read_env.side_effect = _make_read_env_mock({})
    with pytest.raises(ValueError, match="OpenAI selected but OPENAI_API_KEY is not configured"):
        setup_llm_client(provider_preference="openai")
