# Plugin Development Guide

This guide explains how to create plugins for Video Policy Orchestrator (VPO).

## Overview

VPO supports two types of plugins:

- **AnalyzerPlugin**: Read-only plugins that analyze media files and enrich metadata
- **MutatorPlugin**: Plugins that can modify media files during plan execution

Plugins subscribe to events fired by VPO during its operations. A single plugin can implement both interfaces.

## Quick Start

### 1. Create a Simple Analyzer Plugin

Create a file in `~/.vpo/plugins/my_plugin.py`:

```python
"""My VPO analyzer plugin."""

from vpo.plugin_sdk import BaseAnalyzerPlugin

class MyPlugin(BaseAnalyzerPlugin):
    name = "my-plugin"
    version = "1.0.0"
    description = "Logs scanned files"
    events = ["file.scanned"]

    def on_file_scanned(self, event):
        print(f"Scanned: {event.file_info.path}")
        return None  # No metadata enrichment

plugin = MyPlugin()
```

### 2. List Available Plugins

```bash
vpo plugins list
```

The first time you use a directory plugin, VPO will ask for acknowledgment.

## Plugin Types

### AnalyzerPlugin

Analyzer plugins observe VPO operations and can enrich file metadata. They cannot modify files.

```python
from vpo.plugin_sdk import BaseAnalyzerPlugin

class MyAnalyzer(BaseAnalyzerPlugin):
    name = "my-analyzer"
    version = "1.0.0"
    events = ["file.scanned", "policy.after_evaluate"]

    def on_file_scanned(self, event):
        # Called after ffprobe introspection
        # Return dict to add metadata, or None
        return {"custom_field": "value"}

    def on_policy_evaluate(self, event):
        # Called before/after policy evaluation
        pass

    def on_plan_complete(self, event):
        # Called after plan execution success or failure
        pass
```

### MutatorPlugin

Mutator plugins can modify media files during plan execution.

```python
from vpo.plugin_sdk import BaseMutatorPlugin
from vpo.executor.interface import ExecutorResult

class MyMutator(BaseMutatorPlugin):
    name = "my-mutator"
    version = "1.0.0"
    events = ["plan.before_execute"]

    def on_plan_execute(self, event):
        # Called before execution - can modify or replace the plan
        # Return modified Plan or None to use original
        return None

    def execute(self, plan, keep_backup=True):
        # Execute your modifications
        return ExecutorResult(success=True, message="Done")

    def rollback(self, plan):
        # Called if execution fails (optional)
        return ExecutorResult(success=False, message="Rollback not supported")
```

## Events

Plugins subscribe to events by listing them in the `events` attribute.

| Event | Trigger | Plugin Type | Event Data |
|-------|---------|-------------|------------|
| `file.scanned` | After ffprobe introspection | Analyzer | FileScannedEvent |
| `policy.before_evaluate` | Before policy evaluation | Analyzer | PolicyEvaluateEvent |
| `policy.after_evaluate` | After policy evaluation | Analyzer | PolicyEvaluateEvent |
| `plan.before_execute` | Before plan execution | Mutator | PlanExecuteEvent |
| `plan.after_execute` | After successful execution | Analyzer | PlanExecuteEvent |
| `plan.execution_failed` | After execution failure | Analyzer | PlanExecuteEvent |

## Plugin Discovery

VPO discovers plugins from two sources:

### 1. Entry Points (Recommended for Distribution)

Register your plugin in `pyproject.toml`:

```toml
[project.entry-points."vpo.plugins"]
my-plugin = "my_package:plugin"
```

Entry point plugins are trusted and don't require acknowledgment.

### 2. Directory Plugins (Development)

Place plugins in:
- `~/.vpo/plugins/` (default)
- Custom directories via `plugin_dirs` config

Directory plugins require user acknowledgment before first use.

## API Versioning

VPO uses semantic versioning for the plugin API. Plugins declare their compatibility:

```python
class MyPlugin(BaseAnalyzerPlugin):
    name = "my-plugin"
    version = "1.0.0"
    min_api_version = "1.0.0"
    max_api_version = "1.99.99"
```

### Version Compatibility Rules

- **MAJOR** version changes break compatibility
- **MINOR** version changes add features (backward compatible)
- **PATCH** version changes fix bugs

If a plugin's version range doesn't include the current API version, it won't load (unless `--force-load-plugins` is used).

### Current API Version

The current plugin API version is **1.1.0**.

### Compatibility Guidelines

When specifying version ranges:

1. **For stability**: Set `max_api_version = "1.99.99"` to accept all 1.x releases
2. **For specific features**: Set `min_api_version` to the version that introduced features you need
3. **For maximum compatibility**: Test against both min and max versions before release

Example conservative range:
```python
min_api_version = "1.0.0"   # Requires at least 1.0.0
max_api_version = "1.99.99" # Accepts any 1.x release
```

### Deprecation Policy

VPO follows a structured deprecation policy for plugin API changes:

