"""Unit tests for TranscriptionCoordinator.

Tests the coordinator layer that uses PluginRegistry instead of
TranscriptionRegistry for dispatching transcription requests.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from video_policy_orchestrator.db.schema import create_schema
from video_policy_orchestrator.db.types import TrackClassification, TrackInfo
from video_policy_orchestrator.plugin.events import TranscriptionRequestedEvent
from video_policy_orchestrator.plugin.registry import LoadedPlugin, PluginManifest
from video_policy_orchestrator.transcription.coordinator import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    NoTranscriptionPluginError,
    PluginTranscriberAdapter,
    TranscriptionCoordinator,
    TranscriptionCoordinatorResult,
    TranscriptionOptions,
)
from video_policy_orchestrator.transcription.interface import TranscriptionError
from video_policy_orchestrator.transcription.models import (
    TrackClassification as ModelTrackClassification,
)
from video_policy_orchestrator.transcription.models import (
    TranscriptionResult,
)
from video_policy_orchestrator.transcription.multi_sample import AggregatedResult


@pytest.fixture
def db_conn():
    """Create in-memory database with schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    return conn


@pytest.fixture
def mock_registry():
    """Create a mock PluginRegistry."""
    registry = MagicMock()
    registry.get_by_event = MagicMock(return_value=[])
    return registry


@pytest.fixture
def test_file(tmp_path):
    """Create a temporary test file."""
    f = tmp_path / "test.mkv"
    f.write_bytes(b"\x00" * 100)
    return f


@pytest.fixture
def test_track():
    """Create a test TrackInfo."""
    return TrackInfo(
        id=1,
        index=1,
        track_type="audio",
        language="eng",
        duration_seconds=120.0,
    )


@pytest.fixture
def mock_transcription_result():
    """Create a mock TranscriptionResult."""
    now = datetime.now(timezone.utc)
    return TranscriptionResult(
        track_id=1,
        detected_language="eng",
        confidence_score=0.95,
        track_type=ModelTrackClassification.MAIN,
        transcript_sample="Hello world",
        plugin_name="test-plugin",
        created_at=now,
        updated_at=now,
    )


def create_mock_plugin(
    name: str = "test-plugin",
    events: list[str] | None = None,
    transcription_result: TranscriptionResult | None = None,
) -> LoadedPlugin:
    """Create a mock LoadedPlugin for testing."""
    if events is None:
        events = ["transcription.requested"]

    manifest = MagicMock(spec=PluginManifest)
    manifest.name = name
    manifest.version = "1.0.0"
    manifest.events = events

    instance = MagicMock()
    instance.name = name
    instance.version = "1.0.0"
    instance.events = events

    if transcription_result is not None:
        instance.on_transcription_requested = MagicMock(
            return_value=transcription_result
        )
    else:
        instance.on_transcription_requested = MagicMock(return_value=None)

    loaded = MagicMock(spec=LoadedPlugin)
    loaded.manifest = manifest
    loaded.instance = instance
    loaded.enabled = True
    loaded.name = name
    loaded.events = events

    return loaded


def insert_test_file(conn: sqlite3.Connection, file_path: Path) -> int:
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
    conn: sqlite3.Connection,
    file_id: int,
    index: int,
    track_type: str,
    language: str = "eng",
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


class TestTranscriptionOptions:
    """Tests for TranscriptionOptions dataclass."""

    def test_default_values(self):
        """TranscriptionOptions has sensible defaults."""
        options = TranscriptionOptions()

        assert options.confidence_threshold == DEFAULT_CONFIDENCE_THRESHOLD
        assert options.max_samples == 3
        assert options.sample_duration == 30
        assert options.incumbent_bonus == 0.15

    def test_custom_values(self):
        """TranscriptionOptions accepts custom values."""
        options = TranscriptionOptions(
            confidence_threshold=0.9,
            max_samples=5,
            sample_duration=60,
            incumbent_bonus=0.2,
        )

        assert options.confidence_threshold == 0.9
        assert options.max_samples == 5
        assert options.sample_duration == 60
        assert options.incumbent_bonus == 0.2


