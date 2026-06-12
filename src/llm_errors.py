def format_llm_error(error):
    """Turn raw LLM API exceptions into actionable user-facing messages."""
    message = str(error)

    if "suspended due to insufficient balance" in message.lower():
        return (
            "Kimi account is suspended due to insufficient balance. "
            "Recharge at platform.kimi.ai or use Ollama instead."
        )

    if "insufficient_balance" in message or "insufficient balance" in message.lower():
        return (
            "This LLM account has insufficient balance. "
            "Add credits or switch to Ollama in the LLM provider dropdown."
        )

    if "invalid_authentication" in message or "Invalid Authentication" in message:
        provider_hint = _guess_provider_from_error(message)
        return (
            f"Invalid API key for {provider_hint}. "
            "Check the key in your .env file and restart the container."
        )

    if "401" in message and "api" in message.lower():
        return f"Authentication failed for LLM API: {message[:200]}"

    if "402" in message:
        return f"LLM billing error: {message[:200]}"

    if "Ollama connection failed" in message or "Ollama HTTP" in message:
        return message

    if "Could not parse JSON" in message:
        return f"LLM returned invalid JSON. Try again or switch provider. ({message[:120]})"

    return message


def _guess_provider_from_error(message):
    lowered = message.lower()
    if "moonshot" in lowered or "kimi" in lowered:
        return "Kimi (Moonshot)"
    if "minimax" in lowered:
        return "MiniMax"
    if "openai" in lowered:
        return "OpenAI"
    if "anthropic" in lowered or "claude" in lowered:
        return "Claude"
    return "the selected LLM provider"
