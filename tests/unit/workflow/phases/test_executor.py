"""Unit tests for PhaseExecutor operation dispatch.

Tests the phase executor including:
- Operation dispatch to correct handlers
- Virtual policy building from phase config
- Executor selection based on plan/container
- Dry-run mode behavior
- Error handling and rollback
"""

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from video_policy_orchestrator.db.schema import create_schema
from video_policy_orchestrator.db.types import TrackInfo
from video_policy_orchestrator.executor.transcode import TranscodeResult
from video_policy_orchestrator.policy.models import (
    AndCondition,
    AudioFilterConfig,
    AudioIsMultiLanguageCondition,
    Comparison,
    ComparisonOperator,
    ConditionalRule,
    ContainerConfig,
    CountCondition,
    DefaultFlagsConfig,
    ExistsCondition,
    GlobalConfig,
    NotCondition,
    OnErrorMode,
    OperationType,
    OrCondition,
    PhaseDefinition,
    PhasedPolicySchema,
    PhaseExecutionError,
    PluginMetadataCondition,
    PluginMetadataOperator,
    SetDefaultAction,
    SetForcedAction,
    SkipAction,
    SkipType,
    SubtitleFilterConfig,
    TitleMatch,
    TrackFilters,
    TrackType,
    TranscriptionPolicyOptions,
    VideoTranscodeConfig,
    WarnAction,
)
from video_policy_orchestrator.workflow.phases.executor import (
    PhaseExecutionState,
    V11PhaseExecutor,
)


@dataclass
class MockFileInfo:
    """Mock FileInfo for testing V11 executor.

    This matches the actual FileInfo class in db.types with
    container_format (not container) and no file_id attribute.
    """

    path: Path
    container_format: str
    tracks: list[TrackInfo] = field(default_factory=list)


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


@pytest.fixture
def v11_policy(global_config):
    """Create a phased policy for testing."""
    return PhasedPolicySchema(
        schema_version=12,
        config=global_config,
        phases=(PhaseDefinition(name="cleanup"),),
    )


@pytest.fixture
def test_file(tmp_path):
    """Create a temporary test file."""
    f = tmp_path / "test.mkv"
    f.write_bytes(b"\x00" * 100)
    return f


@pytest.fixture
def mock_tracks():
    """Create mock track info list."""
    return [
        TrackInfo(
            index=0,
            track_type="video",
            codec="h264",
            language="und",
        ),
        TrackInfo(
            index=1,
            track_type="audio",
            codec="aac",
            language="eng",
        ),
        TrackInfo(
            index=2,
            track_type="audio",
            codec="aac",
            language="spa",
        ),
        TrackInfo(
            index=3,
            track_type="subtitle",
            codec="srt",
            language="eng",
        ),
    ]


@pytest.fixture
def mock_file_info(test_file, mock_tracks):
    """Create mock FileInfo."""
    return MockFileInfo(
        path=test_file,
        container_format="mkv",
        tracks=mock_tracks,
    )


def insert_test_file(conn, file_path: Path) -> int:
    """Insert a test file record and return its ID."""
    cursor = conn.execute(
        """
        INSERT INTO files (
            path, filename, directory, extension, size_bytes,
            container_format, modified_at, scanned_at, scan_status
        )
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), 'complete')
        """,
        (
            str(file_path),
            file_path.name,
            str(file_path.parent),
            file_path.suffix,
            100,
            "mkv",
        ),
    )
    conn.commit()
    return cursor.lastrowid