class TestTranscriptionCoordinatorResult:
    """Tests for TranscriptionCoordinatorResult dataclass."""

    def test_all_fields(self):
        """TranscriptionCoordinatorResult has all required fields."""
        result = TranscriptionCoordinatorResult(
            track_index=1,
            detected_language="fra",
            confidence=0.88,
            transcript_sample="Bonjour",
            track_type=TrackClassification.MAIN,
            plugin_name="whisper-local",
        )

        assert result.track_index == 1
        assert result.detected_language == "fra"
        assert result.confidence == 0.88
        assert result.transcript_sample == "Bonjour"
        assert result.track_type == TrackClassification.MAIN
        assert result.plugin_name == "whisper-local"


class TestTranscriptionCoordinatorInit:
    """Tests for TranscriptionCoordinator initialization."""

    def test_init_with_registry(self, mock_registry):
        """Coordinator initializes with PluginRegistry."""
        coordinator = TranscriptionCoordinator(mock_registry)

        assert coordinator._registry is mock_registry


class TestTranscriptionCoordinatorGetTranscriptionPlugins:
    """Tests for get_transcription_plugins method."""

    def test_returns_empty_list_when_no_plugins(self, mock_registry):
        """get_transcription_plugins returns empty list when no plugins."""
        mock_registry.get_by_event.return_value = []
        coordinator = TranscriptionCoordinator(mock_registry)

        plugins = coordinator.get_transcription_plugins()

        assert plugins == []
        mock_registry.get_by_event.assert_called_once_with("transcription.requested")

    def test_returns_plugins_for_event(self, mock_registry, mock_transcription_result):
        """get_transcription_plugins returns plugins subscribed to event."""
        plugin = create_mock_plugin(
            "whisper-local", transcription_result=mock_transcription_result
        )
        mock_registry.get_by_event.return_value = [plugin]
        coordinator = TranscriptionCoordinator(mock_registry)

        plugins = coordinator.get_transcription_plugins()

        assert len(plugins) == 1
        assert plugins[0].name == "whisper-local"

    def test_queries_correct_event(self, mock_registry):
        """get_transcription_plugins queries transcription.requested event."""
        coordinator = TranscriptionCoordinator(mock_registry)

        coordinator.get_transcription_plugins()

        mock_registry.get_by_event.assert_called_with("transcription.requested")


class TestTranscriptionCoordinatorIsAvailable:
    """Tests for is_available method."""

    def test_returns_false_when_no_plugins(self, mock_registry):
        """is_available returns False when no plugins available."""
        mock_registry.get_by_event.return_value = []
        coordinator = TranscriptionCoordinator(mock_registry)

        assert coordinator.is_available() is False

    def test_returns_true_when_plugins_exist(
        self, mock_registry, mock_transcription_result
    ):
        """is_available returns True when plugins exist."""
        plugin = create_mock_plugin(transcription_result=mock_transcription_result)
        mock_registry.get_by_event.return_value = [plugin]
        coordinator = TranscriptionCoordinator(mock_registry)

        assert coordinator.is_available() is True


class TestTranscriptionCoordinatorGetDefaultPlugin:
    """Tests for get_default_plugin method."""

    def test_returns_none_when_no_plugins(self, mock_registry):
        """get_default_plugin returns None when no plugins."""
        mock_registry.get_by_event.return_value = []
        coordinator = TranscriptionCoordinator(mock_registry)

        assert coordinator.get_default_plugin() is None

    def test_returns_first_plugin(self, mock_registry, mock_transcription_result):
        """get_default_plugin returns first available plugin."""
        plugin1 = create_mock_plugin(
            "plugin1", transcription_result=mock_transcription_result
        )
        plugin2 = create_mock_plugin(
            "plugin2", transcription_result=mock_transcription_result
        )
        mock_registry.get_by_event.return_value = [plugin1, plugin2]
        coordinator = TranscriptionCoordinator(mock_registry)

        result = coordinator.get_default_plugin()

        assert result is plugin1


