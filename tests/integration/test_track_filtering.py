"""Integration tests for track filtering functionality.

Tests the end-to-end flow of audio, subtitle, and attachment filtering
through the evaluator and executor.
"""

import sqlite3
from pathlib import Path

import pytest

from video_policy_orchestrator.db.models import TrackInfo
from video_policy_orchestrator.db.schema import create_schema
from video_policy_orchestrator.policy.evaluator import compute_track_dispositions
from video_policy_orchestrator.policy.exceptions import InsufficientTracksError
from video_policy_orchestrator.policy.models import (
    AudioFilterConfig,
    LanguageFallbackConfig,
    Plan,
    PolicySchema,
    TrackDisposition,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def v3_audio_filter_policy(temp_dir: Path) -> Path:
    """Create a V3 policy file with audio filtering."""
    policy_path = temp_dir / "audio-filter-policy.yaml"
    policy_path.write_text("""
schema_version: 3
track_order:
  - video
  - audio_main
  - subtitle_main
audio_language_preference:
  - eng
subtitle_language_preference:
  - eng
audio_filter:
  languages:
    - eng
    - und
  minimum: 1
  fallback:
    mode: keep_first
default_flags:
  set_first_video_default: true
  set_preferred_audio_default: true
  set_preferred_subtitle_default: false
  clear_other_defaults: true
""")
    return policy_path


@pytest.fixture
def v3_strict_audio_filter_policy(temp_dir: Path) -> Path:
    """Create a V3 policy file with strict audio filtering (no fallback)."""
    policy_path = temp_dir / "strict-audio-filter-policy.yaml"
    policy_path.write_text("""
schema_version: 3
track_order:
  - video
  - audio_main
  - subtitle_main
audio_language_preference:
  - eng
subtitle_language_preference:
  - eng
audio_filter:
  languages:
    - eng
  minimum: 1
default_flags:
  set_first_video_default: true
  set_preferred_audio_default: true
  set_preferred_subtitle_default: false
  clear_other_defaults: true
""")
    return policy_path


@pytest.fixture
def multilang_tracks() -> list[TrackInfo]:
    """Create test tracks with multiple languages."""
    return [
        TrackInfo(
            index=0,
            track_type="video",
            codec="hevc",
            width=1920,
            height=1080,
        ),
        TrackInfo(
            index=1,
            track_type="audio",
            codec="truehd",
            language="eng",
            title="TrueHD English",
            channels=8,
            is_default=True,
        ),
        TrackInfo(
            index=2,
            track_type="audio",
            codec="ac3",
            language="fra",
            title="French",
            channels=6,
        ),
        TrackInfo(
            index=3,
            track_type="audio",
            codec="ac3",
            language="spa",
            title="Spanish",
            channels=6,
        ),
        TrackInfo(
            index=4,
            track_type="subtitle",
            codec="subrip",
            language="eng",
            title="English",
        ),
        TrackInfo(
            index=5,
            track_type="subtitle",
            codec="subrip",
            language="fra",
            title="French",
        ),
    ]


@pytest.fixture
def non_english_tracks() -> list[TrackInfo]:
    """Create test tracks with no English audio."""
    return [
        TrackInfo(
            index=0,
            track_type="video",
            codec="hevc",
            width=1920,
            height=1080,
        ),
        TrackInfo(
            index=1,
            track_type="audio",
            codec="aac",
            language="jpn",
            title="Japanese",
            channels=2,
            is_default=True,
        ),
        TrackInfo(
            index=2,
            track_type="audio",
            codec="aac",
            language="kor",
            title="Korean",
            channels=2,
        ),
    ]


@pytest.fixture
def db_with_multilang_file(temp_db: Path, temp_dir: Path) -> tuple[Path, Path, int]:
    """Create a database with a multi-language file."""
    test_mkv = temp_dir / "multilang.mkv"
    test_mkv.write_bytes(b"fake mkv content")

    conn = sqlite3.connect(str(temp_db))
    create_schema(conn)

    # Insert file record
    conn.execute(
        """
        INSERT INTO files (path, filename, directory, extension, size_bytes,
                          modified_at, content_hash, container_format,
                          scanned_at, scan_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(test_mkv),
            test_mkv.name,
            str(test_mkv.parent),
            ".mkv",
            100,
            "2024-01-01T00:00:00Z",
            "abc123",
            "matroska",
            "2024-01-01T00:00:00Z",
            "ok",
        ),
    )
    file_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Insert tracks: video, 3 audio (eng, fra, spa), 2 subtitles
    # fmt: off
    tracks = [
        (file_id, 0, "video", "hevc", None, None, 1, 0, None, None, 1920, 1080, "24"),  # noqa: E501
        (file_id, 1, "audio", "truehd", "eng", "TrueHD", 1, 0, 8, "7.1", None, None, None),  # noqa: E501
        (file_id, 2, "audio", "ac3", "fra", "French", 0, 0, 6, "5.1", None, None, None),  # noqa: E501
        (file_id, 3, "audio", "ac3", "spa", "Spanish", 0, 0, 6, "5.1", None, None, None),  # noqa: E501
        (file_id, 4, "subtitle", "subrip", "eng", "English", 0, 0, None, None, None, None, None),  # noqa: E501
        (file_id, 5, "subtitle", "subrip", "fra", "French", 0, 0, None, None, None, None, None),  # noqa: E501
    ]
    # fmt: on
    conn.executemany(
        """
        INSERT INTO tracks (file_id, track_index, track_type, codec, language,
                           title, is_default, is_forced, channels, channel_layout,
                           width, height, frame_rate)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        tracks,
    )
    conn.commit()
    conn.close()

    return temp_db, test_mkv, file_id


# =============================================================================
# Policy Loading Tests
# =============================================================================


class TestV3PolicyLoading:
    """Tests for V3 policy loading with track filtering config."""

    def test_load_v3_policy_with_audio_filter(
        self, v3_audio_filter_policy: Path
    ) -> None:
        """V3 policy with audio_filter should load correctly."""
        from video_policy_orchestrator.policy.loader import load_policy

        policy = load_policy(v3_audio_filter_policy)

        assert policy.schema_version == 3
        assert policy.audio_filter is not None
        assert policy.audio_filter.languages == ("eng", "und")
        assert policy.audio_filter.minimum == 1
        assert policy.audio_filter.fallback is not None
        assert policy.audio_filter.fallback.mode == "keep_first"

    def test_v3_fields_rejected_on_v2_policy(self, temp_dir: Path) -> None:
        """V3 fields should be rejected on v2 policies."""
        from video_policy_orchestrator.policy.loader import (
            PolicyValidationError,
            load_policy,
        )

        policy_path = temp_dir / "invalid-v2.yaml"
        policy_path.write_text("""
schema_version: 2
track_order:
  - video
  - audio_main
audio_language_preference:
  - eng
subtitle_language_preference:
  - eng
audio_filter:
  languages:
    - eng
""")

        with pytest.raises(PolicyValidationError) as exc_info:
            load_policy(policy_path)

        assert "schema_version" in str(exc_info.value).lower()


# =============================================================================
# Track Disposition Tests
# =============================================================================


class TestComputeTrackDispositions:
    """Tests for compute_track_dispositions function."""

    def test_audio_filtering_keeps_matching_languages(
        self, multilang_tracks: list[TrackInfo]
    ) -> None:
        """Audio tracks matching filter languages should be kept."""
        policy = PolicySchema(
            schema_version=3,
            audio_filter=AudioFilterConfig(languages=("eng",)),
        )

        dispositions = compute_track_dispositions(multilang_tracks, policy)

        # Check audio dispositions
        audio_disps = [d for d in dispositions if d.track_type == "audio"]
        assert len(audio_disps) == 3

        eng_audio = [d for d in audio_disps if d.language == "eng"][0]
        assert eng_audio.action == "KEEP"

        fra_audio = [d for d in audio_disps if d.language == "fra"][0]
        assert fra_audio.action == "REMOVE"

        spa_audio = [d for d in audio_disps if d.language == "spa"][0]
        assert spa_audio.action == "REMOVE"

    def test_insufficient_tracks_raises_error(
        self, non_english_tracks: list[TrackInfo]
    ) -> None:
        """InsufficientTracksError should be raised when no audio matches."""
        policy = PolicySchema(
            schema_version=3,
            audio_filter=AudioFilterConfig(languages=("eng",)),
        )

        with pytest.raises(InsufficientTracksError) as exc_info:
            compute_track_dispositions(non_english_tracks, policy)

        err = exc_info.value
        assert err.track_type == "audio"
        assert err.required == 1
        assert err.available == 0

    def test_fallback_keep_first_preserves_minimum(
        self, non_english_tracks: list[TrackInfo]
    ) -> None:
        """Fallback mode keep_first should preserve minimum tracks."""
        policy = PolicySchema(
            schema_version=3,
            audio_filter=AudioFilterConfig(
                languages=("eng",),
                fallback=LanguageFallbackConfig(mode="keep_first"),
            ),
        )

        dispositions = compute_track_dispositions(non_english_tracks, policy)

        audio_disps = [d for d in dispositions if d.track_type == "audio"]
        kept = [d for d in audio_disps if d.action == "KEEP"]
        assert len(kept) >= 1
        assert "fallback" in kept[0].reason.lower()

    def test_fallback_content_language_keeps_matching(
        self, non_english_tracks: list[TrackInfo]
    ) -> None:
        """Fallback mode content_language keeps tracks matching first audio."""
        policy = PolicySchema(
            schema_version=3,
            audio_filter=AudioFilterConfig(
                languages=("eng",),
                fallback=LanguageFallbackConfig(mode="content_language"),
            ),
        )

        dispositions = compute_track_dispositions(non_english_tracks, policy)

        # First audio is Japanese, so Japanese tracks should be kept
        audio_disps = [d for d in dispositions if d.track_type == "audio"]
        jpn_tracks = [d for d in audio_disps if d.language == "jpn"]
        assert all(d.action == "KEEP" for d in jpn_tracks)


# =============================================================================
# Plan Integration Tests
# =============================================================================


class TestPlanWithTrackFiltering:
    """Tests for Plan creation with track filtering."""

    def test_plan_includes_track_dispositions(
        self, multilang_tracks: list[TrackInfo]
    ) -> None:
        """Plan should include track dispositions when filtering is active."""
        policy = PolicySchema(
            schema_version=3,
            audio_filter=AudioFilterConfig(languages=("eng",)),
        )

        dispositions = compute_track_dispositions(multilang_tracks, policy)

        # Create a plan with dispositions
        tracks_kept = sum(1 for d in dispositions if d.action == "KEEP")
        tracks_removed = sum(1 for d in dispositions if d.action == "REMOVE")

        plan = Plan(
            file_id="test-file-id",
            file_path=Path("/test/file.mkv"),
            policy_version=3,
            actions=(),
            requires_remux=True,
            track_dispositions=dispositions,
            tracks_kept=tracks_kept,
            tracks_removed=tracks_removed,
        )

        assert len(plan.track_dispositions) == 6  # All tracks
        assert plan.tracks_kept == 4  # video + 1 audio + 2 subtitles
        assert plan.tracks_removed == 2  # 2 non-English audio

    def test_plan_summary_includes_track_counts(
        self, multilang_tracks: list[TrackInfo]
    ) -> None:
        """Plan summary should include track removal counts."""
        policy = PolicySchema(
            schema_version=3,
            audio_filter=AudioFilterConfig(languages=("eng",)),
        )

        dispositions = compute_track_dispositions(multilang_tracks, policy)
        tracks_removed = sum(1 for d in dispositions if d.action == "REMOVE")

        plan = Plan(
            file_id="test-file-id",
            file_path=Path("/test/file.mkv"),
            policy_version=3,
            actions=(),
            requires_remux=True,
            track_dispositions=dispositions,
            tracks_kept=len(multilang_tracks) - tracks_removed,
            tracks_removed=tracks_removed,
        )

        summary = plan.summary
        assert "removed" in summary.lower()
        assert "2" in summary  # 2 tracks removed


# =============================================================================
# MkvmergeExecutor Integration Tests
# =============================================================================


class TestMkvmergeExecutorTrackSelection:
    """Tests for MkvmergeExecutor track selection argument building."""

    def test_build_track_selection_args_audio_only(self) -> None:
        """Should build correct audio track selection args."""
        from video_policy_orchestrator.executor.mkvmerge import MkvmergeExecutor

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
                reason="video",
            ),
            TrackDisposition(
                track_index=1,
                track_type="audio",
                codec="truehd",
                language="eng",
                title="English",
                channels=8,
                resolution=None,
                action="KEEP",
                reason="language in keep list",
            ),
            TrackDisposition(
                track_index=2,
                track_type="audio",
                codec="ac3",
                language="fra",
                title="French",
                channels=6,
                resolution=None,
                action="REMOVE",
                reason="language not in keep list",
            ),
        )

        executor = MkvmergeExecutor()
        args = executor._build_track_selection_args(dispositions)

        assert "--audio-tracks" in args
        idx = args.index("--audio-tracks")
        assert args[idx + 1] == "1"  # Only keep track 1

    def test_build_track_selection_args_no_filtering(self) -> None:
        """Should return empty args when no tracks are filtered."""
        from video_policy_orchestrator.executor.mkvmerge import MkvmergeExecutor

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
                reason="video",
            ),
            TrackDisposition(
                track_index=1,
                track_type="audio",
                codec="aac",
                language="eng",
                title="English",
                channels=2,
                resolution=None,
                action="KEEP",
                reason="no filter applied",
            ),
        )

        executor = MkvmergeExecutor()
        args = executor._build_track_selection_args(dispositions)

        # No filtering args needed when all tracks are kept
        assert "--audio-tracks" not in args

    def test_can_handle_plan_with_track_removal(self) -> None:
        """Executor should handle plans with track removal."""
        from video_policy_orchestrator.executor.mkvmerge import MkvmergeExecutor

        plan = Plan(
            file_id="test",
            file_path=Path("/test/file.mkv"),
            policy_version=3,
            actions=(),
            requires_remux=True,
            tracks_removed=2,
        )

        executor = MkvmergeExecutor()
        assert executor.can_handle(plan) is True

    def test_cannot_handle_non_mkv_files(self) -> None:
        """Executor should not handle non-MKV files."""
        from video_policy_orchestrator.executor.mkvmerge import MkvmergeExecutor

        plan = Plan(
            file_id="test",
            file_path=Path("/test/file.mp4"),
            policy_version=3,
            actions=(),
            requires_remux=True,
            tracks_removed=2,
        )

        executor = MkvmergeExecutor()
        assert executor.can_handle(plan) is False


