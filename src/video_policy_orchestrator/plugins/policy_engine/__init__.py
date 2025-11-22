"""Policy Engine built-in plugin.

This package provides the core policy evaluation and execution
functionality as a built-in plugin.
"""

from video_policy_orchestrator.plugins.policy_engine.plugin import (
    PolicyEnginePlugin,
    plugin,
)

__all__ = ["PolicyEnginePlugin", "plugin"]