class TestTranscriptionCoordinatorAnalyzeTrack:
    """Tests for analyze_track method."""

    def test_raises_when_no_plugins(self, mock_registry, test_file, test_track):
        """analyze_track raises NoTranscriptionPluginError when no plugins."""
        mock_registry.get_by_event.return_value = []
        coordinator = TranscriptionCoordinator(mock_registry)

        with pytest.raises(NoTranscriptionPluginError):
            coordinator.analyze_track(
                file_path=test_file,
                track=test_track,
                track_duration=120.0,
            )

    def test_calls_smart_detect_with_adapter(
        self, mock_registry, test_file, test_track, mock_transcription_result
    ):
        """analyze_track calls smart_detect with PluginTranscriberAdapter."""
        plugin = create_mock_plugin(transcription_result=mock_transcription_result)
        mock_registry.get_by_event.return_value = [plugin]
        coordinator = TranscriptionCoordinator(mock_registry)

        with patch(
            "video_policy_orchestrator.transcription.coordinator.smart_detect"
        ) as mock_detect:
            mock_detect.return_value = AggregatedResult(
                language="eng",
                confidence=0.95,
                samples_taken=1,
                transcript_sample="Hello world",
            )

            coordinator.analyze_track(
                file_path=test_file,
                track=test_track,
                track_duration=120.0,
            )

        mock_detect.assert_called_once()
        call_kwargs = mock_detect.call_args.kwargs

        # Verify adapter was passed as transcriber
        assert isinstance(call_kwargs["transcriber"], PluginTranscriberAdapter)
        assert call_kwargs["file_path"] == test_file
        assert call_kwargs["track_index"] == 1
        assert call_kwargs["track_duration"] == 120.0
        assert call_kwargs["incumbent_language"] == "eng"

    def test_returns_coordinator_result(
        self, mock_registry, test_file, test_track, mock_transcription_result
    ):
        """analyze_track returns TranscriptionCoordinatorResult."""
        plugin = create_mock_plugin(transcription_result=mock_transcription_result)
        mock_registry.get_by_event.return_value = [plugin]
        coordinator = TranscriptionCoordinator(mock_registry)

        with patch(
            "video_policy_orchestrator.transcription.coordinator.smart_detect"
        ) as mock_detect:
            mock_detect.return_value = AggregatedResult(
                language="fra",
                confidence=0.88,
                samples_taken=2,
                transcript_sample="Bonjour le monde",
            )

            result = coordinator.analyze_track(
                file_path=test_file,
                track=test_track,
                track_duration=120.0,
            )

        assert isinstance(result, TranscriptionCoordinatorResult)
        assert result.track_index == 1
        assert result.detected_language == "fra"
        assert result.confidence == 0.88
        assert result.transcript_sample == "Bonjour le monde"

    def test_uses_custom_options(
        self, mock_registry, test_file, test_track, mock_transcription_result
    ):
        """analyze_track uses custom TranscriptionOptions."""
        plugin = create_mock_plugin(transcription_result=mock_transcription_result)
        mock_registry.get_by_event.return_value = [plugin]
        coordinator = TranscriptionCoordinator(mock_registry)

        options = TranscriptionOptions(
            confidence_threshold=0.9,
            max_samples=5,
            sample_duration=60,
            incumbent_bonus=0.3,
        )

        with patch(
            "video_policy_orchestrator.transcription.coordinator.smart_detect"
        ) as mock_detect:
            mock_detect.return_value = AggregatedResult(
                language="eng",
                confidence=0.95,
                samples_taken=1,
            )

            coordinator.analyze_track(
                file_path=test_file,
                track=test_track,
                track_duration=120.0,
                options=options,
            )

        call_kwargs = mock_detect.call_args.kwargs
        config = call_kwargs["config"]
        assert config.confidence_threshold == 0.9
        assert config.max_samples == 5
        assert config.sample_duration == 60
        assert config.incumbent_bonus == 0.3