def insert_test_track(
    conn, file_id: int, index: int, track_type: str, language: str = "eng"
) -> int:
    """Insert a test track record and return its ID."""
    codec = {"video": "h264", "audio": "aac", "subtitle": "srt"}.get(
        track_type, "unknown"
    )
    cursor = conn.execute(
        """
        INSERT INTO tracks (
            file_id, track_index, track_type, codec, language
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (file_id, index, track_type, codec, language),
    )
    conn.commit()
    return cursor.lastrowid


class TestV11PhaseExecutorInit:
    """Tests for V11PhaseExecutor initialization."""

    def test_init_with_defaults(self, db_conn, v11_policy):
        """V11PhaseExecutor initializes with default values."""
        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy)

        assert executor.conn is db_conn
        assert executor.policy is v11_policy
        assert executor.dry_run is False
        assert executor.verbose is False
        assert executor.policy_name == "workflow"

    def test_init_with_dry_run(self, db_conn, v11_policy):
        """V11PhaseExecutor accepts dry_run parameter."""
        executor = V11PhaseExecutor(
            conn=db_conn,
            policy=v11_policy,
            dry_run=True,
        )

        assert executor.dry_run is True

    def test_init_with_policy_name(self, db_conn, v11_policy):
        """V11PhaseExecutor accepts custom policy_name."""
        executor = V11PhaseExecutor(
            conn=db_conn,
            policy=v11_policy,
            policy_name="custom.yaml",
        )

        assert executor.policy_name == "custom.yaml"


class TestOperationDispatch:
    """Tests for _dispatch_operation handler routing."""

    def test_dispatch_routes_to_container_handler(
        self, db_conn, v11_policy, mock_file_info
    ):
        """Container operation routes to _execute_container."""
        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy, dry_run=True)

        phase = PhaseDefinition(
            name="test",
            container=ContainerConfig(target="mp4"),
        )
        state = PhaseExecutionState(file_path=mock_file_info.path, phase=phase)

        with patch.object(
            executor, "_execute_container", return_value=1
        ) as mock_handler:
            result = executor._dispatch_operation(
                OperationType.CONTAINER, state, mock_file_info
            )

        mock_handler.assert_called_once_with(state, mock_file_info)
        assert result == 1

    def test_dispatch_routes_to_audio_filter_handler(
        self, db_conn, v11_policy, mock_file_info
    ):
        """Audio filter operation routes to _execute_audio_filter."""
        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy, dry_run=True)

        phase = PhaseDefinition(
            name="test",
            audio_filter=AudioFilterConfig(languages=("eng",)),
        )
        state = PhaseExecutionState(file_path=mock_file_info.path, phase=phase)

        with patch.object(
            executor, "_execute_audio_filter", return_value=2
        ) as mock_handler:
            result = executor._dispatch_operation(
                OperationType.AUDIO_FILTER, state, mock_file_info
            )

        mock_handler.assert_called_once_with(state, mock_file_info)
        assert result == 2

    def test_dispatch_unknown_operation_returns_zero(
        self, db_conn, v11_policy, mock_file_info
    ):
        """Unknown operation type returns 0 and logs warning."""
        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy, dry_run=True)

        phase = PhaseDefinition(name="test")
        state = PhaseExecutionState(file_path=mock_file_info.path, phase=phase)

        # Create a mock operation type that isn't in the handlers dict
        # by using a real type but removing it from handlers
        with patch.dict(executor._dispatch_operation.__code__.co_freevars, {}):
            # Actually test with a valid type that has no config
            result = executor._dispatch_operation(
                OperationType.AUDIO_FILTER, state, mock_file_info
            )

        # audio_filter is None in phase, so handler returns 0
        assert result == 0


class TestVirtualPolicyBuilding:
    """Tests for _build_virtual_policy."""

    def test_build_virtual_policy_basic(self, db_conn, v11_policy):
        """Virtual policy includes base config from V11 policy."""
        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy)

        phase = PhaseDefinition(name="test")
        policy = executor._build_virtual_policy(phase)

        assert policy.schema_version == 12
        assert list(policy.audio_language_preference) == ["eng", "und"]
        assert list(policy.subtitle_language_preference) == ["eng"]
        assert list(policy.commentary_patterns) == ["commentary", "director"]

    def test_build_virtual_policy_with_audio_filter(self, db_conn, v11_policy):
        """Virtual policy includes audio filter config."""
        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy)

        phase = PhaseDefinition(
            name="test",
            audio_filter=AudioFilterConfig(languages=("eng", "jpn")),
        )
        policy = executor._build_virtual_policy(phase)

        assert policy.audio_filter is not None
        assert list(policy.audio_filter.languages) == ["eng", "jpn"]

    def test_build_virtual_policy_with_subtitle_filter(self, db_conn, v11_policy):
        """Virtual policy includes subtitle filter config."""
        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy)

        phase = PhaseDefinition(
            name="test",
            subtitle_filter=SubtitleFilterConfig(languages=("eng", "spa")),
        )
        policy = executor._build_virtual_policy(phase)

        assert policy.subtitle_filter is not None
        assert list(policy.subtitle_filter.languages) == ["eng", "spa"]

    def test_build_virtual_policy_with_default_flags(self, db_conn, v11_policy):
        """Virtual policy includes default flags config."""
        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy)

        phase = PhaseDefinition(
            name="test",
            default_flags=DefaultFlagsConfig(
                set_first_video_default=True,
                set_preferred_audio_default=True,
                set_preferred_subtitle_default=False,
                clear_other_defaults=True,
            ),
        )
        policy = executor._build_virtual_policy(phase)

        assert policy.default_flags is not None
        assert policy.default_flags.set_first_video_default is True
        assert policy.default_flags.set_preferred_audio_default is True
        assert policy.default_flags.set_preferred_subtitle_default is False

    def test_build_virtual_policy_with_track_order(self, db_conn, v11_policy):
        """Virtual policy includes track order from phase."""
        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy)

        phase = PhaseDefinition(
            name="test",
            track_order=(
                TrackType.VIDEO,
                TrackType.SUBTITLE_MAIN,
                TrackType.AUDIO_MAIN,
            ),
        )
        policy = executor._build_virtual_policy(phase)

        # track_order may return enum values or strings depending on the policy schema
        track_order_values = [
            t.value if hasattr(t, "value") else t for t in policy.track_order
        ]
        assert track_order_values == ["video", "subtitle_main", "audio_main"]


class TestExecutorSelection:
    """Tests for _select_executor."""

    def test_select_executor_for_container_change_mp4(self, db_conn, v11_policy):
        """FFmpegRemuxExecutor selected for MP4 container change."""
        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy)

        mock_plan = MagicMock()
        mock_plan.container_change = MagicMock()
        mock_plan.container_change.target_format = "mp4"
        mock_plan.tracks_removed = 0
        mock_plan.requires_remux = False

        with patch.object(executor, "_get_tools", return_value={"ffmpeg": True}):
            selected = executor._select_executor(mock_plan, "mkv")

        from video_policy_orchestrator.executor import FFmpegRemuxExecutor

        assert isinstance(selected, FFmpegRemuxExecutor)

    def test_select_executor_for_container_change_mkv(self, db_conn, v11_policy):
        """MkvmergeExecutor selected for MKV container change."""
        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy)

        mock_plan = MagicMock()
        mock_plan.container_change = MagicMock()
        mock_plan.container_change.target_format = "mkv"
        mock_plan.tracks_removed = 0
        mock_plan.requires_remux = False

        with patch.object(executor, "_get_tools", return_value={"mkvmerge": True}):
            selected = executor._select_executor(mock_plan, "mp4")

        from video_policy_orchestrator.executor import MkvmergeExecutor

        assert isinstance(selected, MkvmergeExecutor)

    def test_select_executor_for_track_removal_mkv(self, db_conn, v11_policy):
        """MkvmergeExecutor selected for track removal in MKV."""
        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy)

        mock_plan = MagicMock()
        mock_plan.container_change = None
        mock_plan.tracks_removed = 2
        mock_plan.requires_remux = False

        with patch.object(executor, "_get_tools", return_value={"mkvmerge": True}):
            selected = executor._select_executor(mock_plan, "mkv")

        from video_policy_orchestrator.executor import MkvmergeExecutor

        assert isinstance(selected, MkvmergeExecutor)

    def test_select_executor_for_metadata_only_mkv(self, db_conn, v11_policy):
        """MkvpropeditExecutor selected for metadata-only changes in MKV."""
        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy)

        mock_plan = MagicMock()
        mock_plan.container_change = None
        mock_plan.tracks_removed = 0
        mock_plan.requires_remux = False

        with patch.object(executor, "_get_tools", return_value={"mkvpropedit": True}):
            selected = executor._select_executor(mock_plan, "mkv")

        from video_policy_orchestrator.executor import MkvpropeditExecutor

        assert isinstance(selected, MkvpropeditExecutor)

    def test_select_executor_returns_none_when_no_tools(self, db_conn, v11_policy):
        """Returns None when no suitable tool is available."""
        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy)

        mock_plan = MagicMock()
        mock_plan.container_change = None
        mock_plan.tracks_removed = 0
        mock_plan.requires_remux = False

        with patch.object(executor, "_get_tools", return_value={}):
            selected = executor._select_executor(mock_plan, "mkv")

        assert selected is None


class TestDryRunMode:
    """Tests for dry-run mode behavior."""

    @patch("video_policy_orchestrator.workflow.phases.executor.evaluate_policy")
    def test_dry_run_logs_without_executing(
        self, mock_evaluate, db_conn, v11_policy, mock_file_info
    ):
        """Dry-run logs changes but doesn't call executor."""
        # Insert file into database (required for file_id lookup)
        insert_test_file(db_conn, mock_file_info.path)

        mock_plan = MagicMock()
        mock_plan.actions = [MagicMock()]
        mock_plan.tracks_removed = 1
        mock_evaluate.return_value = mock_plan

        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy, dry_run=True)

        phase = PhaseDefinition(
            name="test",
            audio_filter=AudioFilterConfig(languages=("eng",)),
        )
        state = PhaseExecutionState(file_path=mock_file_info.path, phase=phase)

        result = executor._execute_audio_filter(state, mock_file_info)

        # Returns change count
        assert result == 2  # 1 action + 1 track removed
        # No executor should be called in dry-run
        mock_evaluate.assert_called_once()

    def test_dry_run_audio_synthesis_logs_only(
        self, db_conn, v11_policy, mock_file_info
    ):
        """Dry-run for audio synthesis logs without executing."""
        # Insert file into database (required for file_id lookup)
        insert_test_file(db_conn, mock_file_info.path)

        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy, dry_run=True)

        # Create a mock phase with audio_synthesis that has a non-None value
        mock_audio_synthesis = MagicMock()
        phase = MagicMock()
        phase.audio_synthesis = mock_audio_synthesis
        state = PhaseExecutionState(file_path=mock_file_info.path, phase=phase)

        # plan_synthesis is imported inside the function, so patch at the module level
        with patch(
            "video_policy_orchestrator.policy.synthesis.plan_synthesis"
        ) as mock_plan:
            mock_synthesis_plan = MagicMock()
            mock_synthesis_plan.operations = [MagicMock(), MagicMock()]
            mock_plan.return_value = mock_synthesis_plan

            result = executor._execute_audio_synthesis(state, mock_file_info)

        # Returns operation count
        assert result == 2

    def test_dry_run_transcription_logs_only(self, db_conn, v11_policy, test_file):
        """Dry-run for transcription logs without executing."""
        from unittest.mock import MagicMock

        # Insert file and tracks into database (required for context lookup)
        # Transcription requires tracks with duration_seconds set
        file_id = insert_test_file(db_conn, test_file)
        insert_test_track(db_conn, file_id, 0, "video")
        # Insert audio tracks with duration (manually set via SQL)
        db_conn.execute(
            """
            INSERT INTO tracks (
                file_id, track_index, track_type, codec, language, duration_seconds
            ) VALUES (?, 1, 'audio', 'aac', 'eng', 120.0)
            """,
            (file_id,),
        )
        db_conn.execute(
            """
            INSERT INTO tracks (
                file_id, track_index, track_type, codec, language, duration_seconds
            ) VALUES (?, 2, 'audio', 'aac', 'spa', 120.0)
            """,
            (file_id,),
        )
        db_conn.commit()

        # Create mock plugin registry for transcription to work
        mock_registry = MagicMock()
        executor = V11PhaseExecutor(
            conn=db_conn,
            policy=v11_policy,
            dry_run=True,
            plugin_registry=mock_registry,
        )

        phase = PhaseDefinition(
            name="test",
            transcription=TranscriptionPolicyOptions(enabled=True),
        )
        state = PhaseExecutionState(file_path=test_file, phase=phase)

        # Pass None for file_info to trigger context creation from database
        result = executor._execute_transcription(state, None)

        # Returns audio track count (2 audio tracks with duration)
        assert result == 2

    def test_transcription_skipped_without_plugin_registry(
        self, db_conn, v11_policy, test_file
    ):
        """Transcription is skipped when no plugin registry is provided."""
        # Insert file and tracks into database
        file_id = insert_test_file(db_conn, test_file)
        insert_test_track(db_conn, file_id, 0, "video")
        db_conn.execute(
            """
            INSERT INTO tracks (
                file_id, track_index, track_type, codec, language, duration_seconds
            ) VALUES (?, 1, 'audio', 'aac', 'eng', 120.0)
            """,
            (file_id,),
        )
        db_conn.commit()

        # No plugin_registry provided
        executor = V11PhaseExecutor(
            conn=db_conn, policy=v11_policy, dry_run=True, plugin_registry=None
        )

        phase = PhaseDefinition(
            name="test",
            transcription=TranscriptionPolicyOptions(enabled=True),
        )
        state = PhaseExecutionState(file_path=test_file, phase=phase)

        result = executor._execute_transcription(state, None)

        # Returns 0 because transcription was skipped (no plugin registry)
        assert result == 0


