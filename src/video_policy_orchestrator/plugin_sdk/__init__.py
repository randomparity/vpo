"""Plugin SDK for Video Policy Orchestrator.

This package provides base classes and utilities for plugin authors,
making it easy to create plugins with minimal boilerplate.

Base Classes:
    BaseAnalyzerPlugin: Base for read-only analysis plugins
    BaseMutatorPlugin: Base for file-modifying plugins
    BaseDualPlugin: Base for plugins implementing both interfaces

Helper Functions:
    get_logger: Get a configured logger for a plugin
    get_config: Get VPO configuration
    get_data_dir: Get VPO data directory
    get_plugin_storage_dir: Get plugin-specific storage directory
    normalize_path: Normalize file paths
    is_supported_container: Check container format support
    is_mkv_container: Check if MKV format
    get_host_identifier: Get host identifier for tracking

Testing Utilities:
    PluginTestCase: Base class for plugin tests
    mock_file_info: Create mock FileInfo
    mock_track_info: Create mock TrackInfo
    mock_tracks: Create mock track list
    mock_plan: Create mock Plan
    mock_executor_result: Create mock ExecutorResult
    create_file_scanned_event: Create test event
    create_policy_evaluate_event: Create test event
    create_plan_execute_event: Create test event

Example:
    from video_policy_orchestrator.plugin_sdk import (
        BaseAnalyzerPlugin,
        get_logger,
    )

    class MyPlugin(BaseAnalyzerPlugin):
        name = "my-plugin"
        version = "1.0.0"
        events = ["file.scanned"]

        def on_file_scanned(self, event):
            self.logger.info("Analyzing %s", event.file_path)
            return {"custom_field": "value"}

    plugin = MyPlugin()

"""

# Base classes
from video_policy_orchestrator.plugin_sdk.base import (
    BaseAnalyzerPlugin,
    BaseDualPlugin,
    BaseMutatorPlugin,
)

# Helper functions
from video_policy_orchestrator.plugin_sdk.helpers import (
    get_config,
    get_data_dir,
    get_host_identifier,
    get_logger,
    get_plugin_storage_dir,
    is_mkv_container,
    is_supported_container,
    normalize_path,
)

# Testing utilities
from video_policy_orchestrator.plugin_sdk.testing import (
    PluginTestCase,
    create_file_scanned_event,
    create_plan_execute_event,
    create_policy_evaluate_event,
    create_transcription_completed_event,
    create_transcription_requested_event,
    mock_executor_result,
    mock_file_info,
    mock_plan,
    mock_track_info,
    mock_tracks,
)

__all__ = [
    # Base classes
    "BaseAnalyzerPlugin",
    "BaseMutatorPlugin",
    "BaseDualPlugin",
    # Helpers
    "get_logger",
    "get_config",
    "get_data_dir",
    "get_plugin_storage_dir",
    "get_host_identifier",
    "normalize_path",
    "is_supported_container",
    "is_mkv_container",
    # Testing
    "PluginTestCase",
    "mock_file_info",
    "mock_track_info",
    "mock_tracks",
    "mock_plan",
    "mock_executor_result",
    "create_file_scanned_event",
    "create_policy_evaluate_event",
    "create_plan_execute_event",
    "create_transcription_requested_event",
    "create_transcription_completed_event",
]
