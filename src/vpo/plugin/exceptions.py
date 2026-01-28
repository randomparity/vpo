"""Plugin system exceptions."""


class PluginError(Exception):
    """Base exception for plugin errors."""


class PluginNotFoundError(PluginError):
    """Plugin not found in discovery."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Plugin not found: {name}")


class PluginLoadError(PluginError):
    """Failed to load plugin."""

    def __init__(self, name: str, reason: str) -> None:
        self.name = name
        self.reason = reason
        super().__init__(f"Failed to load plugin '{name}': {reason}")


class PluginVersionError(PluginError):
    """Plugin version incompatible with core."""

    def __init__(
        self,
        name: str,
        plugin_range: tuple[str, str],
        core_version: str,
    ) -> None:
        self.name = name
        self.plugin_range = plugin_range
        self.core_version = core_version
        super().__init__(
            f"Plugin '{name}' requires API {plugin_range[0]}-{plugin_range[1]}, "
            f"but core is {core_version}"
        )


class PluginValidationError(PluginError):
    """Plugin failed validation."""

    def __init__(self, name: str, errors: list[str]) -> None:
        self.name = name
        self.errors = errors
        super().__init__(f"Plugin '{name}' validation failed: {'; '.join(errors)}")


class PluginNotAcknowledgedError(PluginError):
    """Directory plugin has not been acknowledged by user."""

    def __init__(self, name: str, path: str) -> None:
        self.name = name
        self.path = path
        super().__init__(
            f"Plugin '{name}' at {path} requires acknowledgment before loading"
        )
