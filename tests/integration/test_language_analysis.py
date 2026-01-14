"""Integration tests for multi-language audio detection functionality.

Tests the end-to-end flow of language analysis including:
- T091: Full scan with language analysis
- T092: Policy evaluation with audio_is_multi_language condition
- T093: End-to-end forced subtitle enablement
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vpo.db.models import TrackInfo
from vpo.language_analysis.models import (
    AnalysisMetadata,
    LanguageAnalysisResult,
    LanguageClassification,
    LanguagePercentage,
    LanguageSegment,
)
from vpo.policy.evaluator import evaluate_conditional_rules
from vpo.policy.loader import load_policy

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def multi_language_analysis_result() -> LanguageAnalysisResult:
    """Create a mock multi-language analysis result (82% English, 18% French)."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    return LanguageAnalysisResult(
        track_id=1,
        file_hash="abc123",
        primary_language="eng",
        primary_percentage=0.82,
        secondary_languages=(LanguagePercentage("fre", 0.18),),
        classification=LanguageClassification.MULTI_LANGUAGE,
        segments=(
            LanguageSegment("eng", 0.0, 300.0, 0.95),
            LanguageSegment("fre", 300.0, 360.0, 0.92),
            LanguageSegment("eng", 360.0, 600.0, 0.93),
        ),
        metadata=AnalysisMetadata(
            plugin_name="whisper",
            plugin_version="1.0.0",
            model_name="whisper-base",
            sample_positions=(0.0, 300.0, 600.0),
            sample_duration=5.0,
            total_duration=600.0,
            speech_ratio=0.95,
        ),
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def single_language_analysis_result() -> LanguageAnalysisResult:
    """Create a mock single-language analysis result (100% English)."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    return LanguageAnalysisResult(
        track_id=1,
        file_hash="abc123",
        primary_language="eng",
        primary_percentage=1.0,
        secondary_languages=(),
        classification=LanguageClassification.SINGLE_LANGUAGE,
        segments=(
            LanguageSegment("eng", 0.0, 300.0, 0.98),
            LanguageSegment("eng", 300.0, 600.0, 0.97),
        ),
        metadata=AnalysisMetadata(
            plugin_name="whisper",
            plugin_version="1.0.0",
            model_name="whisper-base",
            sample_positions=(0.0, 300.0),
            sample_duration=5.0,
            total_duration=600.0,
            speech_ratio=0.95,
        ),
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def mock_audio_track() -> TrackInfo:
    """Create a mock audio track."""
    return TrackInfo(
        index=1,
        track_type="audio",
        id=1,
        codec="aac",
        language="eng",
        title="English Audio",
        is_default=True,
        is_forced=False,
    )


@pytest.fixture
def mock_forced_subtitle_track() -> TrackInfo:
    """Create a mock forced subtitle track."""
    return TrackInfo(
        index=2,
        track_type="subtitle",
        id=2,
        codec="ass",
        language="eng",
        title="English Forced",
        is_default=False,
        is_forced=True,
    )


@pytest.fixture
def mock_regular_subtitle_track() -> TrackInfo:
    """Create a mock regular subtitle track."""
    return TrackInfo(
        index=3,
        track_type="subtitle",
        id=3,
        codec="ass",
        language="eng",
        title="English",
        is_default=True,
        is_forced=False,
    )


@pytest.fixture
def mock_video_track() -> TrackInfo:
    """Create a mock video track."""
    return TrackInfo(
        index=0,
        track_type="video",
        id=4,
        codec="hevc",
        language=None,
        title="Video",
        is_default=True,
        is_forced=False,
        width=1920,
        height=1080,
    )


@pytest.fixture
def v7_multi_language_policy(temp_dir: Path) -> Path:
    """Create a policy file with audio_is_multi_language condition."""
    policy_path = temp_dir / "multi-language-policy.yaml"
    policy_path.write_text("""
schema_version: 12

