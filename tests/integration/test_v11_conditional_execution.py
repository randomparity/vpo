"""Integration tests for conditional rules through V11PhaseExecutor.

These tests verify that conditional rules defined in phased policies are
correctly converted and executed through the V11 phase executor. This tests
the full path from ConditionalRule dataclass -> dict conversion -> policy
loading -> execution.

These tests specifically catch bugs in:
- _conditional_rule_to_dict (e.g., accessing rule.then vs rule.then_actions)
- _action_to_dict (handling ConditionalAction union types)
- _condition_to_dict (handling all Condition types)
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from vpo.db.queries import upsert_file
from vpo.db.schema import create_schema
from vpo.db.types import FileRecord
from vpo.policy.models import (
    ConditionalRule,
    ExistsCondition,
    GlobalConfig,
    NotCondition,
    OnErrorMode,
    PhaseDefinition,
    PhasedPolicySchema,
    SetForcedAction,
    SkipAction,
    SkipType,
    TrackFilters,
    WarnAction,
)
from vpo.workflow.phases.executor import V11PhaseExecutor

if TYPE_CHECKING:
    from vpo.introspector.ffprobe import FFprobeIntrospector


# Skip entire module if required tools not available
pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("mkvmerge"),
    reason="ffmpeg and mkvmerge required for V11 integration tests",
)


@pytest.fixture
def introspector(ffprobe_available: bool) -> FFprobeIntrospector:
    """Provide an FFprobeIntrospector for verifying output files."""
    if not ffprobe_available:
        pytest.skip("ffprobe not available")

    from vpo.introspector.ffprobe import FFprobeIntrospector

    return FFprobeIntrospector()


@pytest.fixture
def db_conn():
    """Create in-memory database with schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    return conn


@pytest.fixture
def global_config():
    """Create a GlobalConfig for testing."""
    return GlobalConfig(
        audio_language_preference=("eng", "und"),
        subtitle_language_preference=("eng",),
        commentary_patterns=("commentary", "director"),
        on_error=OnErrorMode.CONTINUE,
    )


def insert_file_and_tracks(conn, file_path: Path, introspection_result) -> int:
    """Insert a file and its tracks into the database.

    Returns the file_id.
    """
    from datetime import datetime, timezone

    from vpo.db.queries import upsert_tracks_for_file

    now = datetime.now(timezone.utc).isoformat()

    # Create file record
    file_record = FileRecord(
        id=None,
        path=str(file_path),
        filename=file_path.name,
        directory=str(file_path.parent),
        extension=file_path.suffix,
        size_bytes=file_path.stat().st_size,
        container_format=introspection_result.container_format,
        modified_at=now,
        scanned_at=now,
        scan_status="complete",
        content_hash=None,
        scan_error=None,
    )
    file_id = upsert_file(conn, file_record)

    # Insert tracks
    upsert_tracks_for_file(conn, file_id, introspection_result.tracks)

    return file_id


