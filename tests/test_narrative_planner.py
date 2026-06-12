"""Tests for narrative arc planning."""

from unittest.mock import MagicMock, patch

import pytest

from narrative_planner import generate_narrative_plan, plan_to_prompt_context


def test_plan_to_prompt_context():
    plan = {
        "title": "Test Title",
        "hook": "What if X?",
        "misconception": "People think Y",
        "aha_moment": "Actually Z",
        "emotional_arc": "wonder",
        "color_theme": "classic_3b1b",
        "pacing_notes": "Slow at the proof",
        "scene_beats": [
            {
                "scene_number": 1,
                "purpose": "hook",
                "narration_summary": "Ask a question",
                "visual_approach": "Animated dot",
                "estimated_seconds": 15,
            }
        ],
        "visual_metaphors": {"derivative": "speedometer"},
    }
    ctx = plan_to_prompt_context(plan)
    assert "NARRATIVE ARC" in ctx
    assert "What if X?" in ctx
    assert "Actually Z" in ctx
    assert "Scene 1" in ctx
    assert "speedometer" in ctx


@patch("narrative_planner.complete_llm")
def test_generate_narrative_plan_success(mock_complete_llm):
    mock_complete_llm.return_value = """
    {
        "title": "The Surprising Truth",
        "hook": "What if everything you know is wrong?",
        "misconception": "Linear growth",
        "aha_moment": "It's exponential",
        "emotional_arc": "wonder",
        "scene_beats": [
            {"scene_number": 1, "purpose": "hook", "narration_summary": "Ask", "visual_approach": "Graph", "estimated_seconds": 10, "key_visual": "Curve", "pause_after": true}
        ],
        "visual_metaphors": {"growth": "bacteria colony"},
        "color_theme": "classic_3b1b",
        "estimated_total_seconds": 120,
        "pacing_notes": "Slow at reveal"
    }
    """

    plan = generate_narrative_plan(
        client=MagicMock(), topic="Exponential Growth", provider="openai", model="gpt-4o"
    )
    assert plan is not None
    assert plan["title"] == "The Surprising Truth"
    assert plan["hook"] == "What if everything you know is wrong?"
    assert len(plan["scene_beats"]) == 1
    assert plan["scene_beats"][0]["scene_number"] == 1
    mock_complete_llm.assert_called_once()


@patch("narrative_planner.complete_llm")
def test_generate_narrative_plan_invalid_json(mock_complete_llm):
    mock_complete_llm.return_value = "not json"
    plan = generate_narrative_plan(
        client=MagicMock(), topic="Test", provider="openai", model="gpt-4o"
    )
    assert plan is None


@patch("narrative_planner.complete_llm")
def test_generate_narrative_plan_missing_keys(mock_complete_llm):
    mock_complete_llm.return_value = '{"title": "Only title"}'
    plan = generate_narrative_plan(
        client=MagicMock(), topic="Test", provider="openai", model="gpt-4o"
    )
    assert plan is None


@patch("narrative_planner.complete_llm")
def test_generate_narrative_plan_markdown_fences(mock_complete_llm):
    mock_complete_llm.return_value = (
        '```json\n'
        '{"title": "T", "hook": "H", "aha_moment": "A", "scene_beats": [{"scene_number": 1, "purpose": "hook", "narration_summary": "N", "visual_approach": "V", "estimated_seconds": 10, "key_visual": "K", "pause_after": true}]}'
        '\n```'
    )
    plan = generate_narrative_plan(
        client=MagicMock(), topic="Test", provider="openai", model="gpt-4o"
    )
    assert plan is not None
    assert plan["title"] == "T"
