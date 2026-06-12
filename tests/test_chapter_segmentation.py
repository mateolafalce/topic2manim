"""Tests for chapter_segmentation.py"""
import pytest
from chapter_segmentation import (
    _heuristic_segment,
    _split_by_content,
    auto_segment_chapters,
    chapters_to_html_metadata,
)


class TestHeuristicSegment:
    def test_explicit_chapters(self):
        scenes = [
            {"text": "Intro text", "chapter": "Introduction"},
            {"text": "More intro", "chapter": "Introduction"},
            {"text": "Core concept", "chapter": "Main Idea"},
            {"text": "Details", "chapter": "Main Idea"},
        ]
        result = _heuristic_segment(scenes)
        assert len(result) == 2
        assert result[0]["title"] == "Introduction"
        assert result[0]["scenes"] == [0, 1]
        assert result[1]["title"] == "Main Idea"
        assert result[1]["scenes"] == [2, 3]

    def test_title_shift(self):
        scenes = [
            {"text": "About derivatives", "title": "Derivatives"},
            {"text": "How to compute", "title": "Derivatives"},
            {"text": "Now integrals", "title": "Integrals"},
            {"text": "Integration rules", "title": "Integrals"},
        ]
        result = _heuristic_segment(scenes)
        assert len(result) >= 2

    def test_small_video(self):
        scenes = [{"text": "One"}, {"text": "Two"}]
        result = _heuristic_segment(scenes)
        assert len(result) == 1


class TestSplitByContent:
    def test_splits(self):
        scenes = [
            {"text": "Introduction to algebra and equations"},
            {"text": "Solving linear equations step by step"},
            {"text": "Quadratic formulas and parabolas"},
            {"text": "Graphing quadratic functions"},
        ]
        result = _split_by_content(scenes)
        assert len(result) == 2
        assert len(result[0]["scenes"]) == 2
        assert len(result[1]["scenes"]) == 2


class TestAutoSegmentChapters:
    def test_no_scenes(self):
        assert auto_segment_chapters([]) == []

    def test_two_scenes(self):
        scenes = [{"text": "A"}, {"text": "B"}]
        result = auto_segment_chapters(scenes)
        assert len(result) == 1
        assert result[0]["scenes"] == [0, 1]

    def test_fallback_heuristic(self):
        scenes = [
            {"text": "Scene one about derivatives"},
            {"text": "Scene two about derivatives"},
            {"text": "Scene three about integrals"},
            {"text": "Scene four about integrals"},
        ]
        result = auto_segment_chapters(scenes, client=None, use_llm=False)
        assert len(result) >= 1


class TestChaptersToHtmlMetadata:
    def test_basic(self):
        chapters = [
            {"title": "Intro", "scenes": [0, 1]},
            {"title": "Core", "scenes": [2]},
        ]
        durations = [5.0, 6.0, 8.0]
        meta = chapters_to_html_metadata(chapters, durations)
        assert len(meta) == 2
        assert meta[0]["title"] == "Intro"
        assert meta[0]["start"] == 0.0
        assert meta[0]["end"] == 11.0
        assert meta[1]["start"] == 11.0
        assert meta[1]["end"] == 19.0
