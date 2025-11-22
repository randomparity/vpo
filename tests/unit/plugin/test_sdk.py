"""Unit tests for Plugin SDK."""

from pathlib import Path

from video_policy_orchestrator.db.models import FileInfo, TrackInfo
from video_policy_orchestrator.executor.interface import ExecutorResult
from video_policy_orchestrator.plugin.events import (
    FileScannedEvent,
    PlanExecuteEvent,
    PolicyEvaluateEvent,
)
from video_policy_orchestrator.plugin.interfaces import AnalyzerPlugin, MutatorPlugin
from video_policy_orchestrator.plugin_sdk import (
    BaseAnalyzerPlugin,
    BaseDualPlugin,
    BaseMutatorPlugin,
    PluginTestCase,
    create_file_scanned_event,
    create_plan_execute_event,
    create_policy_evaluate_event,
    get_logger,
    is_mkv_container,
    is_supported_container,
    mock_executor_result,
    mock_file_info,
    mock_plan,
    mock_track_info,
    mock_tracks,
    normalize_path,
)
from video_policy_orchestrator.policy.models import Plan


class TestBaseAnalyzerPlugin:
    """Tests for BaseAnalyzerPlugin."""

    def test_subclass_implements_protocol(self):
        """Subclass of BaseAnalyzerPlugin implements AnalyzerPlugin protocol."""

        class MyPlugin(BaseAnalyzerPlugin):
            name = "test-plugin"
            version = "1.0.0"
            events = ["file.scanned"]

        plugin = MyPlugin()
        assert isinstance(plugin, AnalyzerPlugin)

    def test_default_methods_return_expected(self):
        """Default method implementations return expected values."""

        class MyPlugin(BaseAnalyzerPlugin):
            name = "test-plugin"
            version = "1.0.0"
            events = ["file.scanned"]

        plugin = MyPlugin()

        # on_file_scanned returns None by default
        assert plugin.on_file_scanned(None) is None

        # on_policy_evaluate doesn't raise
        plugin.on_policy_evaluate(None)

        # on_plan_complete doesn't raise
        plugin.on_plan_complete(None)

    def test_logger_available(self):
        """Plugin has a logger available."""

        class MyPlugin(BaseAnalyzerPlugin):
            name = "test-plugin"
            version = "1.0.0"
            events = []

        plugin = MyPlugin()
        assert plugin.logger is not None
        assert "test-plugin" in plugin.logger.name

    def test_optional_attributes_have_defaults(self):
        """Optional attributes have sensible defaults."""

        class MyPlugin(BaseAnalyzerPlugin):
            name = "test-plugin"
            version = "1.0.0"
            events = []

        plugin = MyPlugin()
        assert plugin.description == ""
        assert plugin.author == ""
        assert plugin.min_api_version == "1.0.0"
        assert plugin.max_api_version == "1.99.99"


class TestBaseMutatorPlugin:
    """Tests for BaseMutatorPlugin."""

    def test_subclass_implements_protocol(self):
        """Subclass of BaseMutatorPlugin implements MutatorPlugin protocol."""

        class MyPlugin(BaseMutatorPlugin):
            name = "test-plugin"
            version = "1.0.0"
            events = ["plan.before_execute"]

        plugin = MyPlugin()
        assert isinstance(plugin, MutatorPlugin)

    def test_default_execute_returns_failure(self):
        """Default execute returns failure (not implemented)."""

        class MyPlugin(BaseMutatorPlugin):
            name = "test-plugin"
            version = "1.0.0"
            events = []

        plugin = MyPlugin()
        result = plugin.execute(None)
        assert result.success is False
        assert "not implemented" in result.message.lower()

    def test_default_rollback_returns_failure(self):
        """Default rollback returns failure (not supported)."""

        class MyPlugin(BaseMutatorPlugin):
            name = "test-plugin"
            version = "1.0.0"
            events = []

        plugin = MyPlugin()
        result = plugin.rollback(None)
        assert result.success is False
        assert "not supported" in result.message.lower()

    def test_supports_rollback_default_false(self):
        """supports_rollback defaults to False."""

        class MyPlugin(BaseMutatorPlugin):
            name = "test-plugin"
            version = "1.0.0"
            events = []

        plugin = MyPlugin()
        assert plugin.supports_rollback is False


class TestBaseDualPlugin:
    """Tests for BaseDualPlugin."""

    def test_implements_both_protocols(self):
        """BaseDualPlugin implements both protocols."""

        class MyPlugin(BaseDualPlugin):
            name = "test-plugin"
            version = "1.0.0"
            events = []

        plugin = MyPlugin()
        assert isinstance(plugin, AnalyzerPlugin)
        assert isinstance(plugin, MutatorPlugin)

    def test_has_methods_from_both_bases(self):
        """Has methods from both BaseAnalyzerPlugin and BaseMutatorPlugin."""

        class MyPlugin(BaseDualPlugin):
            name = "test-plugin"
            version = "1.0.0"
            events = []

        plugin = MyPlugin()

        # From AnalyzerPlugin
        assert hasattr(plugin, "on_file_scanned")
        assert hasattr(plugin, "on_policy_evaluate")
        assert hasattr(plugin, "on_plan_complete")

        # From MutatorPlugin
        assert hasattr(plugin, "on_plan_execute")
        assert hasattr(plugin, "execute")
        assert hasattr(plugin, "rollback")


