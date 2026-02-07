"""Plugin interface protocols.

This module defines the Protocol interfaces that plugins must implement.
These are the stable contracts per Constitution XI (Plugin Isolation).

API Version: 1.0.0
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from vpo.plugin.events import (
    FileScannedEvent,
    PlanExecuteEvent,
    PolicyEvaluateEvent,
)


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

    # Note: Plugins may optionally implement close() for resource cleanup.
    # This is NOT part of the protocol to maintain backward compatibility.
    # The registry's shutdown_all() method will call close() if it exists.

    # Note: Plugins may optionally implement on_transcription_requested()
    # to handle transcription requests. This is NOT part of the protocol
    # to maintain backward compatibility with existing plugins.
    # See BaseAnalyzerPlugin for default implementation.
    #
    # def on_transcription_requested(
    #     self, event: TranscriptionRequestedEvent
    # ) -> Any | None:
    #     """Handle a transcription request.
    #
    #     Args:
    #         event: TranscriptionRequestedEvent with audio data and options.
    #
    #     Returns:
    #         TranscriptionResult if transcription succeeded, None otherwise.
    #     """
    #
    # Similarly, plugins may implement on_transcription_completed() to observe
    # transcription results:
    #
    # def on_transcription_completed(
    #     self, event: TranscriptionCompletedEvent
    # ) -> None:
    #     """Called after transcription completes."""


@runtime_checkable
class MutatorPlugin(Protocol):
    """Protocol for mutator plugins that can modify files.

    Mutator plugins receive plans and execute changes to media files.
    They are called during plan.before_execute and can modify or replace
    the plan, or perform additional modifications.

    Security note:
        Mutators can modify execution plans and write to the filesystem.
        They run with full process permissions. Only load mutator plugins
        from trusted sources.

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

    def on_plan_execute(self, event: PlanExecuteEvent) -> Any | None:
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

    def execute(self, plan: Any) -> Any:
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

    def rollback(self, plan: Any) -> Any:
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

    # Note: Plugins may optionally implement close() for resource cleanup.
    # This is NOT part of the protocol to maintain backward compatibility.
    # The registry's shutdown_all() method will call close() if it exists.
