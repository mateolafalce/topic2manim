import json
import os
import urllib.error
import urllib.request

import anthropic
import openai

from env_loader import load_app_env

LLM_PROVIDER_IDS = ("claude", "openai", "kimi", "minimax", "ollama")

LLM_PROVIDERS = {
    "claude": {
        "label": "Claude",
        "api_style": "anthropic",
        "api_key_env": "CLAUDE_API_KEY",
        "model_env": "CLAUDE_MODEL",
        "default_model": "claude-3-5-sonnet-20241022",
    },
    "openai": {
        "label": "OpenAI",
        "api_style": "openai",
        "api_key_env": "OPENAI_API_KEY",
        "model_env": "OPENAI_MODEL",
        "default_model": "gpt-4o",
        "base_url_env": "OPENAI_BASE_URL",
    },
    "kimi": {
        "label": "Kimi (Moonshot)",
        "api_style": "openai",
        "api_key_env": "KIMI_API_KEY",
        "model_env": "KIMI_MODEL",
        "default_model": "moonshot-v1-8k",
        "base_url_env": "KIMI_BASE_URL",
        "default_base_url": "https://api.moonshot.ai/v1",
    },
    "minimax": {
        "label": "MiniMax",
        "api_style": "openai",
        "api_key_env": "MINIMAX_API_KEY",
        "model_env": "MINIMAX_MODEL",
        "default_model": "MiniMax-Text-01",
        "base_url_env": "MINIMAX_BASE_URL",
        "default_base_url": "https://api.minimax.io/v1",
    },
    "ollama": {
        "label": "Ollama",
        "api_style": "ollama",
        "api_key_env": "OLLAMA_API_KEY",
        "model_env": "OLLAMA_MODEL",
        "default_model": "llama3.2",
        "base_url_env": "OLLAMA_BASE_URL",
        "default_base_url": "http://localhost:11434",
    },
}

AUTO_PRIORITY = ("claude", "openai", "kimi", "minimax", "ollama")