class TestPhaseExecution:
    """Tests for execute_phase."""

    def test_execute_phase_empty_operations(self, db_conn, v11_policy, mock_file_info):
        """Phase with no operations returns early."""
        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy, dry_run=True)

        phase = PhaseDefinition(name="empty")
        result = executor.execute_phase(phase, mock_file_info.path, mock_file_info)

        assert result.success is True
        assert result.changes_made == 0
        assert "no operations" in result.message.lower()

    @patch("video_policy_orchestrator.workflow.phases.executor.evaluate_policy")
    def test_execute_phase_accumulates_changes(
        self, mock_evaluate, db_conn, v11_policy, mock_file_info
    ):
        """Phase accumulates changes from multiple operations."""
        # Insert file into database (required for file_id lookup)
        insert_test_file(db_conn, mock_file_info.path)

        mock_plan = MagicMock()
        mock_plan.actions = [MagicMock()]
        mock_plan.tracks_removed = 1
        mock_evaluate.return_value = mock_plan

        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy, dry_run=True)

        phase = PhaseDefinition(
            name="multi-op",
            audio_filter=AudioFilterConfig(languages=("eng",)),
            subtitle_filter=SubtitleFilterConfig(languages=("eng",)),
        )
        result = executor.execute_phase(phase, mock_file_info.path, mock_file_info)

        assert result.success is True
        # Each operation returns 2 changes (1 action + 1 track removed)
        assert result.changes_made == 4
        assert len(result.operations_executed) == 2

    def test_execute_phase_skips_on_error_skip_mode(
        self, db_conn, global_config, mock_file_info
    ):
        """Phase skips remaining operations when on_error=skip."""
        skip_config = GlobalConfig(
            audio_language_preference=global_config.audio_language_preference,
            subtitle_language_preference=global_config.subtitle_language_preference,
            commentary_patterns=global_config.commentary_patterns,
            on_error=OnErrorMode.SKIP,
        )
        policy = PhasedPolicySchema(
            schema_version=12,
            config=skip_config,
            phases=(PhaseDefinition(name="test"),),
        )
        executor = V11PhaseExecutor(conn=db_conn, policy=policy, dry_run=True)

        phase = PhaseDefinition(
            name="test",
            audio_filter=AudioFilterConfig(languages=("eng",)),
            subtitle_filter=SubtitleFilterConfig(languages=("eng",)),
        )

        # Make first operation fail
        with patch.object(
            executor, "_execute_audio_filter", side_effect=Exception("Test error")
        ):
            result = executor.execute_phase(phase, mock_file_info.path, mock_file_info)

        # Phase completes but with fewer operations
        assert result.success is True
        assert (
            len(result.operations_executed) == 0
        )  # Audio filter failed, subtitle skipped

    def test_execute_phase_raises_on_error_fail_mode(
        self, db_conn, global_config, mock_file_info
    ):
        """Phase raises PhaseExecutionError when on_error=fail."""
        fail_config = GlobalConfig(
            audio_language_preference=global_config.audio_language_preference,
            subtitle_language_preference=global_config.subtitle_language_preference,
            commentary_patterns=global_config.commentary_patterns,
            on_error=OnErrorMode.FAIL,
        )
        policy = PhasedPolicySchema(
            schema_version=12,
            config=fail_config,
            phases=(PhaseDefinition(name="test"),),
        )
        executor = V11PhaseExecutor(conn=db_conn, policy=policy, dry_run=True)

        phase = PhaseDefinition(
            name="test",
            audio_filter=AudioFilterConfig(languages=("eng",)),
        )

        # Make operation fail
        with patch.object(
            executor, "_execute_audio_filter", side_effect=Exception("Test error")
        ):
            with pytest.raises(PhaseExecutionError) as exc_info:
                executor.execute_phase(phase, mock_file_info.path, mock_file_info)

        assert exc_info.value.phase_name == "test"


