"""Tests for phase formatting utilities."""

from vpo.core.phase_formatting import (
    _format_audio_synthesis,
    _format_container_change,
    _format_operation_failures,
    _format_track_dispositions,
    _format_track_order,
    _format_transcode_result,
    _format_transcription_results,
    format_phase_details,
)
from vpo.policy.types import ContainerChange, PhaseResult, TrackDisposition


class TestFormatPhaseDetails:
    """Tests for format_phase_details function."""

    def test_format_phase_details_empty_result(self):
        """Empty phase result returns empty list."""
        pr = PhaseResult(
            phase_name="test",
            success=True,
            duration_seconds=0.5,
            operations_executed=(),
            changes_made=0,
        )
        result = format_phase_details(pr)
        assert result == []

    def test_format_phase_details_with_all_fields(self):
        """Phase result with all fields formats correctly."""
        pr = PhaseResult(
            phase_name="test",
            success=True,
            duration_seconds=1.5,
            operations_executed=("container", "audio_filter"),
            changes_made=3,
            container_change=ContainerChange(
                source_format="avi",
                target_format="mkv",
                warnings=(),
                incompatible_tracks=(),
            ),
            track_dispositions=(
                TrackDisposition(
                    track_index=1,
                    track_type="audio",
                    codec="ac3",
                    language="fra",
                    title=None,
                    channels=6,
                    resolution=None,
                    action="REMOVE",
                    reason="Not in preferred languages",
                ),
            ),
            size_before=8_000_000_000,
            size_after=4_000_000_000,
            encoder_type="hardware",
            encoding_fps=120.5,
        )
        result = format_phase_details(pr)

        # Should have container change, track removal, and transcode info
        assert any("Container: avi -> mkv" in line for line in result)
        assert any("Audio removed" in line for line in result)
        assert any("Size:" in line for line in result)
        assert any("Encoder: hardware" in line for line in result)


class TestFormatContainerChange:
    """Tests for _format_container_change function."""

    def test_format_container_change_basic(self):
        """Basic container change without warnings."""
        cc = ContainerChange(
            source_format="avi",
            target_format="mkv",
            warnings=(),
            incompatible_tracks=(),
        )
        result = _format_container_change(cc)
        assert result == ["Container: avi -> mkv"]

    def test_format_container_change_no_change(self):
        """Container with same source and target shows no change."""
        cc = ContainerChange(
            source_format="mkv",
            target_format="mkv",
            warnings=(),
            incompatible_tracks=(),
        )
        result = _format_container_change(cc)
        assert result == ["Container: mkv (no change)"]

    def test_format_container_change_with_warnings(self):
        """Container change with warnings."""
        cc = ContainerChange(
            source_format="mkv",
            target_format="mp4",
            warnings=("PGS subtitles not supported", "Attachment dropped"),
            incompatible_tracks=(2, 3),
        )
        result = _format_container_change(cc)
        assert result[0] == "Container: mkv -> mp4"
        assert "Warning: PGS subtitles not supported" in result[1]
        assert "Warning: Attachment dropped" in result[2]


