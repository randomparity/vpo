"""Plugin system for Video Policy Orchestrator.

This package provides the plugin architecture for extending VPO with
custom analyzers and mutators.

API Version: 1.0.0
"""

from video_policy_orchestrator.plugin.events import (
    ANALYZER_EVENTS,
    FILE_METADATA_ENRICHED,
    FILE_SCANNED,
    MUTATOR_EVENTS,
    PLAN_AFTER_EXECUTE,
    PLAN_BEFORE_EXECUTE,
    PLAN_EXECUTION_FAILED,
    POLICY_AFTER_EVALUATE,
    POLICY_BEFORE_EVALUATE,
    VALID_EVENTS,
    FileMetadataEnrichedEvent,
    FileScannedEvent,
    PlanExecuteEvent,
    PolicyEvaluateEvent,
    is_analyzer_event,
    is_mutator_event,
    is_valid_event,
)
from video_policy_orchestrator.plugin.exceptions import (
    PluginError,
    PluginLoadError,
    PluginNotAcknowledgedError,
    PluginNotFoundError,
    PluginValidationError,
    PluginVersionError,
)
from video_policy_orchestrator.plugin.interfaces import (
    AnalyzerPlugin,
    MutatorPlugin,
)
from video_policy_orchestrator.plugin.loader import (
    PluginLoader,
    compute_plugin_hash,
)
from video_policy_orchestrator.plugin.manifest import (
    PluginManifest,
    PluginSource,
    PluginType,
)
from video_policy_orchestrator.plugin.registry import (
    LoadedPlugin,
    PluginRegistry,
)
from video_policy_orchestrator.plugin.version import (
    PLUGIN_API_VERSION,
    APIVersion,
    is_compatible,
)

__all__ = [
    # Version
    "PLUGIN_API_VERSION",
    "APIVersion",
    "is_compatible",
    # Manifest
    "PluginManifest",
    "PluginType",
    "PluginSource",
    # Interfaces
    "AnalyzerPlugin",
    "MutatorPlugin",
    # Events
    "FILE_SCANNED",
    "FILE_METADATA_ENRICHED",
    "POLICY_BEFORE_EVALUATE",
    "POLICY_AFTER_EVALUATE",
    "PLAN_BEFORE_EXECUTE",
    "PLAN_AFTER_EXECUTE",
    "PLAN_EXECUTION_FAILED",
    "VALID_EVENTS",
    "ANALYZER_EVENTS",
    "MUTATOR_EVENTS",
    "FileScannedEvent",
    "FileMetadataEnrichedEvent",
    "PolicyEvaluateEvent",
    "PlanExecuteEvent",
    "is_valid_event",
    "is_analyzer_event",
    "is_mutator_event",
    # Exceptions
    "PluginError",
    "PluginLoadError",
    "PluginNotFoundError",
    "PluginValidationError",
    "PluginVersionError",
    "PluginNotAcknowledgedError",
    # Registry
    "LoadedPlugin",
    "PluginRegistry",
    # Loader
    "PluginLoader",
    "compute_plugin_hash",
]
