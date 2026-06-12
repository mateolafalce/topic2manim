"""Tests for JSON extraction from LLM responses."""

import json

import pytest

from json_utils import extract_json_from_llm_response


def test_extract_plain_json():
    raw = '{"scenes": [{"text": "Hello", "animation": "Title"}]}'
    result = extract_json_from_llm_response(raw)
    assert result["scenes"][0]["text"] == "Hello"


def test_extract_json_array():
    raw = '[{"text": "A", "animation": "B"}, {"text": "C", "animation": "D"}]'
    result = extract_json_from_llm_response(raw)
    assert len(result) == 2
    assert result[1]["text"] == "C"


def test_extract_json_with_markdown_fence():
    raw = """Here is the script:

```json
{"text": "Hello", "animation": "Title"}
```
"""
    result = extract_json_from_llm_response(raw)
    assert result["text"] == "Hello"


def test_extract_json_with_generic_fence():
    raw = """```
[{"text": "Hello", "animation": "Title"}]
```"""
    result = extract_json_from_llm_response(raw)
    assert len(result) == 1


def test_extract_json_object_with_prose():
    raw = """Sure! Here is the script you requested:

{"text": "Hello", "animation": "Title"}

Let me know if you need anything else!"""
    result = extract_json_from_llm_response(raw)
    assert result["text"] == "Hello"


def test_extract_json_array_with_prose():
    raw = """Here are the scenes:

[{"text": "Scene 1", "animation": "A"}, {"text": "Scene 2", "animation": "B"}]

Hope this helps!"""
    result = extract_json_from_llm_response(raw)
    assert len(result) == 2


def test_extract_empty_response_raises():
    with pytest.raises(ValueError, match="Empty LLM response"):
        extract_json_from_llm_response("")


def test_extract_empty_response_none_raises():
    with pytest.raises(ValueError, match="Empty LLM response"):
        extract_json_from_llm_response(None)


def test_extract_invalid_json_raises():
    raw = "This is not JSON at all"
    with pytest.raises((ValueError, json.JSONDecodeError)):
        extract_json_from_llm_response(raw)