conditional:
  - name: "Enable forced subs for multi-language audio"
    when:
      and:
        - audio_is_multi_language:
            primary_language: eng
            threshold: 0.05
        - exists:
            track_type: subtitle
            language: eng
            is_forced: true
    then:
      - set_default:
          track_type: subtitle
          language: eng
      - warn: "Enabled forced English subtitles for multi-language content"

  - name: "Warn about missing forced subs"
    when:
      and:
        - audio_is_multi_language:
            primary_language: eng
        - not:
            exists:
              track_type: subtitle
              language: eng
              is_forced: true
    then:
      - warn: "Multi-language audio detected but no forced English subtitles available"

audio_language_preference:
  - eng
  - und

subtitle_language_preference:
  - eng
  - und
""")
    return policy_path


@pytest.fixture
def v7_simple_multi_language_policy(temp_dir: Path) -> Path:
    """Create a policy with simple boolean audio_is_multi_language."""
    policy_path = temp_dir / "simple-multi-language.yaml"
    policy_path.write_text("""
schema_version: 12

conditional:
  - name: "Detect any multi-language content"
    when:
      audio_is_multi_language:
        threshold: 0.05
    then:
      - warn: "Multi-language audio detected"

audio_language_preference:
  - eng
""")
    return policy_path


@pytest.fixture
def v6_policy_no_v7_features(temp_dir: Path) -> Path:
    """Create a policy without any V7+ features."""
    policy_path = temp_dir / "v6-policy.yaml"
    policy_path.write_text("""
schema_version: 12

conditional:
  - name: "Skip 4K HEVC"
    when:
      and:
        - exists:
            track_type: video
            height: { gte: 2160 }
        - exists:
            track_type: video
            codec: hevc
    then:
      - skip_video_transcode: true

audio_language_preference:
  - eng