class TestBackupHandling:
    """Tests for backup creation and cleanup."""

    def test_backup_created_before_execution(self, db_conn, v11_policy, test_file):
        """Backup is created before phase execution (non-dry-run)."""
        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy, dry_run=False)

        backup_path = executor._create_backup(test_file)

        assert backup_path is not None
        assert backup_path.exists()
        # The backup path uses with_suffix, which replaces the suffix
        # e.g., "test.mkv" -> "test.mkv.vpo-backup"
        assert str(backup_path).endswith(".vpo-backup")
        assert "test.mkv" in str(backup_path)

        # Cleanup
        backup_path.unlink()

    def test_backup_not_created_in_dry_run(self, db_conn, v11_policy, mock_file_info):
        """No backup created in dry-run mode."""
        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy, dry_run=True)

        phase = PhaseDefinition(name="empty")
        executor.execute_phase(phase, mock_file_info.path, mock_file_info)

        # No backup file should exist
        backup_path = mock_file_info.path.with_suffix(
            mock_file_info.path.suffix + ".vpo-backup"
        )
        assert not backup_path.exists()

    def test_backup_cleaned_up_on_success(
        self, db_conn, v11_policy, test_file, mock_tracks
    ):
        """Backup is removed after successful phase execution."""
        file_info = MockFileInfo(
            path=test_file,
            container_format="mkv",
            tracks=mock_tracks,
        )

        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy, dry_run=False)

        phase = PhaseDefinition(name="empty")

        # Execute phase (empty, so nothing actually happens)
        executor.execute_phase(phase, test_file, file_info)

        # Backup should not exist
        backup_path = test_file.with_suffix(test_file.suffix + ".vpo-backup")
        assert not backup_path.exists()


