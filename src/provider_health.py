"""Quick health checks for configured LLM and TTS providers."""

from openai import APITimeoutError

from llm_errors import format_llm_error
from llm_providers import (
    LLM_PROVIDERS,
    get_configured_llm_providers,
    is_provider_configured,
    setup_llm_client,
)
from llm_chat import complete_llm
from tts_generator import get_available_tts_providers, setup_tts_config


def _status(ok, message, detail=None):
    result = {"ok": ok, "message": message}
    if detail:
        result["detail"] = detail
    return result


def check_llm_provider(provider_id, model=None):
    """Ping an LLM provider with a minimal request."""
    provider_id = (provider_id or "").lower().strip()
    if not is_provider_configured(provider_id):
        label = LLM_PROVIDERS.get(provider_id, {}).get("label", provider_id)
        return _status(False, f"{label} is not configured (missing API key)")

    try:
        config = setup_llm_client(provider_id, model)
        response = complete_llm(
            client=config["client"],
            provider=config["provider"],
            model=config["model"],
            system_prompt="Reply briefly.",
            user_prompt="Reply with exactly: OK",
            max_tokens=20,
        )
        if not response:
            return _status(False, "Empty response from provider")
        return _status(
            True,
            f"Ready ({config['model']})",
            detail=response[:60],
        )
    except APITimeoutError:
        return _status(False, "Connection timed out — provider may be slow or unreachable")
    except Exception as exc:
        return _status(False, format_llm_error(exc))


def check_tts_provider(provider_id, voice_id=None):
    """Verify TTS credentials and optional voice selection."""
    provider_id = (provider_id or "").lower().strip()
    if provider_id in (None, "", "auto"):
        configured = get_available_tts_providers()
        if not configured:
            return _status(False, "No TTS provider configured")
        provider_id = configured[0]

    try:
        config = setup_tts_config(provider_id, voice_id)
        if not config:
            return _status(False, "TTS provider not configured")
        if config["provider"] == "openai":
            return _status(True, f"Ready (voice: {config['voice']})")
        voice_label = config.get("voice_name") or config["voice_id"]
        return _status(True, f"Ready (voice: {voice_label})")
    except Exception as exc:
        return _status(False, str(exc))


def check_providers(
    llm_provider=None, llm_model=None, tts_provider=None, tts_voice=None, enable_tts=True
):
    """Run health checks for the providers about to be used."""
    results = {"llm": {}, "tts": None}

    if llm_provider in (None, "", "auto"):
        configured = get_configured_llm_providers()
        if not configured:
            results["llm"]["setup"] = _status(
                False,
                "No LLM configured — add an API key to .env (project root), then restart the server",
            )
        for provider_id in configured:
            results["llm"][provider_id] = check_llm_provider(provider_id)
    else:
        results["llm"][llm_provider] = check_llm_provider(llm_provider, llm_model)

    if enable_tts:
        results["tts"] = check_tts_provider(tts_provider, tts_voice)

    llm_ok = any(item.get("ok") for item in results["llm"].values())
    tts_ok = results["tts"] is None or results["tts"].get("ok")

    results["ready"] = llm_ok and tts_ok
    results["llm_ready"] = llm_ok
    results["tts_ready"] = tts_ok
    return results