# =============================================================================
# Subtitle Filtering Integration Tests (T061)
# =============================================================================


class TestSubtitleFilteringIntegration:
    """Integration tests for subtitle filtering with forced preservation (T061)."""

    def test_subtitle_filtering_with_forced_preservation(self) -> None:
        """Test subtitle filtering preserves forced subtitles."""
        from video_policy_orchestrator.policy.models import SubtitleFilterConfig

        tracks = [
            TrackInfo(
                index=0,
                track_type="video",
                codec="hevc",
                width=1920,
                height=1080,
            ),
            TrackInfo(
                index=1,
                track_type="audio",
                codec="aac",
                language="eng",
            ),
            TrackInfo(
                index=2,
                track_type="subtitle",
                codec="subrip",
                language="eng",
                is_forced=False,
            ),
            TrackInfo(
                index=3,
                track_type="subtitle",
                codec="subrip",
                language="jpn",
                is_forced=True,  # Foreign language forced subtitle
            ),
            TrackInfo(
                index=4,
                track_type="subtitle",
                codec="subrip",
                language="fra",
                is_forced=False,
            ),
        ]

        policy = PolicySchema(
            schema_version=3,
            subtitle_filter=SubtitleFilterConfig(
                languages=("eng",),
                preserve_forced=True,
            ),
        )

        dispositions = compute_track_dispositions(tracks, policy)

        # English subtitle should be kept (matches language)
        eng_sub = [d for d in dispositions if d.track_index == 2][0]
        assert eng_sub.action == "KEEP"

        # Japanese forced subtitle should be kept (preserve_forced=True)
        jpn_sub = [d for d in dispositions if d.track_index == 3][0]
        assert jpn_sub.action == "KEEP"
        assert "forced" in jpn_sub.reason.lower()

        # French subtitle should be removed
        fra_sub = [d for d in dispositions if d.track_index == 4][0]
        assert fra_sub.action == "REMOVE"

        # Should have 1 track removed total
        removed = [d for d in dispositions if d.action == "REMOVE"]
        assert len(removed) == 1

    def test_subtitle_remove_all_integration(self) -> None:
        """Test remove_all removes all subtitle tracks."""
        from video_policy_orchestrator.policy.models import SubtitleFilterConfig

        tracks = [
            TrackInfo(
                index=0,
                track_type="video",
                codec="hevc",
                width=1920,
                height=1080,
            ),
            TrackInfo(
                index=1,
                track_type="audio",
                codec="aac",
                language="eng",
            ),
            TrackInfo(
                index=2,
                track_type="subtitle",
                codec="subrip",
                language="eng",
                is_forced=True,
            ),
            TrackInfo(
                index=3,
                track_type="subtitle",
                codec="ass",
                language="jpn",
            ),
        ]

        policy = PolicySchema(
            schema_version=3,
            subtitle_filter=SubtitleFilterConfig(
                remove_all=True,
                preserve_forced=True,  # Should be ignored
            ),
        )

        dispositions = compute_track_dispositions(tracks, policy)

        # All subtitles should be removed despite preserve_forced
        subtitle_disps = [d for d in dispositions if d.track_type == "subtitle"]
        assert all(d.action == "REMOVE" for d in subtitle_disps)
        assert len(subtitle_disps) == 2

    def test_combined_audio_and_subtitle_filtering(self) -> None:
        """Test that audio and subtitle filtering work together."""
        from video_policy_orchestrator.policy.models import SubtitleFilterConfig

        tracks = [
            TrackInfo(
                index=0,
                track_type="video",
                codec="hevc",
                width=1920,
                height=1080,
            ),
            TrackInfo(
                index=1,
                track_type="audio",
                codec="truehd",
                language="eng",
            ),
            TrackInfo(
                index=2,
                track_type="audio",
                codec="aac",
                language="jpn",
            ),
            TrackInfo(
                index=3,
                track_type="subtitle",
                codec="subrip",
                language="eng",
            ),
            TrackInfo(
                index=4,
                track_type="subtitle",
                codec="subrip",
                language="jpn",
            ),
        ]

        policy = PolicySchema(
            schema_version=3,
            audio_filter=AudioFilterConfig(languages=("eng",)),
            subtitle_filter=SubtitleFilterConfig(languages=("eng",)),
        )

        dispositions = compute_track_dispositions(tracks, policy)

        # English audio kept
        eng_audio = [d for d in dispositions if d.track_index == 1][0]
        assert eng_audio.action == "KEEP"

        # Japanese audio removed
        jpn_audio = [d for d in dispositions if d.track_index == 2][0]
        assert jpn_audio.action == "REMOVE"

        # English subtitle kept
        eng_sub = [d for d in dispositions if d.track_index == 3][0]
        assert eng_sub.action == "KEEP"

        # Japanese subtitle removed
        jpn_sub = [d for d in dispositions if d.track_index == 4][0]
        assert jpn_sub.action == "REMOVE"

        # Total: 2 tracks removed
        removed = [d for d in dispositions if d.action == "REMOVE"]
        assert len(removed) == 2