class TestFormatTrackDispositions:
    """Tests for _format_track_dispositions function."""

    def test_format_track_dispositions_grouped_by_type(self):
        """Track dispositions are grouped by type."""
        dispositions = (
            TrackDisposition(
                track_index=1,
                track_type="audio",
                codec="ac3",
                language="fra",
                title=None,
                channels=6,
                resolution=None,
                action="REMOVE",
                reason="Not in preferred languages",
            ),
            TrackDisposition(
                track_index=2,
                track_type="audio",
                codec="dts",
                language="deu",
                title=None,
                channels=6,
                resolution=None,
                action="REMOVE",
                reason="Not in preferred languages",
            ),
            TrackDisposition(
                track_index=3,
                track_type="subtitle",
                codec="subrip",
                language="spa",
                title=None,
                channels=None,
                resolution=None,
                action="REMOVE",
                reason="Not in preferred languages",
            ),
        )
        result = _format_track_dispositions(dispositions)

        # Should have Audio removed (2): then Subtitle removed (1):
        assert "Audio removed (2):" in result
        assert "Subtitle removed (1):" in result

    def test_format_track_dispositions_minimal_metadata(self):
        """Track with no metadata shows only track number without trailing colon."""
        dispositions = (
            TrackDisposition(
                track_index=1,
                track_type="attachment",
                codec=None,
                language=None,
                title=None,
                channels=None,
                resolution=None,
                action="REMOVE",
                reason="Not needed",
            ),
        )
        result = _format_track_dispositions(dispositions)

        assert "Attachment removed (1):" in result
        # Track line should be "  - Track 1" without trailing colon
        assert "  - Track 1" in result
        # Should NOT have "Track 1:" (with trailing colon and nothing after)
        assert "  - Track 1:" not in result

    def test_format_track_dispositions_with_title(self):
        """Track with title includes it in output."""
        dispositions = (
            TrackDisposition(
                track_index=2,
                track_type="audio",
                codec="ac3",
                language="eng",
                title="Director's Commentary",
                channels=2,
                resolution=None,
                action="REMOVE",
                reason="Commentary track removed",
            ),
        )
        result = _format_track_dispositions(dispositions)

        assert any('"Director\'s Commentary"' in line for line in result)

    def test_format_track_dispositions_keeps_not_shown(self):
        """Tracks with KEEP action are not shown."""
        dispositions = (
            TrackDisposition(
                track_index=0,
                track_type="video",
                codec="hevc",
                language=None,
                title=None,
                channels=None,
                resolution="1920x1080",
                action="KEEP",
                reason="Primary video",
            ),
            TrackDisposition(
                track_index=1,
                track_type="audio",
                codec="dts",
                language="eng",
                title=None,
                channels=6,
                resolution=None,
                action="KEEP",
                reason="Preferred language",
            ),
        )
        result = _format_track_dispositions(dispositions)
        # No removed tracks, should be empty
        assert result == []


class TestFormatTrackOrder:
    """Tests for _format_track_order function."""

    def test_format_track_order_same_order_returns_empty(self):
        """Same order before and after returns empty list."""
        order_change = ((0, 1, 2, 3), (0, 1, 2, 3))
        result = _format_track_order(order_change)
        assert result == []

    def test_format_track_order_different_order(self):
        """Different order returns formatted string."""
        order_change = ((0, 1, 2, 3), (0, 2, 1, 3))
        result = _format_track_order(order_change)
        assert result == ["Track order: [0, 1, 2, 3] -> [0, 2, 1, 3]"]


class TestFormatAudioSynthesis:
    """Tests for _format_audio_synthesis function."""

    def test_format_audio_synthesis_empty(self):
        """Empty tuple returns empty list."""
        result = _format_audio_synthesis(())
        assert result == []

    def test_format_audio_synthesis_single_track(self):
        """Single synthesized track is formatted correctly."""
        tracks = ("eng stereo AAC",)
        result = _format_audio_synthesis(tracks)
        assert result == [
            "Audio synthesized (1):",
            "  - eng stereo AAC",
        ]

    def test_format_audio_synthesis_multiple_tracks(self):
        """Multiple synthesized tracks are formatted correctly."""
        tracks = ("eng stereo AAC", "fra stereo AAC")
        result = _format_audio_synthesis(tracks)
        assert result == [
            "Audio synthesized (2):",
            "  - eng stereo AAC",
            "  - fra stereo AAC",
        ]


