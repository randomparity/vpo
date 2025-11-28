"""Unit tests for introspector mapping functions."""

import pytest

from video_policy_orchestrator.introspector.mappings import (
    map_channel_layout,
    map_track_type,
)


class TestMapTrackType:
    """Tests for map_track_type function."""

    def test_video(self):
        """Test mapping video codec type."""
        assert map_track_type("video") == "video"

    def test_audio(self):
        """Test mapping audio codec type."""
        assert map_track_type("audio") == "audio"

    def test_subtitle(self):
        """Test mapping subtitle codec type."""
        assert map_track_type("subtitle") == "subtitle"

    def test_attachment(self):
        """Test mapping attachment codec type."""
        assert map_track_type("attachment") == "attachment"

    def test_unknown_returns_other(self):
        """Test that unknown codec types return 'other'."""
        assert map_track_type("data") == "other"
        assert map_track_type("unknown") == "other"
        assert map_track_type("") == "other"

    def test_case_sensitive(self):
        """Test that mapping is case-sensitive."""
        assert map_track_type("Video") == "other"
        assert map_track_type("AUDIO") == "other"


class TestMapChannelLayout:
    """Tests for map_channel_layout function."""

    @pytest.mark.parametrize(
        "channels,expected",
        [
            (1, "mono"),
            (2, "stereo"),
            (6, "5.1"),
            (8, "7.1"),
        ],
    )
    def test_standard_layouts(self, channels, expected):
        """Test standard channel layout mappings."""
        assert map_channel_layout(channels) == expected

    @pytest.mark.parametrize(
        "channels,expected",
        [
            (3, "3ch"),
            (4, "4ch"),
            (5, "5ch"),
            (10, "10ch"),
        ],
    )
    def test_unknown_channel_counts(self, channels, expected):
        """Test that unknown channel counts return 'Nch' format."""
        assert map_channel_layout(channels) == expected

    def test_zero_channels(self):
        """Test zero channels returns '0ch'."""
        assert map_channel_layout(0) == "0ch"