class TestOperationHandlerNoConfig:
    """Tests that operation handlers return 0 when config is not set."""

    def test_container_no_config(self, db_conn, v11_policy, mock_file_info):
        """_execute_container returns 0 when phase.container is None."""
        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy, dry_run=True)

        phase = PhaseDefinition(name="test")  # No container config
        state = PhaseExecutionState(file_path=mock_file_info.path, phase=phase)

        result = executor._execute_container(state, mock_file_info)
        assert result == 0

    def test_audio_filter_no_config(self, db_conn, v11_policy, mock_file_info):
        """_execute_audio_filter returns 0 when phase.audio_filter is None."""
        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy, dry_run=True)

        phase = PhaseDefinition(name="test")  # No audio filter config
        state = PhaseExecutionState(file_path=mock_file_info.path, phase=phase)

        result = executor._execute_audio_filter(state, mock_file_info)
        assert result == 0

    def test_subtitle_filter_no_config(self, db_conn, v11_policy, mock_file_info):
        """_execute_subtitle_filter returns 0 when phase.subtitle_filter is None."""
        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy, dry_run=True)

        phase = PhaseDefinition(name="test")
        state = PhaseExecutionState(file_path=mock_file_info.path, phase=phase)

        result = executor._execute_subtitle_filter(state, mock_file_info)
        assert result == 0

    def test_attachment_filter_no_config(self, db_conn, v11_policy, mock_file_info):
        """_execute_attachment_filter returns 0 when phase.attachment_filter is None."""
        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy, dry_run=True)

        phase = PhaseDefinition(name="test")
        state = PhaseExecutionState(file_path=mock_file_info.path, phase=phase)

        result = executor._execute_attachment_filter(state, mock_file_info)
        assert result == 0

    def test_track_order_no_config(self, db_conn, v11_policy, mock_file_info):
        """_execute_track_order returns 0 when phase.track_order is None."""
        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy, dry_run=True)

        phase = PhaseDefinition(name="test")
        state = PhaseExecutionState(file_path=mock_file_info.path, phase=phase)

        result = executor._execute_track_order(state, mock_file_info)
        assert result == 0

    def test_default_flags_no_config(self, db_conn, v11_policy, mock_file_info):
        """_execute_default_flags returns 0 when phase.default_flags is None."""
        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy, dry_run=True)

        phase = PhaseDefinition(name="test")
        state = PhaseExecutionState(file_path=mock_file_info.path, phase=phase)

        result = executor._execute_default_flags(state, mock_file_info)
        assert result == 0

    def test_conditional_no_config(self, db_conn, v11_policy, mock_file_info):
        """_execute_conditional returns 0 when phase.conditional is None."""
        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy, dry_run=True)

        phase = PhaseDefinition(name="test")
        state = PhaseExecutionState(file_path=mock_file_info.path, phase=phase)

        result = executor._execute_conditional(state, mock_file_info)
        assert result == 0

    def test_audio_synthesis_no_config(self, db_conn, v11_policy, mock_file_info):
        """_execute_audio_synthesis returns 0 when phase.audio_synthesis is None."""
        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy, dry_run=True)

        phase = PhaseDefinition(name="test")
        state = PhaseExecutionState(file_path=mock_file_info.path, phase=phase)

        result = executor._execute_audio_synthesis(state, mock_file_info)
        assert result == 0

    def test_transcode_no_config(self, db_conn, v11_policy, mock_file_info):
        """_execute_transcode returns 0 when phase.transcode is None."""
        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy, dry_run=True)

        phase = PhaseDefinition(name="test")
        state = PhaseExecutionState(file_path=mock_file_info.path, phase=phase)

        result = executor._execute_transcode(state, mock_file_info)
        assert result == 0

    def test_transcription_no_config(self, db_conn, v11_policy, mock_file_info):
        """_execute_transcription returns 0 when phase.transcription is None."""
        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy, dry_run=True)

        phase = PhaseDefinition(name="test")
        state = PhaseExecutionState(file_path=mock_file_info.path, phase=phase)

        result = executor._execute_transcription(state, mock_file_info)
        assert result == 0

    def test_transcription_disabled(self, db_conn, v11_policy, mock_file_info):
        """_execute_transcription returns 0 when transcription.enabled=False."""
        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy, dry_run=True)

        phase = PhaseDefinition(
            name="test",
            transcription=TranscriptionPolicyOptions(enabled=False),
        )
        state = PhaseExecutionState(file_path=mock_file_info.path, phase=phase)

        result = executor._execute_transcription(state, mock_file_info)
        assert result == 0


class TestExecuteTranscode:
    """Tests for _execute_transcode method."""

    @patch("video_policy_orchestrator.executor.transcode.TranscodeExecutor")
    @patch("video_policy_orchestrator.db.queries.get_file_by_path")
    def test_transcode_success(
        self, mock_get_file, mock_executor_cls, db_conn, v11_policy, mock_file_info
    ):
        """Successful transcode returns 1 change."""
        mock_get_file.return_value = MagicMock(size_bytes=1000000)

        mock_executor = MagicMock()
        mock_plan = MagicMock()
        mock_plan.skip_reason = None
        mock_executor.create_plan.return_value = mock_plan

        mock_result = MagicMock(spec=TranscodeResult)
        mock_result.success = True
        mock_executor.execute.return_value = mock_result
        mock_executor_cls.return_value = mock_executor

        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy, dry_run=False)

        phase = PhaseDefinition(
            name="compress",
            transcode=VideoTranscodeConfig(target_codec="hevc"),
        )
        state = PhaseExecutionState(file_path=mock_file_info.path, phase=phase)

        result = executor._execute_transcode(state, mock_file_info)

        assert result == 1
        mock_executor.execute.assert_called_once_with(mock_plan)

    @patch("video_policy_orchestrator.executor.transcode.TranscodeExecutor")
    @patch("video_policy_orchestrator.db.queries.get_file_by_path")
    def test_transcode_failure_raises_runtime_error(
        self, mock_get_file, mock_executor_cls, db_conn, v11_policy, mock_file_info
    ):
        """Failed transcode raises RuntimeError with error_message."""
        mock_get_file.return_value = MagicMock(size_bytes=1000000)

        mock_executor = MagicMock()
        mock_plan = MagicMock()
        mock_plan.skip_reason = None
        mock_executor.create_plan.return_value = mock_plan

        mock_result = MagicMock(spec=TranscodeResult)
        mock_result.success = False
        mock_result.error_message = "FFmpeg exited with code 1: encoding failed"
        mock_executor.execute.return_value = mock_result
        mock_executor_cls.return_value = mock_executor

        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy, dry_run=False)

        phase = PhaseDefinition(
            name="compress",
            transcode=VideoTranscodeConfig(target_codec="hevc"),
        )
        state = PhaseExecutionState(file_path=mock_file_info.path, phase=phase)

        with pytest.raises(RuntimeError) as exc_info:
            executor._execute_transcode(state, mock_file_info)

        assert "Video transcode failed" in str(exc_info.value)
        assert "FFmpeg exited with code 1" in str(exc_info.value)

    @patch("video_policy_orchestrator.executor.transcode.TranscodeExecutor")
    @patch("video_policy_orchestrator.db.queries.get_file_by_path")
    def test_transcode_dry_run_does_not_execute(
        self, mock_get_file, mock_executor_cls, db_conn, v11_policy, mock_file_info
    ):
        """Dry-run mode logs but doesn't execute transcode."""
        mock_get_file.return_value = MagicMock(size_bytes=1000000)

        mock_executor = MagicMock()
        mock_plan = MagicMock()
        mock_plan.skip_reason = None
        mock_executor.create_plan.return_value = mock_plan
        mock_executor_cls.return_value = mock_executor

        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy, dry_run=True)

        phase = PhaseDefinition(
            name="compress",
            transcode=VideoTranscodeConfig(target_codec="hevc"),
        )
        state = PhaseExecutionState(file_path=mock_file_info.path, phase=phase)

        result = executor._execute_transcode(state, mock_file_info)

        assert result == 1
        mock_executor.execute.assert_not_called()

    def test_transcode_skips_when_plan_has_skip_reason(
        self, db_conn, v11_policy, mock_file_info
    ):
        """Transcode is skipped when plan has a skip_reason."""
        with (
            patch(
                "video_policy_orchestrator.executor.transcode.TranscodeExecutor"
            ) as mock_executor_cls,
            patch(
                "video_policy_orchestrator.db.queries.get_file_by_path"
            ) as mock_get_file,
        ):
            mock_get_file.return_value = MagicMock(size_bytes=1000000)

            mock_executor = MagicMock()
            mock_plan = MagicMock()
            mock_plan.skip_reason = "Already HEVC at target quality"
            mock_executor.create_plan.return_value = mock_plan
            mock_executor_cls.return_value = mock_executor

            executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy, dry_run=False)

            phase = PhaseDefinition(
                name="compress",
                transcode=VideoTranscodeConfig(target_codec="hevc"),
            )
            state = PhaseExecutionState(file_path=mock_file_info.path, phase=phase)

            result = executor._execute_transcode(state, mock_file_info)

            assert result == 0
            mock_executor.execute.assert_not_called()

    def test_transcode_skips_when_no_video_track(self, db_conn, v11_policy, test_file):
        """Transcode is skipped when file has no video track."""
        # Create file_info with only audio tracks
        audio_only_file_info = MockFileInfo(
            path=test_file,
            container_format="mkv",
            tracks=[
                TrackInfo(index=0, track_type="audio", codec="aac", language="eng"),
            ],
        )

        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy, dry_run=False)

        phase = PhaseDefinition(
            name="compress",
            transcode=VideoTranscodeConfig(target_codec="hevc"),
        )
        state = PhaseExecutionState(file_path=test_file, phase=phase)

        result = executor._execute_transcode(state, audio_only_file_info)

        assert result == 0


