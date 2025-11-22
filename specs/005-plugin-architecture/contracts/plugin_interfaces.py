"""Plugin Interface Contracts.

This file defines the protocol interfaces that plugins must implement.
These are the stable contracts per Constitution XI (Plugin Isolation).

API Version: 1.0.0
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

# These would be actual imports in implementation
# from video_policy_orchestrator.db.models import FileInfo, TrackInfo
# from video_policy_orchestrator.policy.models import PolicySchema, Plan
# from video_policy_orchestrator.executor.interface import ExecutorResult


# =============================================================================
# Type Stubs (for contract definition - actual types from codebase)
# =============================================================================


class FileInfo(Protocol):
    """File information from database."""

    id: str
    path: Path
    size_bytes: int
    scanned_at: datetime


class TrackInfo(Protocol):
    """Track information from database."""

    id: str
    file_id: str
    track_index: int
    codec_type: str
    language: str | None


class PolicySchema(Protocol):
    """Policy configuration."""

    schema_version: int


class Plan(Protocol):
    """Execution plan."""

    file_id: str
    file_path: Path
    actions: tuple


class ExecutorResult(Protocol):
    """Result of execution."""

    success: bool
    message: str


# =============================================================================
# Plugin Manifest
# =============================================================================


class PluginManifest(Protocol):
    """Plugin metadata interface."""

    @property
    def name(self) -> str:
        """Unique plugin identifier."""
        ...

    @property
    def version(self) -> str:
        """Plugin version (semver)."""
        ...

    @property
    def description(self) -> str:
        """Human-readable description."""
        ...

    @property
    def min_api_version(self) -> str:
        """Minimum supported API version."""
        ...

    @property
    def max_api_version(self) -> str:
        """Maximum supported API version."""
        ...

    @property
    def events(self) -> list[str]:
        """List of events this plugin handles."""
        ...


# =============================================================================
# Event Data Types
# =============================================================================


class FileScannedEvent:
    """Data for file.scanned event."""

    def __init__(self, file_info: FileInfo, tracks: list[TrackInfo]) -> None:
        self.file_info = file_info
        self.tracks = tracks


class PolicyEvaluateEvent:
    """Data for policy.before_evaluate and policy.after_evaluate events."""

    def __init__(
        self,
        file_info: FileInfo,
        policy: PolicySchema,
        plan: Plan | None = None,
    ) -> None:
        self.file_info = file_info
        self.policy = policy
        self.plan = plan


class PlanExecuteEvent:
    """Data for plan.before_execute and plan.after_execute events."""

    def __init__(
        self,
        plan: Plan,
        result: ExecutorResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.plan = plan
        self.result = result
        self.error = error


# =============================================================================
# Plugin Interfaces
# =============================================================================


@runtime_checkable
class AnalyzerPlugin(Protocol):
    """Protocol for read-only analyzer plugins.

    Analyzer plugins can inspect files and tracks, enrich metadata,
    and observe execution events. They MUST NOT modify files.

    Required attributes (can be class attributes or properties):
        name: str - Unique plugin identifier
        version: str - Plugin version (semver)
        events: list[str] - Events to subscribe to

    Optional attributes:
        description: str - Human-readable description
        min_api_version: str - Minimum API version (default: "1.0.0")
        max_api_version: str - Maximum API version (default: "1.99.99")
    """

    name: str
    version: str
    events: list[str]

    def on_file_scanned(self, event: FileScannedEvent) -> dict[str, Any] | None:
        """Called after a file is scanned.

        Args:
            event: FileScannedEvent with file_info and tracks.

        Returns:
            Optional dict of enriched metadata to merge into file_info,
            or None if no enrichment.

        Note:
            Only called if 'file.scanned' in self.events.
        """
        ...

    def on_policy_evaluate(self, event: PolicyEvaluateEvent) -> None:
        """Called before/after policy evaluation.

        Args:
            event: PolicyEvaluateEvent with file_info, policy, and optional plan.

        Note:
            Only called if 'policy.before_evaluate' or 'policy.after_evaluate'
            in self.events.
        """
        ...

    def on_plan_complete(self, event: PlanExecuteEvent) -> None:
        """Called after plan execution completes (success or failure).

        Args:
            event: PlanExecuteEvent with plan and result/error.

        Note:
            Only called if 'plan.after_execute' or 'plan.execution_failed'
            in self.events.
        """
        ...


@runtime_checkable
class MutatorPlugin(Protocol):
    """Protocol for mutator plugins that can modify files.

    Mutator plugins receive plans and execute changes to media files.
    They are called during plan.before_execute and can modify or replace
    the plan, or perform additional modifications.

    Required attributes (can be class attributes or properties):
        name: str - Unique plugin identifier
        version: str - Plugin version (semver)
        events: list[str] - Events to subscribe to

    Optional attributes:
        description: str - Human-readable description
        min_api_version: str - Minimum API version (default: "1.0.0")
        max_api_version: str - Maximum API version (default: "1.99.99")
        supports_rollback: bool - Whether plugin can undo changes (default: False)
    """

    name: str
    version: str
    events: list[str]

    def on_plan_execute(self, event: PlanExecuteEvent) -> Plan | None:
        """Called before plan execution.

        Args:
            event: PlanExecuteEvent with the plan to execute.

        Returns:
            Modified Plan to execute instead, or None to proceed with original.
            Return an empty Plan to skip execution.

        Note:
            Only called if 'plan.before_execute' in self.events.
        """
        ...

    def execute(self, plan: Plan) -> ExecutorResult:
        """Execute the given plan.

        Args:
            plan: The execution plan to apply.

        Returns:
            ExecutorResult with success status and message.

        Note:
            This is the main execution method. Called by the core
            after on_plan_execute hooks have run.
        """
        ...

    def rollback(self, plan: Plan) -> ExecutorResult:
        """Rollback changes made by execute().

        Args:
            plan: The plan that was executed.

        Returns:
            ExecutorResult with success status.

        Note:
            Only called if supports_rollback is True and execute() succeeded
            but a later step failed.
        """
        ...


# =============================================================================
# Plugin Base Classes (SDK)
# =============================================================================


class BaseAnalyzerPlugin:
    """Base class for analyzer plugins with default implementations.

    Subclass this for convenience. All methods have no-op defaults.
    Override only the methods you need.

    Example:
        class MyAnalyzer(BaseAnalyzerPlugin):
            name = "my-analyzer"
            version = "1.0.0"
            events = ["file.scanned"]

            def on_file_scanned(self, event):
                return {"custom_field": "value"}
    """

    name: str = "unnamed-analyzer"
    version: str = "0.0.0"
    description: str = ""
    events: list[str] = []
    min_api_version: str = "1.0.0"
    max_api_version: str = "1.99.99"

    def on_file_scanned(self, event: FileScannedEvent) -> dict[str, Any] | None:
        """Default: no enrichment."""
        return None

    def on_policy_evaluate(self, event: PolicyEvaluateEvent) -> None:
        """Default: no action."""
        pass

    def on_plan_complete(self, event: PlanExecuteEvent) -> None:
        """Default: no action."""
        pass


class BaseMutatorPlugin:
    """Base class for mutator plugins with default implementations.

    Subclass this for convenience. Override execute() at minimum.

    Example:
        class MyMutator(BaseMutatorPlugin):
            name = "my-mutator"
            version = "1.0.0"
            events = ["plan.before_execute"]

            def execute(self, plan):
                # Do something
                return ExecutorResult(success=True)
    """

    name: str = "unnamed-mutator"
    version: str = "0.0.0"
    description: str = ""
    events: list[str] = []
    min_api_version: str = "1.0.0"
    max_api_version: str = "1.99.99"
    supports_rollback: bool = False

    def on_plan_execute(self, event: PlanExecuteEvent) -> Plan | None:
        """Default: proceed with original plan."""
        return None

    def execute(self, plan: Plan) -> ExecutorResult:
        """Must be implemented by subclass."""
        raise NotImplementedError("Subclass must implement execute()")

    def rollback(self, plan: Plan) -> ExecutorResult:
        """Default: rollback not supported."""
        raise NotImplementedError("Rollback not supported by this plugin")


# =============================================================================
# API Version
# =============================================================================

PLUGIN_API_VERSION = "1.0.0"
"""Current plugin API version. Plugins declare compatibility range."""
