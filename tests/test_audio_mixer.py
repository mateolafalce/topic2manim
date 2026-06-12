"""Tests for audio_mixer.py"""
import pytest
from audio_mixer import infer_mood, pick_music_track, map_visual_events_to_sfx


class TestInferMood:
    def test_calm_default(self):
        assert infer_mood("Introduction to Algebra") == "calm"

    def test_dramatic_events(self):
        assert infer_mood("Anything", visual_events=["show_explosion"]) == "dramatic"

    def test_playful_topic(self):
        assert infer_mood("Fun math games") == "playful"

    def test_mysterious_topic(self):
        assert infer_mood("Black holes and quantum physics") == "mysterious"

    def test_upbeat_topic(self):
        assert infer_mood("Breakthrough innovation in science") == "upbeat"

    def test_dramatic_topic(self):
        assert infer_mood("The crisis of climate change") == "dramatic"


class TestPickMusicTrack:
    def test_no_tracks_available(self):
        result = pick_music_track("nonexistent_mood")
        assert result is None

    def test_no_files_on_disk(self):
        # Pick a mood that has entries but files don't exist
        result = pick_music_track("calm")
        assert result is None  # media/audio/music/ doesn't exist in test env


class TestMapVisualEventsToSfx:
    def test_title_whoosh(self):
        events = ["show_title"]
        result = map_visual_events_to_sfx(events, 0.0)
        assert len(result) == 1
        assert result[0]["sfx_id"] == "whoosh"
        assert result[0]["timestamp"] == 0.5

    def test_multiple_events(self):
        events = ["show_title", "show_equation", "highlight_term"]
        result = map_visual_events_to_sfx(events, 10.0)
        assert len(result) == 3
        assert result[0]["timestamp"] == 10.5
        assert result[1]["timestamp"] == 11.8  # 10.5 + 1.5 + 0.3 - wait, current_time advances 1.5 each iteration
        assert result[2]["timestamp"] == 13.0