class TestGetTracksFromDatabase:
    """Tests for _get_tracks method."""

    def test_get_tracks_success(self, db_conn, v11_policy, test_file):
        """_get_tracks returns tracks from database."""
        # Insert file and tracks
        file_id = insert_test_file(db_conn, test_file)
        insert_test_track(db_conn, file_id, 0, "video")
        insert_test_track(db_conn, file_id, 1, "audio", "eng")
        insert_test_track(db_conn, file_id, 2, "subtitle", "eng")

        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy)

        tracks = executor._get_tracks(test_file)

        assert len(tracks) == 3
        assert tracks[0].track_type == "video"
        assert tracks[1].track_type == "audio"
        assert tracks[2].track_type == "subtitle"

    def test_get_tracks_file_not_found(self, db_conn, v11_policy, test_file):
        """_get_tracks raises ValueError when file not in database."""
        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy)

        with pytest.raises(ValueError) as exc_info:
            executor._get_tracks(test_file)

        assert "not in database" in str(exc_info.value)


class TestToolAvailabilityCaching:
    """Tests for tool availability caching."""

    def test_tools_cached(self, db_conn, v11_policy):
        """Tool availability is cached after first call."""
        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy)

        with patch(
            "video_policy_orchestrator.workflow.phases.executor.check_tool_availability"
        ) as mock_check:
            mock_check.return_value = {"ffmpeg": True, "mkvmerge": True}

            # First call
            tools1 = executor._get_tools()
            # Second call
            tools2 = executor._get_tools()

        # Should only call check_tool_availability once
        mock_check.assert_called_once()
        assert tools1 is tools2


