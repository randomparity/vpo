# Quickstart: Plugin Architecture & Extension Model

**Feature**: 005-plugin-architecture
**Date**: 2025-11-22

## Overview

This quickstart guides you through creating, installing, and using VPO plugins.

## Creating a Simple Analyzer Plugin

### 1. Create Plugin File

Create `~/.vpo/plugins/my_analyzer.py`:

```python
"""My first VPO analyzer plugin."""

from video_policy_orchestrator.plugin_sdk import BaseAnalyzerPlugin

class MyAnalyzerPlugin(BaseAnalyzerPlugin):
    """Logs file scan events."""

    name = "my-analyzer"
    version = "1.0.0"
    description = "Logs when files are scanned"
    events = ["file.scanned"]

    def on_file_scanned(self, event):
        print(f"File scanned: {event.file_info.path}")
        print(f"  Tracks: {len(event.tracks)}")
        return None  # No metadata enrichment

# Plugin entry point
plugin = MyAnalyzerPlugin()
```

### 2. Acknowledge the Plugin

```bash
$ vpo plugins list
Found new directory plugin: my-analyzer
⚠️  Warning: Directory plugins run with full application permissions.
Allow 'my-analyzer'? [y/N]: y
Plugin acknowledged.

Installed Plugins:
  NAME           VERSION  TYPE      STATUS   SOURCE
  my-analyzer    1.0.0    analyzer  enabled  directory
  policy-engine  1.0.0    both      enabled  builtin
```

### 3. Run VPO

```bash
$ vpo scan /path/to/videos
File scanned: /path/to/videos/movie.mkv
  Tracks: 5
...
```

## Creating a Packaged Plugin (Entry Point)

### 1. Create Project Structure

```
my-vpo-plugin/
├── pyproject.toml
├── README.md
└── src/
    └── my_vpo_plugin/
        └── __init__.py
```

### 2. Configure Entry Point

`pyproject.toml`:
```toml
[project]
name = "my-vpo-plugin"
version = "1.0.0"
dependencies = ["video-policy-orchestrator>=0.1.0"]

[project.entry-points."vpo.plugins"]
my-plugin = "my_vpo_plugin:plugin"
```

### 3. Implement Plugin

`src/my_vpo_plugin/__init__.py`:
```python
from video_policy_orchestrator.plugin_sdk import BaseAnalyzerPlugin

class MyPlugin(BaseAnalyzerPlugin):
    name = "my-plugin"
    version = "1.0.0"
    events = ["file.scanned"]

    def on_file_scanned(self, event):
        # Your logic here
        return None

plugin = MyPlugin()
```

### 4. Install and Use

```bash
$ pip install -e ./my-vpo-plugin
$ vpo plugins list
Installed Plugins:
  NAME           VERSION  TYPE      STATUS   SOURCE
  my-plugin      1.0.0    analyzer  enabled  entry_point
  policy-engine  1.0.0    both      enabled  builtin
```

## Creating a Mutator Plugin

Mutator plugins can modify files during plan execution:

```python
from video_policy_orchestrator.plugin_sdk import BaseMutatorPlugin
from video_policy_orchestrator.executor.interface import ExecutorResult

class MyMutatorPlugin(BaseMutatorPlugin):
    name = "my-mutator"
    version = "1.0.0"
    events = ["plan.before_execute"]

    def on_plan_execute(self, event):
        # Optionally modify the plan
        print(f"About to execute plan for: {event.plan.file_path}")
        return None  # Proceed with original plan

    def execute(self, plan):
        # Perform your modifications
        # ...
        return ExecutorResult(success=True, message="Done")

plugin = MyMutatorPlugin()
```

## CLI Commands

```bash
# List all plugins
vpo plugins list

# List with verbose output
vpo plugins list -v

# Force load incompatible plugins (use with caution)
vpo --force-load-plugins scan /path

# Disable a plugin
vpo plugins disable my-plugin

# Enable a plugin
vpo plugins enable my-plugin
```

## Available Events

| Event | When Fired | Plugin Type |
|-------|------------|-------------|
| `file.scanned` | After ffprobe introspection | Analyzer |
| `policy.before_evaluate` | Before policy evaluation | Analyzer |
| `policy.after_evaluate` | After policy evaluation | Analyzer |
| `plan.before_execute` | Before plan execution | Mutator |
| `plan.after_execute` | After successful execution | Analyzer |
| `plan.execution_failed` | After execution failure | Analyzer |

## API Version Compatibility

Plugins declare supported API versions:

```python
class MyPlugin(BaseAnalyzerPlugin):
    name = "my-plugin"
    version = "1.0.0"
    min_api_version = "1.0.0"  # Minimum required
    max_api_version = "1.99.99"  # Maximum supported
```

If the core API version is outside this range, the plugin won't load by default.

## Testing Your Plugin

Use the SDK test utilities:

```python
from video_policy_orchestrator.plugin_sdk.testing import (
    PluginTestCase,
    mock_file_info,
    mock_tracks,
)

class TestMyPlugin(PluginTestCase):
    def test_on_file_scanned(self):
        plugin = MyAnalyzerPlugin()
        event = self.create_file_scanned_event(
            file_info=mock_file_info(path="/test/file.mkv"),
            tracks=mock_tracks(video=1, audio=2),
        )
        result = plugin.on_file_scanned(event)
        assert result is None
```

## Next Steps

- Read the full [Plugin Development Guide](../../../docs/plugins.md)
- Explore the [example plugin](../../../examples/plugins/simple_reorder_plugin/)
- Check the [API reference](./contracts/plugin_interfaces.py)