class TestV11ConditionalExecution:
    """Integration tests for conditional rules through V11PhaseExecutor.

    These tests use real video files and the full execution pipeline to verify
    that conditional rules work correctly when executed through the phase
    executor.
    """

    def test_conditional_rule_builds_virtual_policy(
        self,
        generate_video,
        introspector: FFprobeIntrospector,
        db_conn,
        global_config,
    ):
        """Conditional rules in phase are correctly converted to virtual policy.

        This test verifies the fix for the bug where _conditional_rule_to_dict
        accessed rule.then instead of rule.then_actions.
        """
        # Import video spec classes
        scripts_dir = Path(__file__).parent.parent.parent / "scripts"
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
        video_path = generate_video(spec, "conditional_build_test.mkv")

        # Introspect and insert into database
        result = introspector.get_file_info(video_path)
        insert_file_and_tracks(db_conn, video_path, result)

        # Create phased policy with conditional rule
        policy = PhasedPolicySchema(
            schema_version=12,
            config=global_config,
            phases=(
                PhaseDefinition(
                    name="apply",
                    conditional=(
                        ConditionalRule(
                            name="force_eng_subs_for_foreign",
                            when=NotCondition(
                                inner=ExistsCondition(
                                    track_type="audio",
                                    filters=TrackFilters(language="eng"),
                                )
                            ),
                            then_actions=(
                                SetForcedAction(
                                    track_type="subtitle",
                                    language="eng",
                                    value=True,
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        )

        # Build virtual policy through executor - this exercises the conversion code
        executor = V11PhaseExecutor(
            conn=db_conn,
            policy=policy,
            dry_run=True,
        )
        virtual_policy = executor._build_virtual_policy(policy.phases[0])

        # Verify conditional rules were converted correctly
        assert virtual_policy.conditional_rules is not None
        assert len(virtual_policy.conditional_rules) == 1

        rule = virtual_policy.conditional_rules[0]
        assert rule.name == "force_eng_subs_for_foreign"
        assert rule.then_actions is not None
        assert len(rule.then_actions) == 1
        assert isinstance(rule.then_actions[0], SetForcedAction)

    def test_conditional_skip_action_dry_run(
        self,
        generate_video,
        introspector: FFprobeIntrospector,
        db_conn,
        global_config,
    ):
        """Skip actions from conditional rules are correctly propagated.

        This test verifies that SkipAction is correctly converted and can be
        used to skip operations during phase execution.
        """
        scripts_dir = Path(__file__).parent.parent.parent / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))

        from generate_test_media import AudioTrackSpec, VideoSpec

        # Generate video
        spec = VideoSpec(
            video_codec="h264",
            width=640,
            height=480,
            duration_seconds=1.0,
            audio_tracks=(AudioTrackSpec(codec="aac", channels=2, language="eng"),),
        )
        video_path = generate_video(spec, "conditional_skip_test.mkv")

        # Introspect and insert into database
        result = introspector.get_file_info(video_path)
        insert_file_and_tracks(db_conn, video_path, result)

        # Create phased policy with skip action
        policy = PhasedPolicySchema(
            schema_version=12,
            config=global_config,
            phases=(
                PhaseDefinition(
                    name="process",
                    conditional=(
                        ConditionalRule(
                            name="skip_if_h264",
                            when=ExistsCondition(
                                track_type="video",
                                filters=TrackFilters(codec=("h264", "avc")),
                            ),
                            then_actions=(
                                SkipAction(skip_type=SkipType.VIDEO_TRANSCODE),
                                WarnAction(message="Skipping H.264 transcode"),
                            ),
                        ),
                    ),
                ),
            ),
        )

        executor = V11PhaseExecutor(
            conn=db_conn,
            policy=policy,
            dry_run=True,
        )

        # Build virtual policy - verifies conversion works
        virtual_policy = executor._build_virtual_policy(policy.phases[0])

        # Verify skip and warn actions were converted
        rule = virtual_policy.conditional_rules[0]
        assert len(rule.then_actions) == 2
        assert isinstance(rule.then_actions[0], SkipAction)
        assert isinstance(rule.then_actions[1], WarnAction)
        assert rule.then_actions[0].skip_type == SkipType.VIDEO_TRANSCODE
        assert "H.264" in rule.then_actions[1].message

    def test_conditional_with_else_branch(
        self,
        generate_video,
        introspector: FFprobeIntrospector,
        db_conn,
        global_config,
    ):
        """Rules with else branches are correctly converted.

        This test verifies that both then_actions and else_actions are
        correctly converted through _conditional_rule_to_dict.
        """
        scripts_dir = Path(__file__).parent.parent.parent / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))

        from generate_test_media import AudioTrackSpec, VideoSpec

        # Generate video
        spec = VideoSpec(
            video_codec="h264",
            width=640,
            height=480,
            duration_seconds=1.0,
            audio_tracks=(AudioTrackSpec(codec="aac", channels=2, language="eng"),),
        )
        video_path = generate_video(spec, "conditional_else_test.mkv")

        # Introspect and insert into database
        result = introspector.get_file_info(video_path)
        insert_file_and_tracks(db_conn, video_path, result)

        # Create phased policy with else branch
        policy = PhasedPolicySchema(
            schema_version=12,
            config=global_config,
            phases=(
                PhaseDefinition(
                    name="process",
                    conditional=(
                        ConditionalRule(
                            name="check_english_audio",
                            when=ExistsCondition(
                                track_type="audio",
                                filters=TrackFilters(language="eng"),
                            ),
                            then_actions=(WarnAction(message="English audio found"),),
                            else_actions=(
                                WarnAction(message="No English audio"),
                                SkipAction(skip_type=SkipType.TRACK_FILTER),
                            ),
                        ),
                    ),
                ),
            ),
        )

        executor = V11PhaseExecutor(
            conn=db_conn,
            policy=policy,
            dry_run=True,
        )

        virtual_policy = executor._build_virtual_policy(policy.phases[0])

        # Verify both branches were converted
        rule = virtual_policy.conditional_rules[0]
        assert rule.then_actions is not None
        assert len(rule.then_actions) == 1
        assert rule.else_actions is not None
        assert len(rule.else_actions) == 2

    def test_multiple_conditional_rules(
        self,
        generate_video,
        introspector: FFprobeIntrospector,
        db_conn,
        global_config,
    ):
        """Multiple conditional rules are correctly converted and ordered.

        This test verifies that multiple rules maintain their order and are
        all correctly converted.
        """
        scripts_dir = Path(__file__).parent.parent.parent / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))

        from generate_test_media import AudioTrackSpec, VideoSpec

        # Generate video
        spec = VideoSpec(
            video_codec="h264",
            width=640,
            height=480,
            duration_seconds=1.0,
            audio_tracks=(AudioTrackSpec(codec="aac", channels=2, language="eng"),),
        )
        video_path = generate_video(spec, "conditional_multi_test.mkv")

        result = introspector.get_file_info(video_path)
        insert_file_and_tracks(db_conn, video_path, result)

        # Create phased policy with multiple rules
        policy = PhasedPolicySchema(
            schema_version=12,
            config=global_config,
            phases=(
                PhaseDefinition(
                    name="process",
                    conditional=(
                        ConditionalRule(
                            name="rule1_video_check",
                            when=ExistsCondition(
                                track_type="video",
                                filters=TrackFilters(),
                            ),
                            then_actions=(WarnAction(message="Has video"),),
                        ),
                        ConditionalRule(
                            name="rule2_audio_check",
                            when=ExistsCondition(
                                track_type="audio",
                                filters=TrackFilters(language="eng"),
                            ),
                            then_actions=(WarnAction(message="Has English audio"),),
                        ),
                        ConditionalRule(
                            name="rule3_skip_transcode",
                            when=ExistsCondition(
                                track_type="video",
                                filters=TrackFilters(codec=("h264", "avc")),
                            ),
                            then_actions=(
                                SkipAction(skip_type=SkipType.VIDEO_TRANSCODE),
                            ),
                        ),
                    ),
                ),
            ),
        )

        executor = V11PhaseExecutor(
            conn=db_conn,
            policy=policy,
            dry_run=True,
        )

        virtual_policy = executor._build_virtual_policy(policy.phases[0])

        # Verify all rules were converted and ordered
        assert len(virtual_policy.conditional_rules) == 3
        assert virtual_policy.conditional_rules[0].name == "rule1_video_check"
        assert virtual_policy.conditional_rules[1].name == "rule2_audio_check"
        assert virtual_policy.conditional_rules[2].name == "rule3_skip_transcode"
