"""Base classes for plugin development.

These base classes provide default implementations and reduce boilerplate
for plugin authors.
"""

from __future__ import annotations

import logging
from abc import ABC
from typing import Any

from vpo.executor.interface import ExecutorResult
from vpo.plugin.events import (
    FileScannedEvent,
    PlanExecuteEvent,
    PolicyEvaluateEvent,
    TranscriptionCompletedEvent,
    TranscriptionRequestedEvent,
)


class BaseAnalyzerPlugin(ABC):
    """Base class for analyzer plugins.

    Provides default implementations for AnalyzerPlugin protocol methods.
    Subclass and override the methods you need.

    Required attributes (set as class attributes or override as properties):
        name: str - Unique plugin identifier (kebab-case)
        version: str - Plugin version (semver)
        events: list[str] - Events to subscribe to

    Optional attributes:
        description: str - Human-readable description
        author: str - Plugin author
        min_api_version: str - Minimum API version (default: "1.0.0")
        max_api_version: str - Maximum API version (default: "1.99.99")

    Example:
        class MyPlugin(BaseAnalyzerPlugin):
            name = "my-analyzer"
            version = "1.0.0"
            events = ["file.scanned"]

            def on_file_scanned(self, event):
                # Enrich metadata
                return {"my_field": "value"}

    """

    # Required attributes (must be overridden)
    name: str
    version: str
    events: list[str]

    # Optional attributes (have defaults)
    description: str = ""
    author: str = ""
    min_api_version: str = "1.0.0"
    max_api_version: str = "1.99.99"

    def __init__(self) -> None:
        """Initialize the plugin."""
        self._logger = logging.getLogger(f"plugin.{self.name}")

    @property
    def logger(self) -> logging.Logger:
        """Get the plugin's logger."""
        return self._logger

    def on_file_scanned(self, event: FileScannedEvent) -> dict[str, Any] | None:
        """Called when a file is scanned.

        Override to enrich file metadata or perform analysis.

        Args:
            event: FileScannedEvent with file_info and tracks.

        Returns:
            Dict of enriched metadata to merge, or None.

        """
        return None

    def on_policy_evaluate(self, event: PolicyEvaluateEvent) -> None:
        """Called before/after policy evaluation.

        Override to observe or modify policy evaluation.

        Args:
            event: PolicyEvaluateEvent with file_info, policy, and optional plan.

        """
        pass

    def on_plan_complete(self, event: PlanExecuteEvent) -> None:
        """Called after plan execution completes.

        Override to observe execution results or perform cleanup.

        Args:
            event: PlanExecuteEvent with plan and result/error.

        """
        pass

    def on_transcription_requested(
        self, event: TranscriptionRequestedEvent
    ) -> Any | None:
        """Called when transcription is requested.

        Override to provide transcription services.

        Args:
            event: TranscriptionRequestedEvent with audio data and options.

        Returns:
            TranscriptionResult if transcription succeeded, None otherwise.

        """
        return None

    def on_transcription_completed(self, event: TranscriptionCompletedEvent) -> None:
        """Called after transcription completes.

        Override to observe or process transcription results.

        Args:
            event: TranscriptionCompletedEvent with the result.

        """
        pass


class BaseMutatorPlugin(ABC):
    """Base class for mutator plugins.

    Provides default implementations for MutatorPlugin protocol methods.
    Subclass and override the methods you need.

    Required attributes (set as class attributes or override as properties):
        name: str - Unique plugin identifier (kebab-case)
        version: str - Plugin version (semver)
        events: list[str] - Events to subscribe to

    Optional attributes:
        description: str - Human-readable description
        author: str - Plugin author
        min_api_version: str - Minimum API version (default: "1.0.0")
        max_api_version: str - Maximum API version (default: "1.99.99")
        supports_rollback: bool - Whether plugin can rollback (default: False)

    Example:
        class MyMutator(BaseMutatorPlugin):
            name = "my-mutator"
            version = "1.0.0"
            events = ["plan.before_execute"]

            def on_plan_execute(self, event):
                # Optionally modify the plan
                return None  # Proceed with original

            def execute(self, plan):
                # Perform modifications
                return ExecutorResult(success=True, message="Done")

    """

    # Required attributes (must be overridden)
    name: str
    version: str
    events: list[str]

    # Optional attributes (have defaults)
    description: str = ""
    author: str = ""
    min_api_version: str = "1.0.0"
    max_api_version: str = "1.99.99"
    supports_rollback: bool = False

    def __init__(self) -> None:
        """Initialize the plugin."""
        self._logger = logging.getLogger(f"plugin.{self.name}")

    @property
    def logger(self) -> logging.Logger:
        """Get the plugin's logger."""
        return self._logger

    def on_plan_execute(self, event: PlanExecuteEvent) -> Any | None:
        """Called before plan execution.

        Override to modify or replace the plan.

        Args:
            event: PlanExecuteEvent with the plan to execute.

        Returns:
            Modified Plan, or None to proceed with original.

        """
        return None

    def execute(self, plan: Any) -> ExecutorResult:
        """Execute the given plan.

        Must be overridden by mutator plugins that perform modifications.

        Args:
            plan: The execution plan to apply.

        Returns:
            ExecutorResult with success status and message.

        """
        return ExecutorResult(
            success=False,
            message="execute() not implemented",
        )

    def rollback(self, plan: Any) -> ExecutorResult:
        """Rollback changes made by execute().

        Override if supports_rollback is True.

        Args:
            plan: The plan that was executed.

        Returns:
            ExecutorResult with success status.

        """
        return ExecutorResult(
            success=False,
            message="rollback not supported",
        )


class BaseDualPlugin(BaseAnalyzerPlugin, BaseMutatorPlugin):
    """Base class for plugins implementing both interfaces.

    Combines BaseAnalyzerPlugin and BaseMutatorPlugin for plugins that
    need both analysis and mutation capabilities.

    Example:
        class MyPlugin(BaseDualPlugin):
            name = "my-dual-plugin"
            version = "1.0.0"
            events = ["file.scanned", "plan.before_execute"]

            def on_file_scanned(self, event):
                return {"analyzed": True}

            def execute(self, plan):
                return ExecutorResult(success=True, message="Done")

    """

    def __init__(self) -> None:
        """Initialize the plugin (single init for both base classes)."""
        self._logger = logging.getLogger(f"plugin.{self.name}")