1. **Minor versions (1.x.0)**: May add new optional methods and events
   - Existing plugins continue to work without changes
   - New features are opt-in

2. **Deprecation warnings**: Features slated for removal are marked with warnings
   - Warnings appear in logs for at least 2 minor versions
   - Documentation notes the deprecation and migration path

3. **Major versions (2.0.0)**: May remove deprecated features
   - Breaking changes require major version bump
   - Changelog documents all breaking changes
   - Migration guide provided for affected plugins

4. **Support timeline**:
   - API version 1.x will be supported for the foreseeable future
   - At least 6 months notice before any breaking changes
   - LTS (Long Term Support) branches may be maintained for critical fixes

## Plugin Manifest

Every plugin must have these attributes:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | str | Yes | Unique identifier (kebab-case) |
| `version` | str | Yes | Plugin version (semver) |
| `description` | str | No | Human-readable description |
| `author` | str | No | Plugin author |
| `events` | list[str] | Yes | Events to subscribe to |
| `min_api_version` | str | No | Minimum API version (default: "1.0.0") |
| `max_api_version` | str | No | Maximum API version (default: "1.99.99") |

## Plugin SDK

The SDK provides base classes and utilities:

```python
from vpo.plugin_sdk import (
    BaseAnalyzerPlugin,  # Base class for analyzers
    BaseMutatorPlugin,   # Base class for mutators
    get_logger,          # Get configured logger
    get_config,          # Get VPO configuration
)
```

### Testing Utilities

```python
from vpo.plugin_sdk.testing import (
    PluginTestCase,
    mock_file_info,
    mock_tracks,
    create_file_scanned_event,
)

class TestMyPlugin(PluginTestCase):
    def test_on_file_scanned(self):
        plugin = MyPlugin()
        event = create_file_scanned_event(
            file_info=mock_file_info(path="/test/file.mkv"),
            tracks=mock_tracks(video=1, audio=2),
        )
        result = plugin.on_file_scanned(event)
        assert result is None
```

## CLI Commands

```bash
# List all plugins
vpo plugins list

# List with verbose output
vpo plugins list -v

# Enable a disabled plugin
vpo plugins enable my-plugin

# Disable a plugin
vpo plugins disable my-plugin

# Force load incompatible plugins
vpo --force-load-plugins scan /path
```

## Security Model

### Directory Plugin Acknowledgment

Directory plugins can execute arbitrary code. Before first use, VPO:

1. Displays a warning about the plugin's capabilities
2. Prompts for confirmation
3. Records acknowledgment in the database

If the plugin's content changes (different hash), re-acknowledgment is required.

### Hash Coverage

Plugin acknowledgment uses SHA-256 hashes to detect changes. **Important limitations:**

- **Only `.py` files are hashed** - Changes to non-Python files (data files, configs, JSON, etc.) will not trigger re-acknowledgment
- For single-file plugins, only that file is hashed
- For package plugins (directories with `__init__.py`), all `.py` files in the directory tree are hashed

This means a plugin could potentially modify behavior through non-Python files without triggering a re-acknowledgment. When reviewing directory plugins, examine all files in the plugin directory, not just Python code.

### Entry Point Plugins

Entry point plugins come from installed Python packages and don't require acknowledgment. They are considered trusted because they went through pip installation.

## Best Practices

1. **Use base classes**: Inherit from `BaseAnalyzerPlugin` or `BaseMutatorPlugin`
2. **Handle errors gracefully**: Never crash VPO - catch exceptions and log warnings
3. **Be explicit about events**: Only subscribe to events you actually handle
4. **Test thoroughly**: Use the SDK testing utilities
5. **Version conservatively**: Set `max_api_version` to allow minor updates

## Built-in Plugins

VPO ships with built-in metadata enrichment plugins for Radarr and Sonarr:

| Plugin | Description | Documentation |
|--------|-------------|---------------|
| `radarr-metadata` | Enriches movie files with Radarr metadata | [Radarr Plugin Docs](../src/vpo/plugins/radarr_metadata/README.md) |
| `sonarr-metadata` | Enriches TV episode files with Sonarr metadata | [Sonarr Plugin Docs](../src/vpo/plugins/sonarr_metadata/README.md) |

These plugins connect to your Radarr/Sonarr instances via their v3 APIs to provide
metadata for use in policy conditions and actions. See each plugin's documentation
for configuration, available metadata fields, and example policies.

## Example Plugin Project

See `examples/plugins/simple_reorder_plugin/` for a complete example including:

- `pyproject.toml` with entry point configuration
- Implementation using `BaseAnalyzerPlugin`
- README with usage instructions

## Related docs

- [quickstart.md](../specs/005-plugin-architecture/quickstart.md) - Plugin quickstart scenarios
- [contracts/](../specs/005-plugin-architecture/contracts/) - Plugin interface definitions
- [data-model.md](../specs/005-plugin-architecture/data-model.md) - Plugin data models
