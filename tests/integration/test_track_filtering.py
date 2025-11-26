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