class TestTranscriptionCoordinatorAnalyzeAndPersist:
    """Tests for analyze_and_persist method."""

    def test_persists_result_to_database(
        self, db_conn, mock_registry, test_file, mock_transcription_result
    ):
        """analyze_and_persist saves transcription result to database."""
        # Setup: Insert file and track
        file_id = insert_test_file(db_conn, test_file)
        track_id = insert_test_track(db_conn, file_id, 1, "audio", "eng")

        plugin = create_mock_plugin(
            "whisper-local", transcription_result=mock_transcription_result
        )
        mock_registry.get_by_event.return_value = [plugin]
        coordinator = TranscriptionCoordinator(mock_registry)

        track = TrackInfo(
            id=track_id,
            index=1,
            track_type="audio",
            language="eng",
        )

        with patch(
            "video_policy_orchestrator.transcription.coordinator.smart_detect"
        ) as mock_detect:
            mock_detect.return_value = AggregatedResult(
                language="fra",
                confidence=0.88,
                samples_taken=2,
                transcript_sample="Bonjour",
            )

            result = coordinator.analyze_and_persist(
                file_path=test_file,
                track=track,
                track_duration=120.0,
                conn=db_conn,
            )

        # Verify result
        assert result.detected_language == "fra"
        assert result.confidence == 0.88

        # Verify database persistence
        cursor = db_conn.execute(
            "SELECT * FROM transcription_results WHERE track_id = ?",
            (track_id,),
        )
        row = cursor.fetchone()

        assert row is not None
        assert row["detected_language"] == "fra"
        assert row["confidence_score"] == 0.88
        assert row["transcript_sample"] == "Bonjour"

    def test_raises_for_track_without_id(
        self, db_conn, mock_registry, test_file, mock_transcription_result
    ):
        """analyze_and_persist raises ValueError if track has no ID."""
        plugin = create_mock_plugin(transcription_result=mock_transcription_result)
        mock_registry.get_by_event.return_value = [plugin]
        coordinator = TranscriptionCoordinator(mock_registry)

        track = TrackInfo(
            index=1,
            track_type="audio",
            # No id!
        )

        with pytest.raises(ValueError, match="Track 1 has no database ID"):
            coordinator.analyze_and_persist(
                file_path=test_file,
                track=track,
                track_duration=120.0,
                conn=db_conn,
            )

    def test_stores_plugin_name(
        self, db_conn, mock_registry, test_file, mock_transcription_result
    ):
        """analyze_and_persist stores plugin name in database."""
        file_id = insert_test_file(db_conn, test_file)
        track_id = insert_test_track(db_conn, file_id, 1, "audio", "eng")

        plugin = create_mock_plugin(
            "whisper-local", transcription_result=mock_transcription_result
        )
        mock_registry.get_by_event.return_value = [plugin]
        coordinator = TranscriptionCoordinator(mock_registry)

        track = TrackInfo(
            id=track_id,
            index=1,
            track_type="audio",
        )

        with patch(
            "video_policy_orchestrator.transcription.coordinator.smart_detect"
        ) as mock_detect:
            mock_detect.return_value = AggregatedResult(
                language="eng",
                confidence=0.9,
                samples_taken=1,
            )

            # Mock adapter to return the plugin name
            with patch.object(
                PluginTranscriberAdapter,
                "last_plugin_name",
                new_callable=lambda: property(lambda self: "whisper-local"),
            ):
                coordinator.analyze_and_persist(
                    file_path=test_file,
                    track=track,
                    track_duration=120.0,
                    conn=db_conn,
                )

        # Verify plugin_name was stored
        cursor = db_conn.execute(
            "SELECT plugin_name FROM transcription_results WHERE track_id = ?",
            (track_id,),
        )
        row = cursor.fetchone()
        assert row["plugin_name"] == "whisper-local"