# =============================================================================
# Attachment Filtering Integration Tests (T069)
# =============================================================================


class TestAttachmentFilteringIntegration:
    """Integration tests for attachment removal with warnings (T069)."""

    def test_attachment_removal_with_font_warning(self) -> None:
        """Test attachment removal generates warning for fonts with styled subs."""
        from video_policy_orchestrator.policy.models import AttachmentFilterConfig

        tracks = [
            TrackInfo(
                index=0,
                track_type="video",
                codec="hevc",
                width=1920,
                height=1080,
            ),
            TrackInfo(
                index=1,
                track_type="audio",
                codec="aac",
                language="eng",
            ),
            TrackInfo(
                index=2,
                track_type="subtitle",
                codec="ass",  # Styled subtitle
                language="eng",
            ),
            TrackInfo(
                index=3,
                track_type="attachment",
                codec="ttf",
                title="CustomFont.ttf",
            ),
            TrackInfo(
                index=4,
                track_type="attachment",
                codec="image/jpeg",
                title="cover.jpg",
            ),
        ]

        policy = PolicySchema(
            schema_version=3,
            attachment_filter=AttachmentFilterConfig(remove_all=True),
        )

        dispositions = compute_track_dispositions(tracks, policy)

        # Both attachments should be removed
        attachment_disps = [d for d in dispositions if d.track_type == "attachment"]
        assert len(attachment_disps) == 2
        assert all(d.action == "REMOVE" for d in attachment_disps)

        # Font attachment should have styled subtitle warning
        font_disp = [d for d in attachment_disps if "ttf" in (d.codec or "")][0]
        assert "styled subtitle" in font_disp.reason.lower()

        # Cover art should not have styled subtitle warning
        cover_disp = [d for d in attachment_disps if "jpeg" in (d.codec or "")][0]
        assert "styled subtitle" not in cover_disp.reason.lower()

    def test_attachment_removal_combined_with_subtitle_filter(self) -> None:
        """Test attachment removal works with subtitle filtering."""
        from video_policy_orchestrator.policy.models import (
            AttachmentFilterConfig,
            SubtitleFilterConfig,
        )

        tracks = [
            TrackInfo(
                index=0,
                track_type="video",
                codec="hevc",
                width=1920,
                height=1080,
            ),
            TrackInfo(
                index=1,
                track_type="audio",
                codec="aac",
                language="eng",
            ),
            TrackInfo(
                index=2,
                track_type="subtitle",
                codec="ass",
                language="eng",
            ),
            TrackInfo(
                index=3,
                track_type="subtitle",
                codec="subrip",
                language="jpn",
            ),
            TrackInfo(
                index=4,
                track_type="attachment",
                codec="ttf",
                title="Font.ttf",
            ),
        ]

        policy = PolicySchema(
            schema_version=3,
            subtitle_filter=SubtitleFilterConfig(languages=("eng",)),
            attachment_filter=AttachmentFilterConfig(remove_all=True),
        )

        dispositions = compute_track_dispositions(tracks, policy)

        # English subtitle kept, Japanese subtitle removed
        eng_sub = [d for d in dispositions if d.track_index == 2][0]
        assert eng_sub.action == "KEEP"

        jpn_sub = [d for d in dispositions if d.track_index == 3][0]
        assert jpn_sub.action == "REMOVE"

        # Attachment removed with font warning (since ASS subtitle is kept)
        font_disp = [d for d in dispositions if d.track_type == "attachment"][0]
        assert font_disp.action == "REMOVE"
        assert "styled subtitle" in font_disp.reason.lower()

        # Total: 2 tracks removed (Japanese subtitle + font attachment)
        removed = [d for d in dispositions if d.action == "REMOVE"]
        assert len(removed) == 2


