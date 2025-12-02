"""Integration tests for conditional set_forced subtitle action.

Tests that set_forced actions from conditional rules are properly applied
to produce SET_FORCED PlannedActions and can be executed on real files.

This tests the fix for the bug where track_flag_changes from conditional
rules were computed but never propagated to the final Plan.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from video_policy_orchestrator.policy.evaluator import evaluate_policy
from video_policy_orchestrator.policy.loader import load_policy
from video_policy_orchestrator.policy.models import ActionType

if TYPE_CHECKING:
    from video_policy_orchestrator.introspector.ffprobe import FFprobeIntrospector


class TestConditionalForcedSubtitle:
    """Test set_forced action with real media files.

    Regression tests for the bug where conditional set_forced actions
    were not being converted to PlannedActions.
    """

    def test_german_audio_forces_english_subtitle(
        self,
        generate_video,
        introspector: FFprobeIntrospector,
        tmp_path: Path,
        ffmpeg_available: bool,
        mkvmerge_available: bool,
    ) -> None:
        """English subtitle should be forced when only German audio exists.

        This is the primary regression test for the bug where set_forced
        conditional actions were not creating SET_FORCED PlannedActions.
        """
        if not ffmpeg_available:
            pytest.skip("ffmpeg not available")
        if not mkvmerge_available:
            pytest.skip("mkvmerge not available for subtitle generation")

        # Import video spec classes
        import sys

        scripts_dir = Path(__file__).parent.parent.parent.parent / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))

        from generate_test_media import AudioTrackSpec, SubtitleTrackSpec, VideoSpec

        # Generate video with German audio + English subtitle
        spec = VideoSpec(
            video_codec="h264",
            width=640,
            height=480,
            duration_seconds=1.0,
            audio_tracks=(
                AudioTrackSpec(
                    codec="aac", channels=2, language="ger", title="German Audio"
                ),
            ),
            subtitle_tracks=(SubtitleTrackSpec(language="eng", title="English"),),
        )
        video_path = generate_video(spec, "german_audio_eng_subs.mkv")

        # Create policy with conditional set_forced
        policy_path = tmp_path / "force_subs_policy.yaml"
        policy_path.write_text("""
schema_version: 12

subtitle_language_preference: [eng, und]

conditional:
  - name: force_english_subs_for_foreign_audio
    when:
      not:
        exists:
          track_type: audio
          language: eng
    then:
      - set_forced:
          track_type: subtitle
          language: eng
          value: true
""")

        # Introspect the video
        result = introspector.get_file_info(video_path)
        tracks = result.tracks

        # Verify test setup: should have German audio and English subtitle
        audio_tracks = [t for t in tracks if t.track_type == "audio"]
        subtitle_tracks = [t for t in tracks if t.track_type == "subtitle"]
        assert len(audio_tracks) == 1
        assert audio_tracks[0].language == "ger"
        assert len(subtitle_tracks) == 1
        assert subtitle_tracks[0].language == "eng"
        assert subtitle_tracks[0].is_forced is False  # Not forced initially

        # Load policy and evaluate
        policy = load_policy(policy_path)
        plan = evaluate_policy(
            file_id=None,
            file_path=video_path,
            container="mkv",
            tracks=tracks,
            policy=policy,
        )

        # Verify SET_FORCED action exists
        forced_actions = [
            a for a in plan.actions if a.action_type == ActionType.SET_FORCED
        ]
        assert len(forced_actions) == 1, (
            f"Expected 1 SET_FORCED action, got {len(forced_actions)}. "
            f"All actions: {[a.action_type for a in plan.actions]}"
        )

        action = forced_actions[0]
        eng_sub = subtitle_tracks[0]
        assert action.track_index == eng_sub.index
        assert action.current_value is False
        assert action.desired_value is True

    def test_english_audio_does_not_force_subtitle(
        self,
        generate_video,
        introspector: FFprobeIntrospector,
        tmp_path: Path,
        ffmpeg_available: bool,
        mkvmerge_available: bool,
    ) -> None:
        """English subtitle should NOT be forced when English audio exists.

        This ensures the conditional rule only triggers when appropriate.
        """
        if not ffmpeg_available:
            pytest.skip("ffmpeg not available")
        if not mkvmerge_available:
            pytest.skip("mkvmerge not available for subtitle generation")

        import sys

        scripts_dir = Path(__file__).parent.parent.parent.parent / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))

        from generate_test_media import AudioTrackSpec, SubtitleTrackSpec, VideoSpec

        # Generate video with English audio + English subtitle
        spec = VideoSpec(
            video_codec="h264",
            width=640,
            height=480,
            duration_seconds=1.0,
            audio_tracks=(
                AudioTrackSpec(
                    codec="aac", channels=2, language="eng", title="English Audio"
                ),
            ),
            subtitle_tracks=(SubtitleTrackSpec(language="eng", title="English"),),
        )
        video_path = generate_video(spec, "english_audio_eng_subs.mkv")

        # Same policy as above
        policy_path = tmp_path / "force_subs_policy.yaml"
        policy_path.write_text("""