""")
    return policy_path


# =============================================================================
# T091: Integration Test for Full Scan with Language Analysis
# =============================================================================


class TestScanWithLanguageAnalysis:
    """Integration tests for scan command with --analyze-languages flag."""

    def test_scan_with_analyze_languages_option_exists(self):
        """Verify --analyze-languages option is available on scan command."""
        from click.testing import CliRunner

        from vpo.cli.scan import scan

        runner = CliRunner()
        result = runner.invoke(scan, ["--help"])

        assert result.exit_code == 0
        assert "--analyze-languages" in result.output

    def test_language_analysis_service_callable(
        self,
        mock_audio_track: TrackInfo,
    ):
        """Verify language analysis service can be called with proper arguments."""
        from vpo.language_analysis.service import (
            LanguageAnalysisError,
            analyze_track_languages,
        )

        # Verify the function signature is correct (it should raise if called
        # with invalid arguments, which shows the function exists)
        with pytest.raises((LanguageAnalysisError, ValueError)):
            # Should fail due to missing transcriber
            analyze_track_languages(
                file_path=Path("/nonexistent.mkv"),
                track_index=0,
                track_id=1,
                track_duration=600.0,
                file_hash="abc123",
                transcriber=MagicMock(supports_feature=lambda x: False),
            )


# =============================================================================
# T092: Integration Test for Policy Evaluation with audio_is_multi_language
# =============================================================================


class TestAudioIsMultiLanguageCondition:
    """Integration tests for audio_is_multi_language policy condition."""

    def test_v7_policy_loads_with_audio_is_multi_language(
        self,
        v7_multi_language_policy: Path,
    ):
        """Test that policy with audio_is_multi_language loads correctly."""
        policy = load_policy(v7_multi_language_policy)

        assert policy.schema_version == 12
        assert len(policy.conditional_rules) == 2
        assert (
            policy.conditional_rules[0].name
            == "Enable forced subs for multi-language audio"
        )

    def test_v7_simple_boolean_condition_loads(
        self,
        v7_simple_multi_language_policy: Path,
    ):
        """Test that policy with simple boolean audio_is_multi_language loads."""
        policy = load_policy(v7_simple_multi_language_policy)

        assert policy.schema_version == 12
        assert len(policy.conditional_rules) == 1

    def test_audio_is_multi_language_condition_matches_multi_language_track(
        self,
        v7_multi_language_policy: Path,
        mock_audio_track: TrackInfo,
        mock_forced_subtitle_track: TrackInfo,
        mock_video_track: TrackInfo,
        multi_language_analysis_result: LanguageAnalysisResult,
    ):
        """Test audio_is_multi_language matches when track has multiple languages."""
        policy = load_policy(v7_multi_language_policy)
        tracks = [mock_video_track, mock_audio_track, mock_forced_subtitle_track]
        language_results = {1: multi_language_analysis_result}

        result = evaluate_conditional_rules(
            policy.conditional_rules,
            tracks,
            Path("/test/movie.mkv"),
            language_results=language_results,
        )

        assert result.matched_rule == "Enable forced subs for multi-language audio"
        assert result.matched_branch == "then"
        assert len(result.warnings) == 1
        assert "multi-language" in result.warnings[0].lower()

    def test_audio_is_multi_language_does_not_match_single_language(
        self,
        v7_simple_multi_language_policy: Path,
        mock_audio_track: TrackInfo,
        mock_video_track: TrackInfo,
        single_language_analysis_result: LanguageAnalysisResult,
    ):
        """Test that audio_is_multi_language doesn't match single-language content."""
        policy = load_policy(v7_simple_multi_language_policy)
        tracks = [mock_video_track, mock_audio_track]
        language_results = {1: single_language_analysis_result}

        result = evaluate_conditional_rules(
            policy.conditional_rules,
            tracks,
            Path("/test/movie.mkv"),
            language_results=language_results,
        )

        # Should not match any rule since content is single-language
        assert result.matched_rule is None
        assert len(result.warnings) == 0

    def test_audio_is_multi_language_with_primary_language_constraint(
        self,
        temp_dir: Path,
        mock_audio_track: TrackInfo,
        mock_video_track: TrackInfo,
    ):
        """Test audio_is_multi_language with primary_language constraint."""
        from datetime import datetime, timezone

        # Create a French-primary multi-language result
        now = datetime.now(timezone.utc)
        french_primary_result = LanguageAnalysisResult(
            track_id=1,
            file_hash="abc123",
            primary_language="fre",
            primary_percentage=0.82,
            secondary_languages=(LanguagePercentage("eng", 0.18),),
            classification=LanguageClassification.MULTI_LANGUAGE,
            segments=(),
            metadata=AnalysisMetadata(
                plugin_name="whisper",
                plugin_version="1.0.0",
                model_name="whisper-base",
                sample_positions=(),
                sample_duration=5.0,
                total_duration=600.0,
                speech_ratio=0.95,
            ),
            created_at=now,
            updated_at=now,
        )

        # Policy expects English primary
        policy_path = temp_dir / "english-primary.yaml"
        policy_path.write_text("""
schema_version: 12

conditional:
  - name: "English primary multi-language"
    when:
      audio_is_multi_language:
        primary_language: eng
        threshold: 0.05
    then:
      - warn: "English multi-language detected"

audio_language_preference:
  - eng
""")

        policy = load_policy(policy_path)
        tracks = [mock_video_track, mock_audio_track]
        language_results = {1: french_primary_result}

        result = evaluate_conditional_rules(
            policy.conditional_rules,
            tracks,
            Path("/test/movie.mkv"),
            language_results=language_results,
        )

        # Should NOT match because primary language is French, not English
        assert result.matched_rule is None

    def test_audio_is_multi_language_with_threshold(
        self,
        temp_dir: Path,
        mock_audio_track: TrackInfo,
        mock_video_track: TrackInfo,
    ):
        """Test audio_is_multi_language with custom threshold."""
        from datetime import datetime, timezone

        # Create result with 3% secondary language (below 5% threshold)
        now = datetime.now(timezone.utc)
        minimal_secondary = LanguageAnalysisResult(
            track_id=1,
            file_hash="abc123",
            primary_language="eng",
            primary_percentage=0.97,
            secondary_languages=(LanguagePercentage("fre", 0.03),),
            classification=LanguageClassification.MULTI_LANGUAGE,  # Still multi
            segments=(),
            metadata=AnalysisMetadata(
                plugin_name="whisper",
                plugin_version="1.0.0",
                model_name="whisper-base",
                sample_positions=(),
                sample_duration=5.0,
                total_duration=600.0,
                speech_ratio=0.95,
            ),
            created_at=now,
            updated_at=now,
        )

        # Policy with 5% threshold
        policy_path = temp_dir / "threshold-policy.yaml"
        policy_path.write_text("""
schema_version: 12

conditional:
  - name: "Multi-language with 5% threshold"
    when:
      audio_is_multi_language:
        threshold: 0.05
    then:
      - warn: "Multi-language detected"

audio_language_preference:
  - eng
""")

        policy = load_policy(policy_path)
        tracks = [mock_video_track, mock_audio_track]
        language_results = {1: minimal_secondary}

        result = evaluate_conditional_rules(
            policy.conditional_rules,
            tracks,
            Path("/test/movie.mkv"),
            language_results=language_results,
        )

        # Should NOT match because secondary is only 3%, below 5% threshold
        assert result.matched_rule is None