# =============================================================================
# Fallback Mode Integration Tests (T079)
# =============================================================================


class TestFallbackModeIntegration:
    """Integration tests for language fallback modes end-to-end (T079)."""

    def test_content_language_fallback_with_anime_file(self) -> None:
        """Test content_language fallback with anime file (Japanese audio only)."""
        tracks = [
            TrackInfo(
                index=0,
                track_type="video",
                codec="hevc",
                width=1920,
                height=1080,
            ),
            TrackInfo(
                index=1,
                track_type="audio",
                codec="aac",
                language="jpn",
                title="Japanese Stereo",
                channels=2,
                is_default=True,
            ),
            TrackInfo(
                index=2,
                track_type="audio",
                codec="flac",
                language="jpn",
                title="Japanese 5.1",
                channels=6,
            ),
            TrackInfo(
                index=3,
                track_type="subtitle",
                codec="ass",
                language="eng",
                title="English",
            ),
        ]

        policy = PolicySchema(
            schema_version=3,
            audio_filter=AudioFilterConfig(
                languages=("eng",),  # No English audio in file
                fallback=LanguageFallbackConfig(mode="content_language"),
            ),
        )

        dispositions = compute_track_dispositions(tracks, policy)

        # Both Japanese audio tracks should be kept (content language)
        audio_disps = [d for d in dispositions if d.track_type == "audio"]
        assert len(audio_disps) == 2
        assert all(d.action == "KEEP" for d in audio_disps)
        assert all("content language" in d.reason.lower() for d in audio_disps)

    def test_keep_first_fallback_with_multi_dub_file(self) -> None:
        """Test keep_first fallback with file having multiple dubbed tracks."""
        tracks = [
            TrackInfo(
                index=0,
                track_type="video",
                codec="h264",
                width=1920,
                height=1080,
            ),
            TrackInfo(
                index=1,
                track_type="audio",
                codec="ac3",
                language="fra",
                title="French",
                channels=6,
            ),
            TrackInfo(
                index=2,
                track_type="audio",
                codec="ac3",
                language="deu",
                title="German",
                channels=6,
            ),
            TrackInfo(
                index=3,
                track_type="audio",
                codec="ac3",
                language="spa",
                title="Spanish",
                channels=6,
            ),
            TrackInfo(
                index=4,
                track_type="audio",
                codec="ac3",
                language="ita",
                title="Italian",
                channels=6,
            ),
        ]

        policy = PolicySchema(
            schema_version=3,
            audio_filter=AudioFilterConfig(
                languages=("eng",),  # No English
                minimum=2,
                fallback=LanguageFallbackConfig(mode="keep_first"),
            ),
        )

        dispositions = compute_track_dispositions(tracks, policy)

        # First 2 audio tracks should be kept
        audio_disps = [d for d in dispositions if d.track_type == "audio"]
        kept = [d for d in audio_disps if d.action == "KEEP"]
        removed = [d for d in audio_disps if d.action == "REMOVE"]

        assert len(kept) == 2
        assert len(removed) == 2
        assert kept[0].language == "fra"  # First track
        assert kept[1].language == "deu"  # Second track

    def test_keep_all_fallback_preserves_all_tracks(self) -> None:
        """Test keep_all fallback preserves all audio tracks."""
        tracks = [
            TrackInfo(
                index=0,
                track_type="video",
                codec="hevc",
                width=3840,
                height=2160,
            ),
            TrackInfo(
                index=1,
                track_type="audio",
                codec="truehd",
                language="deu",
                title="TrueHD German",
                channels=8,
            ),
            TrackInfo(
                index=2,
                track_type="audio",
                codec="ac3",
                language="deu",
                title="AC3 German",
                channels=6,
            ),
        ]

        policy = PolicySchema(
            schema_version=3,
            audio_filter=AudioFilterConfig(
                languages=("eng", "jpn"),  # Neither present
                fallback=LanguageFallbackConfig(mode="keep_all"),
            ),
        )

        dispositions = compute_track_dispositions(tracks, policy)

        # All audio tracks should be kept
        audio_disps = [d for d in dispositions if d.track_type == "audio"]
        assert len(audio_disps) == 2
        assert all(d.action == "KEEP" for d in audio_disps)
        assert all("keep_all" in d.reason.lower() for d in audio_disps)

    def test_error_fallback_raises_with_helpful_message(self) -> None:
        """Test error fallback raises with helpful message showing languages."""
        tracks = [
            TrackInfo(
                index=0,
                track_type="video",
                codec="hevc",
                width=1920,
                height=1080,
            ),
            TrackInfo(
                index=1,
                track_type="audio",
                codec="aac",
                language="kor",
                title="Korean",
                channels=2,
            ),
            TrackInfo(
                index=2,
                track_type="audio",
                codec="aac",
                language="jpn",
                title="Japanese",
                channels=2,
            ),
        ]

        policy = PolicySchema(
            schema_version=3,
            audio_filter=AudioFilterConfig(
                languages=("eng", "fra", "deu"),
                fallback=LanguageFallbackConfig(mode="error"),
            ),
        )

        with pytest.raises(InsufficientTracksError) as exc_info:
            compute_track_dispositions(tracks, policy)

        err = exc_info.value
        assert err.track_type == "audio"
        assert err.available == 0
        assert err.required == 1
        # Check policy languages are in error
        assert "eng" in err.policy_languages
        assert "fra" in err.policy_languages
        assert "deu" in err.policy_languages
        # Check file languages are in error
        assert "kor" in err.file_languages
        assert "jpn" in err.file_languages

    def test_fallback_combined_with_subtitle_and_attachment_filters(self) -> None:
        """Test fallback mode works correctly with other filters active."""
        tracks = [
            TrackInfo(
                index=0,
                track_type="video",
                codec="hevc",
                width=1920,
                height=1080,
            ),
            TrackInfo(
                index=1,
                track_type="audio",
                codec="aac",
                language="jpn",
                title="Japanese",
                channels=2,
            ),
            TrackInfo(
                index=2,
                track_type="subtitle",
                codec="ass",
                language="eng",
                title="English",
            ),
            TrackInfo(
                index=3,
                track_type="subtitle",
                codec="ass",
                language="jpn",
                title="Japanese",
            ),
            TrackInfo(
                index=4,
                track_type="attachment",
                codec="ttf",
                title="Font.ttf",
            ),
        ]

        from video_policy_orchestrator.policy.models import (
            AttachmentFilterConfig,
            SubtitleFilterConfig,
        )

        policy = PolicySchema(
            schema_version=3,
            audio_filter=AudioFilterConfig(
                languages=("eng",),  # No English audio
                fallback=LanguageFallbackConfig(mode="content_language"),
            ),
            subtitle_filter=SubtitleFilterConfig(
                languages=("eng",),
            ),
            attachment_filter=AttachmentFilterConfig(
                remove_all=True,
            ),
        )

        dispositions = compute_track_dispositions(tracks, policy)

        # Audio: Japanese kept via content_language fallback
        audio_disp = [d for d in dispositions if d.track_type == "audio"][0]
        assert audio_disp.action == "KEEP"
        assert "content language" in audio_disp.reason.lower()

        # Subtitles: English kept, Japanese removed
        subtitle_disps = [d for d in dispositions if d.track_type == "subtitle"]
        eng_sub = [d for d in subtitle_disps if d.language == "eng"][0]
        jpn_sub = [d for d in subtitle_disps if d.language == "jpn"][0]
        assert eng_sub.action == "KEEP"
        assert jpn_sub.action == "REMOVE"

        # Attachment: removed with styled subtitle warning
        attach_disp = [d for d in dispositions if d.track_type == "attachment"][0]
        assert attach_disp.action == "REMOVE"
        assert "styled subtitle" in attach_disp.reason.lower()

        # Count removed tracks
        removed = [d for d in dispositions if d.action == "REMOVE"]
        assert len(removed) == 2  # Japanese subtitle + font attachment