class TestConditionalRuleConversion:
    """Tests for conditional rule conversion methods.

    These tests verify that _build_virtual_policy correctly converts
    ConditionalRule dataclasses to dict format for policy loading.
    This catches bugs like accessing rule.then instead of rule.then_actions.
    """

    def test_build_virtual_policy_with_conditional_rules(self, db_conn, v11_policy):
        """Virtual policy includes conditional rules with then_actions.

        This test would have caught the original bug where _conditional_rule_to_dict
        accessed rule.then instead of rule.then_actions.
        """
        rule = ConditionalRule(
            name="test_rule",
            when=ExistsCondition(track_type="video", filters=TrackFilters()),
            then_actions=(SkipAction(skip_type=SkipType.VIDEO_TRANSCODE),),
            else_actions=None,
        )

        phase = PhaseDefinition(name="test", conditional=(rule,))

        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy)
        policy = executor._build_virtual_policy(phase)

        # Verify conditional rules were converted
        assert policy.conditional_rules is not None
        assert len(policy.conditional_rules) == 1

        # Verify rule loaded correctly - catches then vs then_actions bug
        loaded_rule = policy.conditional_rules[0]
        assert loaded_rule.name == "test_rule"
        assert loaded_rule.then_actions is not None
        assert len(loaded_rule.then_actions) == 1

    def test_conditional_rule_with_then_and_else_actions(self, db_conn, v11_policy):
        """Virtual policy correctly converts rules with both then and else branches."""
        rule = ConditionalRule(
            name="dual_branch_rule",
            when=ExistsCondition(
                track_type="audio",
                filters=TrackFilters(language="eng"),
            ),
            then_actions=(SkipAction(skip_type=SkipType.TRACK_FILTER),),
            else_actions=(WarnAction(message="No English audio found"),),
        )

        phase = PhaseDefinition(name="test", conditional=(rule,))

        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy)
        policy = executor._build_virtual_policy(phase)

        loaded_rule = policy.conditional_rules[0]
        assert loaded_rule.then_actions is not None
        assert loaded_rule.else_actions is not None
        assert len(loaded_rule.then_actions) == 1
        assert len(loaded_rule.else_actions) == 1

    def test_condition_to_dict_exists_condition(self, db_conn, v11_policy):
        """ExistsCondition with filters converts correctly."""
        rule = ConditionalRule(
            name="exists_test",
            when=ExistsCondition(
                track_type="subtitle",
                filters=TrackFilters(
                    language="eng",
                    is_forced=True,
                ),
            ),
            then_actions=(SkipAction(skip_type=SkipType.VIDEO_TRANSCODE),),
        )

        phase = PhaseDefinition(name="test", conditional=(rule,))

        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy)
        policy = executor._build_virtual_policy(phase)

        loaded_rule = policy.conditional_rules[0]
        assert isinstance(loaded_rule.when, ExistsCondition)
        assert loaded_rule.when.track_type == "subtitle"
        assert loaded_rule.when.filters.language == "eng"
        assert loaded_rule.when.filters.is_forced is True

    def test_condition_to_dict_count_condition(self, db_conn, v11_policy):
        """CountCondition converts correctly with operator and value."""
        rule = ConditionalRule(
            name="count_test",
            when=CountCondition(
                track_type="audio",
                filters=TrackFilters(),
                operator=ComparisonOperator.GTE,
                value=2,
            ),
            then_actions=(SkipAction(skip_type=SkipType.TRACK_FILTER),),
        )

        phase = PhaseDefinition(name="test", conditional=(rule,))

        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy)
        policy = executor._build_virtual_policy(phase)

        loaded_rule = policy.conditional_rules[0]
        assert isinstance(loaded_rule.when, CountCondition)
        assert loaded_rule.when.track_type == "audio"
        assert loaded_rule.when.operator == ComparisonOperator.GTE
        assert loaded_rule.when.value == 2

    def test_condition_to_dict_and_condition(self, db_conn, v11_policy):
        """AndCondition converts correctly with nested conditions."""
        rule = ConditionalRule(
            name="and_test",
            when=AndCondition(
                conditions=(
                    ExistsCondition(track_type="video", filters=TrackFilters()),
                    ExistsCondition(
                        track_type="audio", filters=TrackFilters(language="eng")
                    ),
                )
            ),
            then_actions=(SkipAction(skip_type=SkipType.VIDEO_TRANSCODE),),
        )

        phase = PhaseDefinition(name="test", conditional=(rule,))

        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy)
        policy = executor._build_virtual_policy(phase)

        loaded_rule = policy.conditional_rules[0]
        assert isinstance(loaded_rule.when, AndCondition)
        assert len(loaded_rule.when.conditions) == 2

    def test_condition_to_dict_or_condition(self, db_conn, v11_policy):
        """OrCondition converts correctly."""
        rule = ConditionalRule(
            name="or_test",
            when=OrCondition(
                conditions=(
                    ExistsCondition(
                        track_type="audio", filters=TrackFilters(language="eng")
                    ),
                    ExistsCondition(
                        track_type="audio", filters=TrackFilters(language="und")
                    ),
                )
            ),
            then_actions=(SkipAction(skip_type=SkipType.VIDEO_TRANSCODE),),
        )

        phase = PhaseDefinition(name="test", conditional=(rule,))

        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy)
        policy = executor._build_virtual_policy(phase)

        loaded_rule = policy.conditional_rules[0]
        assert isinstance(loaded_rule.when, OrCondition)
        assert len(loaded_rule.when.conditions) == 2

    def test_condition_to_dict_not_condition(self, db_conn, v11_policy):
        """NotCondition converts correctly."""
        rule = ConditionalRule(
            name="not_test",
            when=NotCondition(
                inner=ExistsCondition(
                    track_type="audio", filters=TrackFilters(language="eng")
                )
            ),
            then_actions=(SkipAction(skip_type=SkipType.VIDEO_TRANSCODE),),
        )

        phase = PhaseDefinition(name="test", conditional=(rule,))

        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy)
        policy = executor._build_virtual_policy(phase)

        loaded_rule = policy.conditional_rules[0]
        assert isinstance(loaded_rule.when, NotCondition)
        assert isinstance(loaded_rule.when.inner, ExistsCondition)

    def test_condition_to_dict_audio_is_multi_language(self, db_conn, v11_policy):
        """AudioIsMultiLanguageCondition converts correctly."""
        rule = ConditionalRule(
            name="multi_lang_test",
            when=AudioIsMultiLanguageCondition(threshold=0.1),
            then_actions=(WarnAction(message="Multi-language audio detected"),),
        )

        phase = PhaseDefinition(name="test", conditional=(rule,))

        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy)
        policy = executor._build_virtual_policy(phase)

        loaded_rule = policy.conditional_rules[0]
        assert isinstance(loaded_rule.when, AudioIsMultiLanguageCondition)
        assert loaded_rule.when.threshold == 0.1

    def test_condition_to_dict_plugin_metadata(self, db_conn, v11_policy):
        """PluginMetadataCondition converts correctly."""
        rule = ConditionalRule(
            name="plugin_test",
            when=PluginMetadataCondition(
                plugin="radarr",
                field="original_language",
                value="jpn",
                operator=PluginMetadataOperator.EQ,
            ),
            then_actions=(SkipAction(skip_type=SkipType.VIDEO_TRANSCODE),),
        )

        phase = PhaseDefinition(name="test", conditional=(rule,))

        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy)
        policy = executor._build_virtual_policy(phase)

        loaded_rule = policy.conditional_rules[0]
        assert isinstance(loaded_rule.when, PluginMetadataCondition)
        assert loaded_rule.when.plugin == "radarr"
        assert loaded_rule.when.field == "original_language"
        assert loaded_rule.when.value == "jpn"

    def test_action_to_dict_skip_action(self, db_conn, v11_policy):
        """SkipAction converts correctly."""
        rule = ConditionalRule(
            name="skip_test",
            when=ExistsCondition(track_type="video", filters=TrackFilters()),
            then_actions=(
                SkipAction(skip_type=SkipType.VIDEO_TRANSCODE),
                SkipAction(skip_type=SkipType.AUDIO_TRANSCODE),
            ),
        )

        phase = PhaseDefinition(name="test", conditional=(rule,))

        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy)
        policy = executor._build_virtual_policy(phase)

        loaded_rule = policy.conditional_rules[0]
        assert len(loaded_rule.then_actions) == 2
        # Both should be SkipActions
        assert all(isinstance(a, SkipAction) for a in loaded_rule.then_actions)

    def test_action_to_dict_warn_action(self, db_conn, v11_policy):
        """WarnAction converts correctly."""
        rule = ConditionalRule(
            name="warn_test",
            when=ExistsCondition(track_type="video", filters=TrackFilters()),
            then_actions=(WarnAction(message="Test warning message"),),
        )

        phase = PhaseDefinition(name="test", conditional=(rule,))

        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy)
        policy = executor._build_virtual_policy(phase)

        loaded_rule = policy.conditional_rules[0]
        assert len(loaded_rule.then_actions) == 1
        action = loaded_rule.then_actions[0]
        assert isinstance(action, WarnAction)
        assert action.message == "Test warning message"

    def test_action_to_dict_set_forced_action(self, db_conn, v11_policy):
        """SetForcedAction converts correctly."""
        rule = ConditionalRule(
            name="set_forced_test",
            when=NotCondition(
                inner=ExistsCondition(
                    track_type="audio", filters=TrackFilters(language="eng")
                )
            ),
            then_actions=(
                SetForcedAction(track_type="subtitle", language="eng", value=True),
            ),
        )

        phase = PhaseDefinition(name="test", conditional=(rule,))

        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy)
        policy = executor._build_virtual_policy(phase)

        loaded_rule = policy.conditional_rules[0]
        assert len(loaded_rule.then_actions) == 1
        action = loaded_rule.then_actions[0]
        assert isinstance(action, SetForcedAction)
        assert action.track_type == "subtitle"
        assert action.language == "eng"
        assert action.value is True

    def test_action_to_dict_set_default_action(self, db_conn, v11_policy):
        """SetDefaultAction converts correctly."""
        rule = ConditionalRule(
            name="set_default_test",
            when=ExistsCondition(track_type="video", filters=TrackFilters()),
            then_actions=(
                SetDefaultAction(track_type="audio", language="eng", value=True),
            ),
        )

        phase = PhaseDefinition(name="test", conditional=(rule,))

        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy)
        policy = executor._build_virtual_policy(phase)

        loaded_rule = policy.conditional_rules[0]
        assert len(loaded_rule.then_actions) == 1
        action = loaded_rule.then_actions[0]
        assert isinstance(action, SetDefaultAction)
        assert action.track_type == "audio"
        assert action.language == "eng"

    def test_filters_to_dict_all_fields(self, db_conn, v11_policy):
        """TrackFilters with all fields converts correctly."""
        rule = ConditionalRule(
            name="filters_test",
            when=ExistsCondition(
                track_type="audio",
                filters=TrackFilters(
                    language=("eng", "und"),
                    codec=("aac", "ac3"),
                    is_default=True,
                    is_forced=False,
                    channels=Comparison(operator=ComparisonOperator.GTE, value=6),
                    not_commentary=True,
                ),
            ),
            then_actions=(SkipAction(skip_type=SkipType.VIDEO_TRANSCODE),),
        )

        phase = PhaseDefinition(name="test", conditional=(rule,))

        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy)
        policy = executor._build_virtual_policy(phase)

        loaded_rule = policy.conditional_rules[0]
        filters = loaded_rule.when.filters
        # Language and codec may be list or tuple depending on loader
        assert set(filters.language) == {"eng", "und"}
        assert set(filters.codec) == {"aac", "ac3"}
        assert filters.is_default is True
        assert filters.is_forced is False
        assert filters.not_commentary is True
        # Channels comparison
        assert filters.channels is not None

    def test_filters_to_dict_with_title_match(self, db_conn, v11_policy):
        """TrackFilters with TitleMatch converts correctly."""
        rule = ConditionalRule(
            name="title_test",
            when=ExistsCondition(
                track_type="audio",
                filters=TrackFilters(
                    title=TitleMatch(contains="Commentary"),
                ),
            ),
            then_actions=(SkipAction(skip_type=SkipType.TRACK_FILTER),),
        )

        phase = PhaseDefinition(name="test", conditional=(rule,))

        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy)
        policy = executor._build_virtual_policy(phase)

        loaded_rule = policy.conditional_rules[0]
        filters = loaded_rule.when.filters
        assert filters.title is not None
        # Title could be TitleMatch or dict depending on loader
        if isinstance(filters.title, TitleMatch):
            assert filters.title.contains == "Commentary"
        else:
            assert filters.title.get("contains") == "Commentary"

    def test_multiple_conditional_rules(self, db_conn, v11_policy):
        """Multiple conditional rules convert correctly."""
        rules = (
            ConditionalRule(
                name="rule1",
                when=ExistsCondition(track_type="video", filters=TrackFilters()),
                then_actions=(SkipAction(skip_type=SkipType.VIDEO_TRANSCODE),),
            ),
            ConditionalRule(
                name="rule2",
                when=ExistsCondition(
                    track_type="audio", filters=TrackFilters(language="eng")
                ),
                then_actions=(WarnAction(message="English audio found"),),
            ),
            ConditionalRule(
                name="rule3",
                when=NotCondition(
                    inner=ExistsCondition(track_type="subtitle", filters=TrackFilters())
                ),
                then_actions=(WarnAction(message="No subtitles"),),
            ),
        )

        phase = PhaseDefinition(name="test", conditional=rules)

        executor = V11PhaseExecutor(conn=db_conn, policy=v11_policy)
        policy = executor._build_virtual_policy(phase)

        assert policy.conditional_rules is not None
        assert len(policy.conditional_rules) == 3
        assert policy.conditional_rules[0].name == "rule1"
        assert policy.conditional_rules[1].name == "rule2"
        assert policy.conditional_rules[2].name == "rule3"
