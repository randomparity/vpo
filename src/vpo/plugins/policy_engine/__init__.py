"""Policy Engine built-in plugin.

This package provides the core policy evaluation and execution
functionality as a built-in plugin.
"""

from vpo.plugins.policy_engine.plugin import (
    PolicyEnginePlugin,
    plugin_instance,
)

__all__ = ["PolicyEnginePlugin", "plugin_instance"]