class OllamaClient:
    """Minimal client wrapper for Ollama's native HTTP API."""

    def __init__(self, base_url, api_key=None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key


def get_all_llm_providers():
    return list(LLM_PROVIDER_IDS)


def _provider_spec(provider_id):
    if provider_id not in LLM_PROVIDERS:
        raise ValueError(f"Unknown LLM provider: {provider_id}")
    return LLM_PROVIDERS[provider_id]


def _read_env(name):
    load_app_env()
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _ollama_base_url():
    return _read_env("OLLAMA_BASE_URL") or LLM_PROVIDERS["ollama"]["default_base_url"]


def _is_local_ollama(base_url):
    lowered = (base_url or "").lower()
    return any(
        token in lowered for token in ("localhost", "127.0.0.1", "host.docker.internal", ":11434")
    )


def is_provider_configured(provider_id):
    if provider_id == "ollama":
        base_url = _ollama_base_url()
        if _is_local_ollama(base_url):
            return True
        return bool(_read_env("OLLAMA_API_KEY"))

    spec = _provider_spec(provider_id)
    return bool(_read_env(spec["api_key_env"]))


def get_configured_llm_providers():
    return [provider_id for provider_id in LLM_PROVIDER_IDS if is_provider_configured(provider_id)]


def uses_openai_compatible_api(provider_id):
    return _provider_spec(provider_id)["api_style"] == "openai"


def _build_openai_client(spec):
    api_key = _read_env(spec["api_key_env"])
    if not api_key:
        raise ValueError(f"{spec['label']} requires {spec['api_key_env']}")

    base_url = _read_env(spec.get("base_url_env")) or spec.get("default_base_url")
    client_kwargs = {"api_key": api_key, "timeout": 60.0, "max_retries": 2}
    if base_url:
        client_kwargs["base_url"] = base_url
    return openai.OpenAI(**client_kwargs)


def _build_ollama_client(spec):
    base_url = _ollama_base_url()
    api_key = _read_env(spec["api_key_env"])

    if not _is_local_ollama(base_url) and not api_key:
        raise ValueError(
            f"{spec['label']} requires {spec['api_key_env']}. "
            "Create a key at https://ollama.com/settings/keys"
        )

    return OllamaClient(base_url=base_url, api_key=api_key)


def _build_provider_config(provider_id):
    spec = _provider_spec(provider_id)
    model = _read_env(spec["model_env"]) or spec["default_model"]

    if spec["api_style"] == "anthropic":
        api_key = _read_env(spec["api_key_env"])
        if not api_key:
            raise ValueError(
                f"{spec['label']} selected but {spec['api_key_env']} is not configured"
            )
        return {
            "client": anthropic.Anthropic(api_key=api_key),
            "provider": provider_id,
            "model": model,
            "api_style": spec["api_style"],
            "label": spec["label"],
        }

    if spec["api_style"] == "ollama":
        if not is_provider_configured(provider_id):
            raise ValueError(
                f"{spec['label']} selected but {spec['api_key_env']} is not configured"
            )
        return {
            "client": _build_ollama_client(spec),
            "provider": provider_id,
            "model": model,
            "api_style": spec["api_style"],
            "label": spec["label"],
        }

    if not is_provider_configured(provider_id):
        raise ValueError(f"{spec['label']} selected but {spec['api_key_env']} is not configured")

    return {
        "client": _build_openai_client(spec),
        "provider": provider_id,
        "model": model,
        "api_style": spec["api_style"],
        "label": spec["label"],
    }


def get_default_models():
    """Return the configured default model name for each LLM provider."""
    models = {}
    for provider_id in LLM_PROVIDER_IDS:
        spec = LLM_PROVIDERS[provider_id]
        models[provider_id] = _read_env(spec["model_env"]) or spec["default_model"]
    return models


def list_ollama_models():
    """Fetch available models from Ollama Cloud or local Ollama."""
    if not is_provider_configured("ollama"):
        return []

    base_url = _ollama_base_url().rstrip("/")
    api_key = _read_env("OLLAMA_API_KEY")
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    models = []
    import ssl

    for path in ("/api/tags", "/v1/models"):
        url = f"{base_url}{path}"
        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            # Allow unverified HTTPS for local/self-signed Ollama instances
            ctx = ssl.create_default_context()
            if _is_local_ollama(base_url):
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(request, timeout=15, context=ctx) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
            continue

        if path == "/api/tags":
            for item in body.get("models", []):
                name = item.get("name") or item.get("model")
                if name:
                    models.append(name)
        else:
            for item in body.get("data", []):
                name = item.get("id") or item.get("name")
                if name:
                    models.append(name)

        if models:
            break

    return sorted(set(models))


def list_provider_models(provider_id):
    """Return selectable models for a provider."""
    provider_id = (provider_id or "").lower().strip()
    if provider_id == "ollama":
        return list_ollama_models()
    if provider_id in LLM_PROVIDERS:
        default = get_default_models().get(provider_id)
        return [default] if default else []
    return []


def setup_llm_client(provider_preference="auto", model_override=None):
    preference = (provider_preference or "auto").lower().strip()
    env_default = _read_env("LLM_PROVIDER") or "auto"
    effective_preference = preference if preference != "auto" else env_default

    if effective_preference != "auto":
        config = _build_provider_config(effective_preference)
    else:
        config = None
        for provider_id in AUTO_PRIORITY:
            if is_provider_configured(provider_id):
                config = _build_provider_config(provider_id)
                break
        if not config:
            raise ValueError(
                "No LLM provider configured. Add an API key for Claude, OpenAI, Kimi, "
                "MiniMax, or Ollama Cloud in your .env file"
            )

    override = (model_override or "").strip()
    if override:
        config["model"] = override

    return config


def create_chat_completion(client, provider_id, model, messages, max_tokens=16000):
    """Create a chat completion using provider-appropriate request parameters."""
    if provider_id == "openai":
        return client.chat.completions.create(
            model=model,
            messages=messages,
            max_completion_tokens=max_tokens,
        )

    return client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
    )
