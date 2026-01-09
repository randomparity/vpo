"""Plugin system for Video Policy Orchestrator.

This package provides the plugin architecture for extending VPO with
custom analyzers and mutators.

API Version: 1.0.0
"""

from vpo.plugin.events import (
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
from vpo.plugin.exceptions import (
    PluginError,
    PluginLoadError,
    PluginNotAcknowledgedError,
    PluginNotFoundError,
    PluginValidationError,
    PluginVersionError,
)
from vpo.plugin.interfaces import (
    AnalyzerPlugin,
    MutatorPlugin,
)
from vpo.plugin.loader import (
    PluginLoader,
    compute_plugin_hash,
)
from vpo.plugin.manifest import (
    PluginManifest,
    PluginSource,
    PluginType,
)
from vpo.plugin.registry import (
    LoadedPlugin,
    PluginRegistry,
)
from vpo.plugin.version import (
    PLUGIN_API_VERSION,
    APIVersion,
    is_compatible,
)


def get_default_registry() -> PluginRegistry:
    """Create and initialize a PluginRegistry with built-in plugins.

    This is the standard way to get a registry for CLI commands and
    workflow processing. Creates a new registry each time (no caching).

    Returns:
        PluginRegistry with built-in plugins loaded.
    """
    registry = PluginRegistry()
    registry.load_builtin_plugins()
    return registry


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
    "get_default_registry",
    # Loader
    "PluginLoader",
    "compute_plugin_hash",
]
