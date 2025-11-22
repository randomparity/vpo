"""Plugin registry for transcription plugins."""

import logging
from typing import TYPE_CHECKING

from video_policy_orchestrator.transcription.interface import TranscriptionError

if TYPE_CHECKING:
    from video_policy_orchestrator.transcription.interface import TranscriptionPlugin

logger = logging.getLogger(__name__)


class PluginNotFoundError(TranscriptionError):
    """Raised when a requested plugin is not found."""

    pass


class TranscriptionRegistry:
    """Registry for discovering and managing transcription plugins.

    The registry maintains a collection of available transcription plugins
    and provides methods to select and retrieve them by name.
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._plugins: dict[str, TranscriptionPlugin] = {}

    def register(self, plugin: "TranscriptionPlugin") -> None:
        """Register a transcription plugin.

        Args:
            plugin: Plugin instance to register.
        """
        logger.debug("Registering transcription plugin: %s", plugin.name)
        self._plugins[plugin.name] = plugin

    def unregister(self, name: str) -> bool:
        """Unregister a plugin by name.

        Args:
            name: Plugin name to unregister.

        Returns:
            True if plugin was removed, False if not found.
        """
        if name in self._plugins:
            del self._plugins[name]
            logger.debug("Unregistered transcription plugin: %s", name)
            return True
        return False

    def get(self, name: str) -> "TranscriptionPlugin":
        """Get a plugin by name.

        Args:
            name: Plugin name to retrieve.

        Returns:
            The requested plugin.

        Raises:
            PluginNotFoundError: If plugin is not registered.
        """
        if name not in self._plugins:
            available = list(self._plugins.keys())
            raise PluginNotFoundError(
                f"Plugin '{name}' not found. Available: {available}"
            )
        return self._plugins[name]

    def get_default(self) -> "TranscriptionPlugin | None":
        """Get the default plugin (first registered).

        Returns:
            The first registered plugin, or None if none registered.
        """
        if not self._plugins:
            return None
        return next(iter(self._plugins.values()))

    def list_plugins(self) -> list[str]:
        """List all registered plugin names.

        Returns:
            List of plugin names.
        """
        return list(self._plugins.keys())

    def has_plugin(self, name: str) -> bool:
        """Check if a plugin is registered.

        Args:
            name: Plugin name to check.

        Returns:
            True if plugin is registered.
        """
        return name in self._plugins

    def __len__(self) -> int:
        """Return number of registered plugins."""
        return len(self._plugins)


# Global registry instance
_registry: TranscriptionRegistry | None = None


def get_registry(
    config: "TranscriptionPluginConfig | None" = None,
) -> TranscriptionRegistry:
    """Get the global transcription plugin registry.

    Creates the registry on first access and attempts to discover
    available plugins.

    Args:
        config: Optional configuration for plugin initialization.

    Returns:
        The global TranscriptionRegistry instance.
    """
    global _registry
    if _registry is None:
        _registry = TranscriptionRegistry()
        _discover_plugins(_registry, config)
    return _registry


def _discover_plugins(
    registry: TranscriptionRegistry,
    config: "TranscriptionPluginConfig | None" = None,
) -> None:
    """Discover and register available transcription plugins.

    Currently discovers the built-in Whisper plugin. Can be extended
    to support entry points or configuration-based discovery.

    Args:
        registry: Registry to populate with discovered plugins.
        config: Optional configuration for plugin initialization.
    """
    # Try to load built-in Whisper plugin
    try:
        from video_policy_orchestrator.plugins.whisper_transcriber import (
            WhisperTranscriptionPlugin,
        )
        from video_policy_orchestrator.transcription.models import TranscriptionConfig

        # Create config from VPO config if provided
        transcription_config = None
        if config:
            transcription_config = TranscriptionConfig(
                enabled_plugin=config.plugin,
                model_size=config.model_size,
                sample_duration=config.sample_duration,
                gpu_enabled=config.gpu_enabled,
            )

        # Only register if dependencies are available
        plugin = WhisperTranscriptionPlugin(config=transcription_config)
        registry.register(plugin)
        logger.info("Discovered Whisper transcription plugin")
    except ImportError:
        logger.debug("Whisper plugin dependencies not available")
    except Exception as e:
        logger.warning("Failed to load Whisper plugin: %s", e)


# Import type for type hints
from typing import TYPE_CHECKING  # noqa: E402

if TYPE_CHECKING:
    from video_policy_orchestrator.config.models import TranscriptionPluginConfig