schema_version: 12

subtitle_language_preference: [eng, und]

conditional:
  - name: force_english_subs_for_foreign_audio
    when:
      not:
        exists:
          track_type: audio
          language: eng
    then:
      - set_forced:
          track_type: subtitle
          language: eng
          value: true
""")

        result = introspector.get_file_info(video_path)
        tracks = result.tracks

        policy = load_policy(policy_path)
        plan = evaluate_policy(
            file_id=None,
            file_path=video_path,
            container="mkv",
            tracks=tracks,
            policy=policy,
        )

        # Should NOT have SET_FORCED action (English audio exists)
        forced_actions = [
            a for a in plan.actions if a.action_type == ActionType.SET_FORCED
        ]
        assert len(forced_actions) == 0, (
            f"Expected no SET_FORCED actions (English audio exists), "
            f"got {len(forced_actions)}"
        )

    def test_conditional_result_contains_trace(
        self,
        generate_video,
        introspector: FFprobeIntrospector,
        tmp_path: Path,
        ffmpeg_available: bool,
        mkvmerge_available: bool,
    ) -> None:
        """Conditional result should contain evaluation trace for debugging."""
        if not ffmpeg_available:
            pytest.skip("ffmpeg not available")
        if not mkvmerge_available:
            pytest.skip("mkvmerge not available for subtitle generation")

        import sys

        scripts_dir = Path(__file__).parent.parent.parent.parent / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))

        from generate_test_media import AudioTrackSpec, SubtitleTrackSpec, VideoSpec

        spec = VideoSpec(
            video_codec="h264",
            width=640,
            height=480,
            duration_seconds=1.0,
            audio_tracks=(
                AudioTrackSpec(
                    codec="aac", channels=2, language="ger", title="German Audio"
                ),
            ),
            subtitle_tracks=(SubtitleTrackSpec(language="eng", title="English"),),
        )
        video_path = generate_video(spec, "trace_test.mkv")

        policy_path = tmp_path / "policy.yaml"
        policy_path.write_text("""
schema_version: 12

conditional:
  - name: force_english_subs_for_foreign_audio
    when:
      not:
        exists:
          track_type: audio
          language: eng
    then:
      - set_forced:
          track_type: subtitle
          language: eng
          value: true
""")

        result = introspector.get_file_info(video_path)
        tracks = result.tracks

        policy = load_policy(policy_path)
        plan = evaluate_policy(
            file_id=None,
            file_path=video_path,
            container="mkv",
            tracks=tracks,
            policy=policy,
        )

        # Verify conditional_result is populated
        assert plan.conditional_result is not None
        assert (
            plan.conditional_result.matched_rule
            == "force_english_subs_for_foreign_audio"
        )
        assert plan.conditional_result.matched_branch == "then"
        assert len(plan.conditional_result.evaluation_trace) == 1
        assert len(plan.conditional_result.track_flag_changes) == 1
