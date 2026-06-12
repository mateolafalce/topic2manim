"""Tests for captions.py"""
import os
import tempfile
from pathlib import Path
import pytest
from captions import (
    _format_srt_time,
    _estimate_word_durations,
    generate_srt,
)


class TestFormatSrtTime:
    def test_zero(self):
        assert _format_srt_time(0) == "00:00:00,000"

    def test_seconds(self):
        assert _format_srt_time(5.5) == "00:00:05,500"

    def test_minutes(self):
        assert _format_srt_time(125.0) == "00:02:05,000"

    def test_hours(self):
        assert _format_srt_time(3661.0) == "01:01:01,000"


class TestEstimateWordDurations:
    def test_basic(self):
        durations = _estimate_word_durations("the cat sat", 3.0)
        assert len(durations) == 3
        assert abs(sum(durations) - 3.0) < 0.01

    def test_punctuation(self):
        durations = _estimate_word_durations("Hello, world!", 2.0)
        assert len(durations) == 2
        # Punctuation gets more time
        assert durations[1] > durations[0]


class TestGenerateSrt:
    def test_basic_generation(self):
        scenes = [
            {"text": "Hello world this is a test."},
            {"text": "Second scene here."},
        ]
        with tempfile.NamedTemporaryFile(suffix=".srt", delete=False, mode="w") as f:
            output_path = f.name
        try:
            result = generate_srt(scenes, scene_durations=[5.0, 3.0], output_path=output_path)
            assert os.path.exists(result)
            content = Path(result).read_text()
            assert "1" in content
            assert "-->" in content
            assert "Hello world" in content
        finally:
            os.unlink(output_path)

    def test_empty_scenes(self):
        scenes = []
        with tempfile.NamedTemporaryFile(suffix=".srt", delete=False, mode="w") as f:
            output_path = f.name
        try:
            result = generate_srt(scenes, output_path=output_path)
            content = Path(result).read_text()
            assert content.strip() == ""
        finally:
            os.unlink(output_path)
