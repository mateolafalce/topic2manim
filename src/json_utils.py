import json
import re


def extract_json_from_llm_response(response_text):
    """
    Extract and parse JSON from an LLM response.

    Handles markdown fences, leading/trailing prose, and JSON arrays/objects.
    """
    if not response_text:
        raise ValueError("Empty LLM response")

    text = response_text.strip()

    if "```json" in text:
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            text = match.group(1).strip()
    elif "```" in text:
        match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            text = match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    array_start = text.find("[")
    array_end = text.rfind("]")
    if array_start != -1 and array_end > array_start:
        return json.loads(text[array_start : array_end + 1])

    object_start = text.find("{")
    object_end = text.rfind("}")
    if object_start != -1 and object_end > object_start:
        return json.loads(text[object_start : object_end + 1])

    raise ValueError(f"Could not parse JSON from LLM response: {text[:300]}")