class TestFormatTranscodeResult:
    """Tests for _format_transcode_result function."""

    def test_format_transcode_result_with_all_fields(self):
        """Transcode result with all fields formats correctly."""
        result = _format_transcode_result(
            size_before=8_000_000_000,
            size_after=4_000_000_000,
            encoder_type="hardware",
            encoding_fps=120.5,
        )

        assert any("Size:" in line and "-50.0%" in line for line in result)
        assert "Encoder: hardware" in result
        assert "Speed: 120.5 fps" in result

    def test_format_transcode_result_size_increase(self):
        """Transcode result with size increase shows positive percentage."""
        result = _format_transcode_result(
            size_before=4_000_000_000,
            size_after=5_000_000_000,
            encoder_type="software",
            encoding_fps=30.0,
        )

        assert any("+25.0%" in line for line in result)
        assert "Encoder: software" in result

    def test_format_transcode_result_size_zero_no_crash(self):
        """Transcode result with size_before=0 does not crash."""
        result = _format_transcode_result(
            size_before=0,
            size_after=1_000_000,
            encoder_type=None,
            encoding_fps=None,
        )

        # Should have size line without percentage
        assert len(result) >= 1
        assert "Size:" in result[0]
        # Should not crash on division by zero

    def test_format_transcode_result_no_encoder_type(self):
        """Transcode result without encoder type omits that line."""
        result = _format_transcode_result(
            size_before=8_000_000_000,
            size_after=4_000_000_000,
            encoder_type=None,
            encoding_fps=60.0,
        )

        assert not any("Encoder:" in line for line in result)
        assert "Speed: 60.0 fps" in result

    def test_format_transcode_result_no_fps(self):
        """Transcode result without FPS omits speed line."""
        result = _format_transcode_result(
            size_before=8_000_000_000,
            size_after=4_000_000_000,
            encoder_type="hardware",
            encoding_fps=None,
        )

        assert not any("Speed:" in line for line in result)
        assert "Encoder: hardware" in result

    def test_format_transcode_result_zero_fps(self):
        """Transcode result with FPS=0 omits speed line."""
        result = _format_transcode_result(
            size_before=8_000_000_000,
            size_after=4_000_000_000,
            encoder_type="hardware",
            encoding_fps=0.0,
        )

        assert not any("Speed:" in line for line in result)


class TestFormatTranscriptionResults:
    """Tests for _format_transcription_results function."""

    def test_format_transcription_results_empty(self):
        """Empty tuple returns empty list."""
        result = _format_transcription_results(())
        assert result == []

    def test_format_transcription_results_single_track(self):
        """Single transcription result is formatted correctly."""
        results = ((1, "eng", 0.94, "main"),)
        result = _format_transcription_results(results)
        assert result == [
            "Transcription analyzed (1):",
            "  - Track 1: eng (main, 94%)",
        ]

    def test_format_transcription_results_multiple_tracks(self):
        """Multiple transcription results are formatted correctly."""
        results = (
            (1, "eng", 0.94, "main"),
            (2, "fra", 0.87, "alternate"),
        )
        result = _format_transcription_results(results)
        assert result == [
            "Transcription analyzed (2):",
            "  - Track 1: eng (main, 94%)",
            "  - Track 2: fra (alternate, 87%)",
        ]

    def test_format_transcription_results_unknown_language(self):
        """Transcription result with None language shows 'unknown'."""
        results = ((3, None, 0.45, "non_speech"),)
        result = _format_transcription_results(results)
        assert result == [
            "Transcription analyzed (1):",
            "  - Track 3: unknown (non_speech, 45%)",
        ]

    def test_format_transcription_results_low_confidence(self):
        """Transcription result with low confidence rounds correctly."""
        results = ((1, "eng", 0.156, "main"),)
        result = _format_transcription_results(results)
        assert result == [
            "Transcription analyzed (1):",
            "  - Track 1: eng (main, 15%)",
        ]

    def test_format_transcription_results_commentary_type(self):
        """Transcription result with commentary track type."""
        results = ((2, "eng", 0.92, "commentary"),)
        result = _format_transcription_results(results)
        assert result == [
            "Transcription analyzed (1):",
            "  - Track 2: eng (commentary, 92%)",
        ]


class TestFormatOperationFailures:
    """Tests for _format_operation_failures function."""

    def test_format_operation_failures_empty(self):
        """Empty tuple returns empty list."""
        result = _format_operation_failures(())
        assert result == []

    def test_format_operation_failures_single(self):
        """Single failure is formatted correctly."""
        failures = (("container", "File not found"),)
        result = _format_operation_failures(failures)
        assert result == [
            "Failures (1):",
            "  - container: File not found",
        ]

    def test_format_operation_failures_multiple(self):
        """Multiple failures are formatted correctly."""
        failures = (
            ("container", "Incompatible codec"),
            ("audio_filter", "No audio tracks"),
        )
        result = _format_operation_failures(failures)
        assert result == [
            "Failures (2):",
            "  - container: Incompatible codec",
            "  - audio_filter: No audio tracks",
        ]

    def test_format_operation_failures_long_message_truncated(self):
        """Long error messages are truncated to 80 chars."""
        long_msg = "A" * 100
        failures = (("transcode", long_msg),)
        result = _format_operation_failures(failures)
        assert result[1] == "  - transcode: " + "A" * 77 + "..."
