"""Tests for quality_metrics.py"""
import pytest
from quality_metrics import (
    count_syllables,
    flesch_reading_ease,
    flesch_kincaid_grade,
    analyze_script_readability,
    estimate_wpm,
    analyze_pacing,
    compute_retention_score,
    analyze_full_script,
)


class TestCountSyllables:
    def test_simple_words(self):
        assert count_syllables("cat") == 1
        assert count_syllables("hello") == 2
        assert count_syllables("beautiful") == 3

    def test_silent_e(self):
        assert count_syllables("like") == 1
        assert count_syllables("time") == 1

    def test_empty(self):
        assert count_syllables("") == 0


class TestFleschReadingEase:
    def test_very_easy(self):
        text = "The cat sat on the mat. The dog ran fast."
        score = flesch_reading_ease(text)
        assert score > 80

    def test_difficult(self):
        text = "The constitutional ramifications of jurisprudential hermeneutics necessitate a comprehensive epistemological framework."
        score = flesch_reading_ease(text)
        assert score < 30


class TestAnalyzeScriptReadability:
    def test_basic_metrics(self):
        text = "The cat sat. The dog ran. The bird flew."
        result = analyze_script_readability(text)
        assert "flesch_reading_ease" in result
        assert "word_count" in result
        assert result["word_count"] == 9
        assert "recommended_audience" in result


class TestEstimateWPM:
    def test_basic(self):
        assert estimate_wpm("one two three four five", 60) == 5.0

    def test_zero_duration(self):
        assert estimate_wpm("hello world", 0) == 0.0


class TestAnalyzePacing:
    def test_optimal_pacing(self):
        scenes = [{"text": "This is a test scene with exactly ten words here."}]
        durations = [6.0]  # ~100 WPM
        result = analyze_pacing(scenes, durations)
        assert result[0]["pace"] == "optimal"

    def test_fast_pacing(self):
        scenes = [{"text": "This is a test scene with exactly ten words here."}]
        durations = [2.0]  # ~300 WPM
        result = analyze_pacing(scenes, durations)
        assert result[0]["pace"] == "too_fast"


class TestComputeRetentionScore:
    def test_with_hook_and_metaphor(self):
        pacing = [{"pace": "optimal"}]
        result = compute_retention_score(
            "What if everything you knew was wrong? Imagine a world where...",
            pacing,
            has_hook=True,
            has_visual_metaphor=True,
            scene_count=6,
        )
        assert 50 < result["predicted_retention"] <= 95
        assert result["hook_bonus"] > 0

    def test_without_hook(self):
        pacing = [{"pace": "optimal"}]
        result = compute_retention_score(
            "Today we will learn about calculus.",
            pacing,
            has_hook=False,
            has_visual_metaphor=False,
            scene_count=6,
        )
        assert result["hook_bonus"] == 0


class TestAnalyzeFullScript:
    def test_complete_analysis(self):
        scenes = [
            {"text": "What if everything you knew about math was completely wrong?"},
            {"text": "Most people think addition is simple, like combining apples."},
            {"text": "But imagine a world where numbers behave like waves instead."},
        ]
        durations = [5.0, 6.0, 7.0]
        result = analyze_full_script(scenes, durations, topic="Math")
        assert "retention_prediction" in result
        assert "readability" in result
        assert "pacing" in result
        assert result["retention_prediction"]["has_hook"] is True
        assert result["retention_prediction"]["has_visual_metaphor"] is True

    def test_suggestions(self):
        scenes = [{"text": "Today we will learn about calculus. It is very hard."}]
        durations = [3.0]
        result = analyze_full_script(scenes, durations)
        assert len(result["suggestions"]) > 0
