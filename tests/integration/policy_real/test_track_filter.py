"""Integration tests for track filtering using real video files.

These tests verify that track filtering operations (keeping/removing tracks)
work correctly on actual video files.

Tier 2: Track operations that require remuxing.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from video_policy_orchestrator.executor.mkvmerge import MkvmergeExecutor
from video_policy_orchestrator.policy.models import (
    Plan,
    TrackDisposition,
)

if TYPE_CHECKING:
    from video_policy_orchestrator.introspector.ffprobe import FFprobeIntrospector

from .conftest import get_audio_tracks, get_subtitle_tracks

pytestmark = [
    pytest.mark.integration,
]


def make_track_disposition(track, action: str, reason: str) -> TrackDisposition:
    """Helper to create TrackDisposition from a track."""
    resolution = None
    if track.track_type == "video" and track.width and track.height:
        resolution = f"{track.width}x{track.height}"

    return TrackDisposition(
        track_index=track.index,
        track_type=track.track_type,
        codec=track.codec,
        language=track.language,
        title=track.title,
        channels=getattr(track, "channels", None),
        resolution=resolution,
        action=action,
        reason=reason,
    )


class TestAudioTrackFiltering:
    """Test audio track filtering operations."""

    def test_filter_audio_by_language(
        self,
        generated_multi_audio: Path | None,
        copy_video,
        introspector: FFprobeIntrospector,
        mkvmerge_available: bool,
    ) -> None:
        """Only specified language audio tracks should be kept."""
        if not mkvmerge_available:
            pytest.skip("mkvmerge not available")
        if generated_multi_audio is None:
            pytest.skip("Test video not available")

        # Make a working copy since executor modifies files in-place
        working_copy = copy_video(generated_multi_audio, "filter_audio.mkv")

        original = introspector.get_file_info(working_copy)
        original_audio = get_audio_tracks(original)

        assert len(original_audio) >= 3, "Expected at least 3 audio tracks"

        # Keep only English and Japanese
        dispositions = []
        for track in original.tracks:
            if track.track_type == "video":
                dispositions.append(make_track_disposition(track, "KEEP", "video"))
            elif track.track_type == "audio":
                if track.language in ("eng", "jpn"):
                    dispositions.append(
                        make_track_disposition(
                            track,
                            "KEEP",
                            f"language {track.language} matches preference",
                        )
                    )
                else:
                    dispositions.append(
                        make_track_disposition(
                            track,
                            "REMOVE",
                            f"language {track.language} not in preference",
                        )
                    )

        plan = Plan(
            file_id="test",
            file_path=working_copy,
            policy_version=3,
            requires_remux=True,
            actions=(),
            track_dispositions=tuple(dispositions),
            tracks_kept=len([d for d in dispositions if d.action == "KEEP"]),
            tracks_removed=len([d for d in dispositions if d.action == "REMOVE"]),
        )

        executor = MkvmergeExecutor()
        result = executor.execute(
            plan,
            keep_backup=False,
            keep_original=False,
        )
        assert result.success, f"Execution failed: {result.error}"

        # Verify
        modified = introspector.get_file_info(working_copy)
        modified_audio = get_audio_tracks(modified)

        # Should only have 2 audio tracks now
        assert len(modified_audio) == 2, (
            f"Expected 2 audio tracks, got {len(modified_audio)}"
        )

        # Should be English and Japanese
        languages = {t.language for t in modified_audio}
        assert languages == {"eng", "jpn"}, f"Expected eng and jpn, got {languages}"

    def test_keep_all_audio_tracks(
        self,
        generated_multi_audio: Path | None,
        copy_video,
        introspector: FFprobeIntrospector,
        mkvmerge_available: bool,
    ) -> None:
        """All audio tracks should be kept when filter keeps all."""
        if not mkvmerge_available:
            pytest.skip("mkvmerge not available")
        if generated_multi_audio is None:
            pytest.skip("Test video not available")

        # Make a working copy since executor modifies files in-place
        working_copy = copy_video(generated_multi_audio, "keep_all.mkv")

        original = introspector.get_file_info(working_copy)
        original_audio = get_audio_tracks(original)

        # Keep all tracks
        dispositions = []
        for track in original.tracks:
            dispositions.append(make_track_disposition(track, "KEEP", "keep all"))

        plan = Plan(
            file_id="test",
            file_path=working_copy,
            policy_version=3,
            requires_remux=True,
            actions=(),
            track_dispositions=tuple(dispositions),
            tracks_kept=len(dispositions),
            tracks_removed=0,
        )

        executor = MkvmergeExecutor()
        result = executor.execute(
            plan,
            keep_backup=False,
            keep_original=False,
        )
        assert result.success

        modified = introspector.get_file_info(working_copy)
        modified_audio = get_audio_tracks(modified)

        assert len(modified_audio) == len(original_audio)


class TestSubtitleTrackFiltering:
    """Test subtitle track filtering operations."""

    def test_filter_subtitles_by_language(
        self,
        generated_multi_subtitle: Path | None,
        copy_video,
        introspector: FFprobeIntrospector,
        mkvmerge_available: bool,
    ) -> None:
        """Only specified language subtitle tracks should be kept."""
        if not mkvmerge_available:
            pytest.skip("mkvmerge not available")
        if generated_multi_subtitle is None:
            pytest.skip("Test video not available")

        # Make a working copy since executor modifies files in-place
        working_copy = copy_video(generated_multi_subtitle, "filtered_subs.mkv")

        original = introspector.get_file_info(working_copy)
        original_subs = get_subtitle_tracks(original)

        if len(original_subs) < 2:
            pytest.skip("Not enough subtitle tracks for filtering test")

        # Keep only English subtitles
        dispositions = []
        for track in original.tracks:
            if track.track_type in ("video", "audio"):
                dispositions.append(
                    make_track_disposition(track, "KEEP", "non-subtitle")
                )
            elif track.track_type == "subtitle":
                if track.language == "eng":
                    dispositions.append(
                        make_track_disposition(track, "KEEP", "English subtitle")
                    )
                else:
                    dispositions.append(
                        make_track_disposition(
                            track,
                            "REMOVE",
                            f"language {track.language} not preferred",
                        )
                    )

        plan = Plan(
            file_id="test",
            file_path=working_copy,
            policy_version=3,
            requires_remux=True,
            actions=(),
            track_dispositions=tuple(dispositions),
            tracks_kept=len([d for d in dispositions if d.action == "KEEP"]),
            tracks_removed=len([d for d in dispositions if d.action == "REMOVE"]),
        )

        executor = MkvmergeExecutor()
        result = executor.execute(
            plan,
            keep_backup=False,
            keep_original=False,
        )
        assert result.success

        modified = introspector.get_file_info(working_copy)
        modified_subs = get_subtitle_tracks(modified)

        # All remaining subtitles should be English
        for sub in modified_subs:
            assert sub.language == "eng", f"Expected eng, got {sub.language}"

    def test_preserve_forced_subtitle(
        self,
        generated_multi_subtitle: Path | None,
        copy_video,
        introspector: FFprobeIntrospector,
        mkvmerge_available: bool,
    ) -> None:
        """Forced subtitles should be preserved even when filtering."""
        if not mkvmerge_available:
            pytest.skip("mkvmerge not available")
        if generated_multi_subtitle is None:
            pytest.skip("Test video not available")

        # Make a working copy since executor modifies files in-place
        working_copy = copy_video(generated_multi_subtitle, "forced_only.mkv")

        original = introspector.get_file_info(working_copy)
        original_subs = get_subtitle_tracks(original)

        # Find forced subtitle
        forced_sub = next((s for s in original_subs if s.is_forced), None)
        if forced_sub is None:
            pytest.skip("No forced subtitle found in test file")

        # Keep video, audio, and only forced subtitles
        dispositions = []
        for track in original.tracks:
            if track.track_type in ("video", "audio"):
                dispositions.append(
                    make_track_disposition(track, "KEEP", "non-subtitle")
                )
            elif track.track_type == "subtitle":
                if track.is_forced:
                    dispositions.append(
                        make_track_disposition(
                            track,
                            "KEEP",
                            "forced subtitle preserved",
                        )
                    )
                else:
                    dispositions.append(
                        make_track_disposition(track, "REMOVE", "non-forced subtitle")
                    )

        plan = Plan(
            file_id="test",
            file_path=working_copy,
            policy_version=3,
            requires_remux=True,
            actions=(),
            track_dispositions=tuple(dispositions),
            tracks_kept=len([d for d in dispositions if d.action == "KEEP"]),
            tracks_removed=len([d for d in dispositions if d.action == "REMOVE"]),
        )

        executor = MkvmergeExecutor()
        result = executor.execute(
            plan,
            keep_backup=False,
            keep_original=False,
        )
        assert result.success

        modified = introspector.get_file_info(working_copy)
        modified_subs = get_subtitle_tracks(modified)

        # Should have at least the forced subtitle
        assert len(modified_subs) >= 1, "Expected at least 1 subtitle (forced)"

        # The kept subtitle should be forced
        kept_forced = [s for s in modified_subs if s.is_forced]
        assert len(kept_forced) >= 1, "Forced subtitle should be preserved"

    def test_remove_all_subtitles(
        self,
        generated_multi_subtitle: Path | None,
        copy_video,
        introspector: FFprobeIntrospector,
        mkvmerge_available: bool,
    ) -> None:
        """All subtitles should be removed when configured."""
        if not mkvmerge_available:
            pytest.skip("mkvmerge not available")
        if generated_multi_subtitle is None:
            pytest.skip("Test video not available")

        # Make a working copy since executor modifies files in-place
        working_copy = copy_video(generated_multi_subtitle, "no_subs.mkv")

        original = introspector.get_file_info(working_copy)

        # Keep video and audio, remove all subtitles
        dispositions = []
        for track in original.tracks:
            if track.track_type in ("video", "audio"):
                dispositions.append(
                    make_track_disposition(track, "KEEP", "non-subtitle")
                )
            elif track.track_type == "subtitle":
                dispositions.append(
                    make_track_disposition(track, "REMOVE", "remove all subtitles")
                )

        plan = Plan(
            file_id="test",
            file_path=working_copy,
            policy_version=3,
            requires_remux=True,
            actions=(),
            track_dispositions=tuple(dispositions),
            tracks_kept=len([d for d in dispositions if d.action == "KEEP"]),
            tracks_removed=len([d for d in dispositions if d.action == "REMOVE"]),
        )

        executor = MkvmergeExecutor()
        result = executor.execute(
            plan,
            keep_backup=False,
            keep_original=False,
        )
        assert result.success

        modified = introspector.get_file_info(working_copy)
        modified_subs = get_subtitle_tracks(modified)

        assert len(modified_subs) == 0, (
            f"Expected 0 subtitles, got {len(modified_subs)}"
        )


class TestCombinedFiltering:
    """Test combined audio and subtitle filtering."""

    def test_filter_both_audio_and_subtitles(
        self,
        generated_multi_subtitle: Path | None,
        copy_video,
        introspector: FFprobeIntrospector,
        mkvmerge_available: bool,
    ) -> None:
        """Both audio and subtitle filtering should work together."""
        if not mkvmerge_available:
            pytest.skip("mkvmerge not available")
        if generated_multi_subtitle is None:
            pytest.skip("Test video not available")

        # Make a working copy since executor modifies files in-place
        working_copy = copy_video(generated_multi_subtitle, "english_only.mkv")

        original = introspector.get_file_info(working_copy)

        # Build dispositions: keep video, English audio only, English subtitles only
        dispositions = []
        for track in original.tracks:
            if track.track_type == "video":
                dispositions.append(make_track_disposition(track, "KEEP", "video"))
            elif track.track_type == "audio":
                if track.language == "eng":
                    dispositions.append(
                        make_track_disposition(track, "KEEP", "English audio")
                    )
                else:
                    dispositions.append(
                        make_track_disposition(track, "REMOVE", "non-English audio")
                    )
            elif track.track_type == "subtitle":
                if track.language == "eng":
                    dispositions.append(
                        make_track_disposition(track, "KEEP", "English subtitle")
                    )
                else:
                    dispositions.append(
                        make_track_disposition(track, "REMOVE", "non-English subtitle")
                    )

        plan = Plan(
            file_id="test",
            file_path=working_copy,
            policy_version=3,
            requires_remux=True,
            actions=(),
            track_dispositions=tuple(dispositions),
            tracks_kept=len([d for d in dispositions if d.action == "KEEP"]),
            tracks_removed=len([d for d in dispositions if d.action == "REMOVE"]),
        )

        executor = MkvmergeExecutor()
        result = executor.execute(
            plan,
            keep_backup=False,
            keep_original=False,
        )
        assert result.success

        modified = introspector.get_file_info(working_copy)
        modified_audio = get_audio_tracks(modified)
        modified_subs = get_subtitle_tracks(modified)

        # All audio should be English
        for track in modified_audio:
            assert track.language == "eng", (
                f"Expected English audio, got {track.language}"
            )

        # All subtitles should be English
        for track in modified_subs:
            assert track.language == "eng", (
                f"Expected English subtitle, got {track.language}"
            )