class TestHelperFunctions:
    """Tests for SDK helper functions."""

    def test_get_logger(self):
        """get_logger returns configured logger."""
        logger = get_logger("my-plugin")
        assert logger is not None
        assert "my-plugin" in logger.name

    def test_normalize_path(self):
        """normalize_path resolves paths correctly."""
        path = normalize_path("~/test/file.txt")
        assert path.is_absolute()
        assert "~" not in str(path)

    def test_is_supported_container(self):
        """is_supported_container checks known formats."""
        assert is_supported_container("mkv") is True
        assert is_supported_container("MKV") is True
        assert is_supported_container("mp4") is True
        assert is_supported_container("xyz") is False

    def test_is_mkv_container(self):
        """is_mkv_container detects MKV formats."""
        assert is_mkv_container("mkv") is True
        assert is_mkv_container("matroska") is True
        assert is_mkv_container("mp4") is False


class TestMockFactories:
    """Tests for mock factory functions."""

    def test_mock_file_info(self):
        """mock_file_info creates valid FileInfo."""
        info = mock_file_info(path="/test/video.mkv")
        assert isinstance(info, FileInfo)
        assert info.path == Path("/test/video.mkv")
        assert info.filename == "video.mkv"

    def test_mock_track_info(self):
        """mock_track_info creates valid TrackInfo."""
        track = mock_track_info(index=1, track_type="audio")
        assert isinstance(track, TrackInfo)
        assert track.index == 1
        assert track.track_type == "audio"

    def test_mock_tracks(self):
        """mock_tracks creates list of tracks."""
        tracks = mock_tracks(video=1, audio=2, subtitle=1)
        assert len(tracks) == 4
        assert tracks[0].track_type == "video"
        assert tracks[1].track_type == "audio"
        assert tracks[2].track_type == "audio"
        assert tracks[3].track_type == "subtitle"

    def test_mock_plan(self, tmp_path: Path):
        """mock_plan creates valid Plan."""
        plan = mock_plan(file_path=tmp_path / "test.mkv")
        assert isinstance(plan, Plan)
        assert plan.file_path == tmp_path / "test.mkv"

    def test_mock_executor_result(self):
        """mock_executor_result creates valid ExecutorResult."""
        result = mock_executor_result(success=True, message="OK")
        assert isinstance(result, ExecutorResult)
        assert result.success is True
        assert result.message == "OK"


class TestEventFactories:
    """Tests for event factory functions."""

    def test_create_file_scanned_event(self):
        """create_file_scanned_event creates valid event."""
        event = create_file_scanned_event()
        assert isinstance(event, FileScannedEvent)
        assert event.file_info is not None
        assert event.tracks is not None

    def test_create_policy_evaluate_event(self):
        """create_policy_evaluate_event creates valid event."""
        event = create_policy_evaluate_event()
        assert isinstance(event, PolicyEvaluateEvent)
        assert event.file_info is not None
        assert event.policy is not None

    def test_create_plan_execute_event(self):
        """create_plan_execute_event creates valid event."""
        event = create_plan_execute_event()
        assert isinstance(event, PlanExecuteEvent)
        assert event.plan is not None


class TestPluginTestCase:
    """Tests for PluginTestCase."""

    def test_create_events(self):
        """PluginTestCase provides event creation methods."""
        test_case = PluginTestCase()

        event1 = test_case.create_file_scanned_event()
        assert isinstance(event1, FileScannedEvent)

        event2 = test_case.create_policy_evaluate_event()
        assert isinstance(event2, PolicyEvaluateEvent)

        event3 = test_case.create_plan_execute_event()
        assert isinstance(event3, PlanExecuteEvent)


class TestSDKModuleExports:
    """Tests for SDK module exports."""

    def test_base_classes_exported(self):
        """Base classes are exported from SDK."""
        from video_policy_orchestrator.plugin_sdk import (
            BaseAnalyzerPlugin,
            BaseDualPlugin,
            BaseMutatorPlugin,
        )

        assert BaseAnalyzerPlugin is not None
        assert BaseMutatorPlugin is not None
        assert BaseDualPlugin is not None

    def test_helpers_exported(self):
        """Helper functions are exported from SDK."""
        from video_policy_orchestrator.plugin_sdk import (
            get_config,
            get_data_dir,
            get_logger,
            get_plugin_storage_dir,
            is_mkv_container,
            is_supported_container,
            normalize_path,
        )

        assert callable(get_logger)
        assert callable(get_config)
        assert callable(get_data_dir)
        assert callable(get_plugin_storage_dir)
        assert callable(normalize_path)
        assert callable(is_supported_container)
        assert callable(is_mkv_container)

    def test_testing_utilities_exported(self):
        """Testing utilities are exported from SDK."""
        from video_policy_orchestrator.plugin_sdk import (
            PluginTestCase,
            create_file_scanned_event,
            create_plan_execute_event,
            create_policy_evaluate_event,
            mock_executor_result,
            mock_file_info,
            mock_plan,
            mock_track_info,
            mock_tracks,
        )

        assert PluginTestCase is not None
        assert callable(mock_file_info)
        assert callable(mock_track_info)
        assert callable(mock_tracks)
        assert callable(mock_plan)
        assert callable(mock_executor_result)
        assert callable(create_file_scanned_event)
        assert callable(create_policy_evaluate_event)
        assert callable(create_plan_execute_event)
