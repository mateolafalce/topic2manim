"""Shared helpers for provider-specific LLM chat calls."""

import json
import urllib.error
import urllib.request

from llm_providers import create_chat_completion, uses_openai_compatible_api


def _vision_supported(provider: str) -> bool:
    return provider in ("openai", "claude", "ollama")


def complete_llm_vision(
    client,
    provider,
    model,
    system_prompt,
    user_prompt,
    images_base64,
    max_tokens=4000,
):
    """Vision chat — OpenAI, Claude, or Ollama (if model supports images)."""
    if not images_base64:
        return complete_llm(client, provider, model, system_prompt, user_prompt, max_tokens)

    if provider == "openai" or uses_openai_compatible_api(provider):
        content = [{"type": "text", "text": user_prompt}]
        for image_b64 in images_base64:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                }
            )
        response = create_chat_completion(
            client=client,
            provider_id=provider,
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            max_tokens=max_tokens,
        )
        if not response.choices:
            raise Exception(f"No choices returned by {provider} vision call")
        text = response.choices[0].message.content
        if not text:
            raise Exception(f"{provider} returned empty vision response")
        return text.strip()

    if provider == "claude":
        content = []
        for image_b64 in images_base64:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": image_b64,
                    },
                }
            )
        content.append({"type": "text", "text": user_prompt})
        response = client.messages.create(
            model=model,
            max_tokens=min(max_tokens, 4000),
            system=system_prompt,
            messages=[{"role": "user", "content": content}],
        )
        return response.content[0].text.strip()

    if provider == "ollama":
        import ssl

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt, "images": images_base64})
        url = f"{client.base_url}/api/chat"
        payload = json.dumps(
            {
                "model": model,
                "messages": messages,
                "stream": False,
            }
        ).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if client.api_key:
            headers["Authorization"] = f"Bearer {client.api_key}"
        request = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        ctx = ssl.create_default_context()
        lowered = (client.base_url or "").lower()
        if any(token in lowered for token in ("localhost", "127.0.0.1", "host.docker.internal", ":11434")):
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(request, timeout=300, context=ctx) as response:
            body = json.loads(response.read().decode("utf-8"))
        message = body.get("message") or {}
        content = message.get("content") or message.get("thinking")
        if not content:
            raise Exception(f"Ollama vision returned empty content: {body}")
        return content.strip()

    raise Exception(f"Vision critique not supported for provider: {provider}")


def ollama_chat_complete(client, model, system_prompt, user_prompt, max_tokens=16000):
    """Call Ollama's native /api/chat endpoint (used by Ollama Cloud and local Ollama)."""
    import ssl

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    url = f"{client.base_url}/api/chat"
    payload = json.dumps(
        {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
    ).encode("utf-8")

    headers = {"Content-Type": "application/json"}
    if client.api_key:
        headers["Authorization"] = f"Bearer {client.api_key}"

    request = urllib.request.Request(url, data=payload, headers=headers, method="POST")

    # Allow unverified HTTPS for local/self-signed Ollama instances
    ctx = ssl.create_default_context()
    lowered = (client.base_url or "").lower()
    if any(token in lowered for token in ("localhost", "127.0.0.1", "host.docker.internal", ":11434")):
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(request, timeout=300, context=ctx) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise Exception(f"Ollama HTTP {exc.code}: {error_body}") from exc
    except urllib.error.URLError as exc:
        raise Exception(
            f"Ollama connection failed: {exc.reason}. "
            "Check OLLAMA_API_KEY, OLLAMA_BASE_URL, and network access."
        ) from exc

    message = body.get("message") or {}
    content = message.get("content")
    if not content:
        content = message.get("thinking")
    if not content:
        raise Exception(f"Ollama returned empty content: {body}")

    return content.strip()


def complete_llm(client, provider, model, system_prompt, user_prompt, max_tokens=16000):
    """
    Run a chat completion and return response text.

    Supports Anthropic (Claude), OpenAI-compatible providers, and native Ollama.
    """
    if provider == "ollama":
        return ollama_chat_complete(
            client=client,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
        )

    if uses_openai_compatible_api(provider):
        response = create_chat_completion(
            client=client,
            provider_id=provider,
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
        )

        if not response.choices:
            raise Exception(f"No choices returned by {provider}")

        content = response.choices[0].message.content
        if content is None:
            finish_reason = response.choices[0].finish_reason
            raise Exception(f"{provider} returned empty content. Finish reason: {finish_reason}")

        return content.strip()

    response = client.messages.create(
        model=model,
        max_tokens=min(max_tokens, 4000),
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text.strip()