# =============================================================================
# T093: Integration Test for End-to-End Forced Subtitle Enablement
# =============================================================================


class TestForcedSubtitleEnablement:
    """Integration tests for forced subtitle enablement via policy."""

    def test_set_default_action_in_policy_context(
        self,
        v7_multi_language_policy: Path,
        mock_audio_track: TrackInfo,
        mock_forced_subtitle_track: TrackInfo,
        mock_video_track: TrackInfo,
        multi_language_analysis_result: LanguageAnalysisResult,
    ):
        """Test that set_default action triggers correctly for multi-language."""
        policy = load_policy(v7_multi_language_policy)
        tracks = [mock_video_track, mock_audio_track, mock_forced_subtitle_track]
        language_results = {1: multi_language_analysis_result}

        result = evaluate_conditional_rules(
            policy.conditional_rules,
            tracks,
            Path("/test/movie.mkv"),
            language_results=language_results,
        )

        # Should match and enable forced subtitles
        assert result.matched_rule == "Enable forced subs for multi-language audio"

    def test_warning_when_no_forced_subs_available(
        self,
        v7_multi_language_policy: Path,
        mock_audio_track: TrackInfo,
        mock_regular_subtitle_track: TrackInfo,  # Not forced
        mock_video_track: TrackInfo,
        multi_language_analysis_result: LanguageAnalysisResult,
    ):
        """Test warning is issued when multi-language but no forced subs."""
        policy = load_policy(v7_multi_language_policy)
        tracks = [mock_video_track, mock_audio_track, mock_regular_subtitle_track]
        language_results = {1: multi_language_analysis_result}

        result = evaluate_conditional_rules(
            policy.conditional_rules,
            tracks,
            Path("/test/movie.mkv"),
            language_results=language_results,
        )

        # Should match second rule (warn about missing forced subs)
        assert result.matched_rule == "Warn about missing forced subs"
        assert len(result.warnings) == 1
        assert "no forced English subtitles" in result.warnings[0]


# =============================================================================
# Feature Tests (formerly Backward Compatibility)
# =============================================================================


class TestLanguageAnalysisFeatures:
    """Tests for language analysis policy features."""

    def test_policy_with_conditional_rules_loads(self, v6_policy_no_v7_features: Path):
        """Test that policy with conditional rules loads correctly."""
        policy = load_policy(v6_policy_no_v7_features)

        assert policy.schema_version == 12
        assert len(policy.conditional_rules) == 1
        assert policy.conditional_rules[0].name == "Skip 4K HEVC"
