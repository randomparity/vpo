"""Policy Engine plugin implementation.

This module implements the Policy Engine as a built-in plugin, serving as both
a reference implementation and the primary policy evaluation mechanism for VPO.
"""

from __future__ import annotations

import logging
from typing import Any

from video_policy_orchestrator.db.models import TrackInfo
from video_policy_orchestrator.executor.ffmpeg_metadata import FfmpegMetadataExecutor
from video_policy_orchestrator.executor.ffmpeg_remux import FFmpegRemuxExecutor
from video_policy_orchestrator.executor.interface import (
    ExecutorResult,
    check_tool_availability,
)
from video_policy_orchestrator.executor.mkvmerge import MkvmergeExecutor
from video_policy_orchestrator.executor.mkvpropedit import MkvpropeditExecutor
from video_policy_orchestrator.plugin.events import (
    PLAN_AFTER_EXECUTE,
    PLAN_BEFORE_EXECUTE,
    PLAN_EXECUTION_FAILED,
    POLICY_AFTER_EVALUATE,
    POLICY_BEFORE_EVALUATE,
    PlanExecuteEvent,
    PolicyEvaluateEvent,
)
from video_policy_orchestrator.plugin.manifest import PluginSource
from video_policy_orchestrator.policy.evaluator import evaluate_policy
from video_policy_orchestrator.policy.models import ActionType, Plan, PolicySchema

logger = logging.getLogger(__name__)