class TestPluginTranscriberAdapter:
    """Tests for PluginTranscriberAdapter class."""

    def test_implements_transcription_plugin_interface(
        self, mock_registry, test_file, test_track
    ):
        """Adapter implements TranscriptionPlugin protocol methods."""
        adapter = PluginTranscriberAdapter(
            registry=mock_registry,
            file_path=test_file,
            track=test_track,
        )

        # Check protocol methods exist
        assert hasattr(adapter, "name")
        assert hasattr(adapter, "version")
        assert hasattr(adapter, "transcribe")
        assert hasattr(adapter, "detect_language")
        assert hasattr(adapter, "supports_feature")
        assert hasattr(adapter, "detect_multi_language")

    def test_transcribe_dispatches_event(
        self, mock_registry, test_file, test_track, mock_transcription_result
    ):
        """transcribe dispatches TranscriptionRequestedEvent to plugins."""
        plugin = create_mock_plugin(transcription_result=mock_transcription_result)
        mock_registry.get_by_event.return_value = [plugin]

        adapter = PluginTranscriberAdapter(
            registry=mock_registry,
            file_path=test_file,
            track=test_track,
        )

        adapter.transcribe(b"audio data", sample_rate=16000)

        # Verify event was dispatched
        plugin.instance.on_transcription_requested.assert_called_once()
        call_args = plugin.instance.on_transcription_requested.call_args[0]
        event = call_args[0]

        assert isinstance(event, TranscriptionRequestedEvent)
        assert event.file_path == test_file
        assert event.track == test_track
        assert event.audio_data == b"audio data"
        assert event.sample_rate == 16000

    def test_transcribe_returns_first_non_none_result(
        self, mock_registry, test_file, test_track, mock_transcription_result
    ):
        """transcribe returns first non-None result from plugins."""
        # First plugin returns None
        plugin1 = create_mock_plugin("plugin1")
        plugin1.instance.on_transcription_requested.return_value = None

        # Second plugin returns result
        plugin2 = create_mock_plugin(
            "plugin2", transcription_result=mock_transcription_result
        )

        mock_registry.get_by_event.return_value = [plugin1, plugin2]

        adapter = PluginTranscriberAdapter(
            registry=mock_registry,
            file_path=test_file,
            track=test_track,
        )

        result = adapter.transcribe(b"audio data")

        assert result == mock_transcription_result
        assert adapter.last_plugin_name == "plugin2"

    def test_transcribe_raises_when_no_plugins(
        self, mock_registry, test_file, test_track
    ):
        """transcribe raises TranscriptionError when no plugins available."""
        mock_registry.get_by_event.return_value = []

        adapter = PluginTranscriberAdapter(
            registry=mock_registry,
            file_path=test_file,
            track=test_track,
        )

        with pytest.raises(TranscriptionError, match="No transcription plugins"):
            adapter.transcribe(b"audio data")

    def test_transcribe_raises_when_all_plugins_fail(
        self, mock_registry, test_file, test_track
    ):
        """transcribe raises TranscriptionError when all plugins fail."""
        plugin = create_mock_plugin("failing-plugin")
        plugin.instance.on_transcription_requested.side_effect = Exception(
            "Plugin error"
        )
        mock_registry.get_by_event.return_value = [plugin]

        adapter = PluginTranscriberAdapter(
            registry=mock_registry,
            file_path=test_file,
            track=test_track,
        )

        with pytest.raises(
            TranscriptionError, match="All transcription plugins failed"
        ):
            adapter.transcribe(b"audio data")

    def test_transcribe_includes_language_in_options(
        self, mock_registry, test_file, test_track, mock_transcription_result
    ):
        """transcribe includes language hint in event options."""
        plugin = create_mock_plugin(transcription_result=mock_transcription_result)
        mock_registry.get_by_event.return_value = [plugin]

        adapter = PluginTranscriberAdapter(
            registry=mock_registry,
            file_path=test_file,
            track=test_track,
        )

        adapter.transcribe(b"audio data", language="fra")

        event = plugin.instance.on_transcription_requested.call_args[0][0]
        assert event.options.get("language") == "fra"

    def test_detect_language_dispatches_event(
        self, mock_registry, test_file, test_track, mock_transcription_result
    ):
        """detect_language dispatches event with detect_only option."""
        plugin = create_mock_plugin(transcription_result=mock_transcription_result)
        mock_registry.get_by_event.return_value = [plugin]

        adapter = PluginTranscriberAdapter(
            registry=mock_registry,
            file_path=test_file,
            track=test_track,
        )

        adapter.detect_language(b"audio data")

        event = plugin.instance.on_transcription_requested.call_args[0][0]
        assert event.options.get("detect_only") is True

    def test_supports_feature_checks_all_plugins(
        self, mock_registry, test_file, test_track
    ):
        """supports_feature returns True if any plugin supports feature."""
        plugin1 = create_mock_plugin("plugin1")
        plugin1.instance.supports_feature = MagicMock(return_value=False)

        plugin2 = create_mock_plugin("plugin2")
        plugin2.instance.supports_feature = MagicMock(return_value=True)

        mock_registry.get_by_event.return_value = [plugin1, plugin2]

        adapter = PluginTranscriberAdapter(
            registry=mock_registry,
            file_path=test_file,
            track=test_track,
        )

        assert adapter.supports_feature("gpu") is True

    def test_supports_feature_returns_false_when_none_support(
        self, mock_registry, test_file, test_track
    ):
        """supports_feature returns False when no plugins support feature."""
        plugin = create_mock_plugin("plugin1")
        plugin.instance.supports_feature = MagicMock(return_value=False)
        mock_registry.get_by_event.return_value = [plugin]

        adapter = PluginTranscriberAdapter(
            registry=mock_registry,
            file_path=test_file,
            track=test_track,
        )

        assert adapter.supports_feature("nonexistent") is False

    def test_detect_multi_language_returns_result(
        self, mock_registry, test_file, test_track, mock_transcription_result
    ):
        """detect_multi_language converts transcribe result."""
        plugin = create_mock_plugin(transcription_result=mock_transcription_result)
        mock_registry.get_by_event.return_value = [plugin]

        adapter = PluginTranscriberAdapter(
            registry=mock_registry,
            file_path=test_file,
            track=test_track,
        )

        result = adapter.detect_multi_language(b"audio data")

        assert result.language == "eng"
        assert result.confidence == 0.95
        assert result.has_speech is True

    def test_detect_multi_language_handles_error(
        self, mock_registry, test_file, test_track
    ):
        """detect_multi_language returns error result on failure."""
        plugin = create_mock_plugin("failing-plugin")
        plugin.instance.on_transcription_requested.side_effect = Exception("Error")
        mock_registry.get_by_event.return_value = [plugin]

        adapter = PluginTranscriberAdapter(
            registry=mock_registry,
            file_path=test_file,
            track=test_track,
        )

        result = adapter.detect_multi_language(b"audio data")

        assert result.language is None
        assert result.confidence == 0.0
        assert result.has_speech is False
        assert len(result.errors) > 0