class PolicyEnginePlugin:
    """Built-in policy engine plugin.

    This plugin implements both AnalyzerPlugin and MutatorPlugin interfaces,
    providing core policy evaluation and execution capabilities.

    As a built-in plugin, it is automatically loaded and cannot be
    unacknowledged. It can be disabled via the plugins CLI.
    """

    # Plugin metadata
    name = "policy-engine"
    version = "1.0.0"
    description = "Core policy evaluation and execution engine"
    author = "VPO Team"

    # API compatibility
    min_api_version = "1.0.0"
    max_api_version = "1.99.99"

    # Events this plugin handles
    events = [
        POLICY_BEFORE_EVALUATE,
        POLICY_AFTER_EVALUATE,
        PLAN_BEFORE_EXECUTE,
        PLAN_AFTER_EXECUTE,
        PLAN_EXECUTION_FAILED,
    ]

    # Plugin source (built-in)
    source = PluginSource.BUILTIN

    # Mutator plugin configuration
    supports_rollback = False

    def __init__(self) -> None:
        """Initialize the policy engine plugin."""
        self._keep_backup = True
        self._verbose = False
        logger.debug("PolicyEnginePlugin initialized")

    # ============================================================
    # AnalyzerPlugin interface methods
    # ============================================================

    def on_file_scanned(self, event: Any) -> dict[str, Any] | None:
        """Handle file.scanned event (not used by policy engine).

        The policy engine does not enrich file metadata during scanning.

        Args:
            event: FileScannedEvent data.

        Returns:
            None (no enrichment).
        """
        return None

    def on_policy_evaluate(self, event: PolicyEvaluateEvent) -> None:
        """Handle policy.before_evaluate and policy.after_evaluate events.

        For before_evaluate: Logs the evaluation start.
        For after_evaluate: Logs the evaluation result.

        Args:
            event: PolicyEvaluateEvent with file_info, policy, and optional plan.
        """
        if event.plan is None:
            # before_evaluate
            logger.debug(
                "Policy evaluation starting for: %s",
                event.file_path,
            )
        else:
            # after_evaluate
            logger.debug(
                "Policy evaluation completed: %s",
                event.plan.summary,
            )

    def on_plan_complete(self, event: PlanExecuteEvent) -> None:
        """Handle plan.after_execute and plan.execution_failed events.

        Args:
            event: PlanExecuteEvent with plan and result/error.
        """
        if event.error is not None:
            logger.warning(
                "Plan execution failed for %s: %s",
                event.plan.file_path,
                event.error,
            )
        elif event.result is not None:
            if event.result.success:
                logger.info(
                    "Plan execution succeeded for %s",
                    event.plan.file_path,
                )
            else:
                logger.warning(
                    "Plan execution failed for %s: %s",
                    event.plan.file_path,
                    event.result.message,
                )

    # ============================================================
    # MutatorPlugin interface methods
    # ============================================================

    def on_plan_execute(self, event: PlanExecuteEvent) -> Plan | None:
        """Handle plan.before_execute event.

        The policy engine passes through the plan unchanged.

        Args:
            event: PlanExecuteEvent with the plan to execute.

        Returns:
            None to proceed with original plan.
        """
        return None

    def execute(
        self,
        plan: Plan,
        keep_backup: bool = True,
        keep_original: bool = False,
    ) -> ExecutorResult:
        """Execute the given plan.

        Selects the appropriate executor based on container format and
        plan requirements, then executes the actions.

        Args:
            plan: The execution plan to apply.
            keep_backup: Whether to keep backup file after success.
            keep_original: Whether to keep original file after container
                conversion (only applies when output path differs from input).

        Returns:
            ExecutorResult with success status and message.
        """
        if plan.is_empty:
            return ExecutorResult(
                success=True,
                message="No changes required",
            )

        # Determine container format
        container = plan.file_path.suffix.lstrip(".").lower()
        if container == "matroska":
            container = "mkv"

        # Check tool availability
        tools = check_tool_availability()

        # Select appropriate executor
        executor = self._select_executor(plan, container, tools)
        if executor is None:
            return ExecutorResult(
                success=False,
                message=self._missing_tool_message(plan, container, tools),
            )

        # Execute the plan
        logger.info(
            "Executing plan for %s with %s",
            plan.file_path,
            type(executor).__name__,
        )

        try:
            return executor.execute(
                plan,
                keep_backup=keep_backup,
                keep_original=keep_original,
            )
        except Exception as e:
            logger.exception("Executor raised exception")
            return ExecutorResult(
                success=False,
                message=str(e),
            )

    def rollback(self, plan: Plan) -> ExecutorResult:
        """Rollback changes (not supported).

        The policy engine relies on backup files for recovery.

        Args:
            plan: The plan that was executed.

        Returns:
            ExecutorResult indicating rollback is not supported.
        """
        return ExecutorResult(
            success=False,
            message="PolicyEnginePlugin does not support rollback. "
            "Use backup files for recovery.",
        )

    # ============================================================
    # Core policy evaluation method
    # ============================================================

    def evaluate(
        self,
        file_id: str,
        file_path: Any,
        container: str,
        tracks: list[TrackInfo],
        policy: PolicySchema,
        transcription_results: dict | None = None,
        language_results: dict | None = None,
    ) -> Plan:
        """Evaluate a policy against file tracks.

        This is the primary entry point for policy evaluation, wrapping
        the core evaluate_policy function.

        Args:
            file_id: UUID of the file being evaluated.
            file_path: Path to the media file.
            container: Container format (mkv, mp4, etc.).
            tracks: List of track metadata.
            policy: Validated policy configuration.
            transcription_results: Optional dict mapping track_id to
                TranscriptionResultRecord for displaying transcription status.
            language_results: Optional dict mapping track_id to
                LanguageAnalysisResult for audio_is_multi_language conditions.

        Returns:
            Plan describing changes needed to conform to policy.
        """
        return evaluate_policy(
            file_id=file_id,
            file_path=file_path,
            container=container,
            tracks=tracks,
            policy=policy,
            transcription_results=transcription_results,
            language_results=language_results,
        )

    # ============================================================
    # Helper methods
    # ============================================================

    def _select_executor(
        self,
        plan: Plan,
        container: str,
        tools: dict[str, bool],
    ) -> Any | None:
        """Select appropriate executor for the plan.

        Selection priority:
        1. Container conversion - route based on target format
        2. Track filtering - requires remux capability
        3. Track reordering - requires mkvmerge for MKV
        4. Metadata-only changes - use in-place editing where possible

        Args:
            plan: Execution plan.
            container: Container format.
            tools: Available tools.

        Returns:
            Executor instance or None if required tool unavailable.
        """
        # Priority 1: Container conversion
        if plan.container_change:
            target = plan.container_change.target_format
            if target == "mp4":
                if not tools.get("ffmpeg"):
                    return None
                return FFmpegRemuxExecutor()
            elif target == "mkv":
                if not tools.get("mkvmerge"):
                    return None
                return MkvmergeExecutor()

        # Priority 2: Track filtering requires remux
        if plan.tracks_removed > 0:
            if container in ("mkv", "matroska"):
                if not tools.get("mkvmerge"):
                    return None
                return MkvmergeExecutor()
            # Non-MKV with track filtering needs ffmpeg remux
            if not tools.get("ffmpeg"):
                return None
            return FFmpegRemuxExecutor()

        # Priority 3: Track reordering (MKV only)
        if container in ("mkv", "matroska"):
            if plan.requires_remux:
                has_reorder = any(
                    a.action_type == ActionType.REORDER for a in plan.actions
                )
                if has_reorder:
                    if not tools.get("mkvmerge"):
                        return None
                    return MkvmergeExecutor()
            # Metadata-only changes use mkvpropedit
            if not tools.get("mkvpropedit"):
                return None
            return MkvpropeditExecutor()
        else:
            # Non-MKV metadata changes use ffmpeg
            if not tools.get("ffmpeg"):
                return None
            return FfmpegMetadataExecutor()

    def _missing_tool_message(
        self,
        plan: Plan,
        container: str,
        tools: dict[str, bool],
    ) -> str:
        """Generate error message for missing tool.

        Args:
            plan: Execution plan.
            container: Container format.
            tools: Available tools.

        Returns:
            Human-readable error message.
        """
        # Container conversion
        if plan.container_change:
            target = plan.container_change.target_format
            if target == "mp4" and not tools.get("ffmpeg"):
                return "MP4 conversion requires ffmpeg. Install ffmpeg."
            if target == "mkv" and not tools.get("mkvmerge"):
                return "MKV conversion requires mkvmerge. Install mkvtoolnix."

        # Track filtering
        if plan.tracks_removed > 0:
            if container in ("mkv", "matroska") and not tools.get("mkvmerge"):
                return "Track filtering requires mkvmerge. Install mkvtoolnix."
            if not tools.get("ffmpeg"):
                return "Track filtering requires ffmpeg. Install ffmpeg."

        # MKV-specific operations
        if container in ("mkv", "matroska"):
            if plan.requires_remux and not tools.get("mkvmerge"):
                return "Track reordering requires mkvmerge. Install mkvtoolnix."
            if not tools.get("mkvpropedit"):
                return "MKV editing requires mkvpropedit. Install mkvtoolnix."
        else:
            if not tools.get("ffmpeg"):
                return "Metadata editing requires ffmpeg. Install ffmpeg."
        return "Required tool not available."


# Plugin instance for discovery
# Named 'plugin_instance' to avoid shadowing the 'plugin' module name
# when accessed via package imports (e.g., 'from ... import plugin')
plugin_instance = PolicyEnginePlugin()