class TestTranscriptionCoordinatorClassification:
    """Tests for track classification via _classify_track."""

    def test_classifies_commentary_by_title(
        self, mock_registry, test_file, mock_transcription_result
    ):
        """Classifies track as COMMENTARY based on title metadata."""
        plugin = create_mock_plugin(transcription_result=mock_transcription_result)
        mock_registry.get_by_event.return_value = [plugin]
        coordinator = TranscriptionCoordinator(mock_registry)

        track = TrackInfo(
            id=1,
            index=1,
            track_type="audio",
            title="Director's Commentary",
        )

        with patch(
            "video_policy_orchestrator.transcription.coordinator.smart_detect"
        ) as mock_detect:
            mock_detect.return_value = AggregatedResult(
                language="eng",
                confidence=0.9,
                samples_taken=1,
                transcript_sample="In this scene, we wanted to...",
            )

            result = coordinator.analyze_track(
                file_path=test_file,
                track=track,
                track_duration=120.0,
            )

        assert result.track_type == TrackClassification.COMMENTARY

    def test_classifies_music_by_title(
        self, mock_registry, test_file, mock_transcription_result
    ):
        """Classifies track as MUSIC based on title metadata."""
        plugin = create_mock_plugin(transcription_result=mock_transcription_result)
        mock_registry.get_by_event.return_value = [plugin]
        coordinator = TranscriptionCoordinator(mock_registry)

        track = TrackInfo(
            id=1,
            index=1,
            track_type="audio",
            title="Isolated Score",
        )

        with patch(
            "video_policy_orchestrator.transcription.coordinator.smart_detect"
        ) as mock_detect:
            mock_detect.return_value = AggregatedResult(
                language=None,
                confidence=0.3,
                samples_taken=1,
            )

            result = coordinator.analyze_track(
                file_path=test_file,
                track=track,
                track_duration=120.0,
            )

        assert result.track_type == TrackClassification.MUSIC

    def test_classifies_main_for_normal_track(
        self, mock_registry, test_file, mock_transcription_result
    ):
        """Classifies track as MAIN for normal audio with speech."""
        plugin = create_mock_plugin(transcription_result=mock_transcription_result)
        mock_registry.get_by_event.return_value = [plugin]
        coordinator = TranscriptionCoordinator(mock_registry)

        track = TrackInfo(
            id=1,
            index=1,
            track_type="audio",
            language="eng",
        )

        with patch(
            "video_policy_orchestrator.transcription.coordinator.smart_detect"
        ) as mock_detect:
            mock_detect.return_value = AggregatedResult(
                language="eng",
                confidence=0.95,
                samples_taken=1,
                transcript_sample="The quick brown fox jumps over the lazy dog.",
            )

            result = coordinator.analyze_track(
                file_path=test_file,
                track=track,
                track_duration=120.0,
            )

        assert result.track_type == TrackClassification.MAIN
