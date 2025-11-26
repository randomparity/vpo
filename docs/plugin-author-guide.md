# Plugin Author Guide

This guide walks you through creating, testing, and publishing VPO plugins. It focuses on the development workflow rather than API details (see [plugins.md](plugins.md) for the API reference).

## Quick Start

The fastest way to create a plugin is to copy the hello_world template:

```bash
# Copy the template
cp -r examples/plugins/hello_world ~/my-vpo-plugin
cd ~/my-vpo-plugin

# Rename the package
mv src/hello_world src/my_plugin

# Install in development mode
pip install -e ".[dev]"

# Verify it loads
vpo plugins list
```

## Project Structure

A VPO plugin is a standard Python package with an entry point:

```text
my-plugin/
├── pyproject.toml          # Package config with entry point
├── README.md               # Usage documentation
├── src/
│   └── my_plugin/
│       └── __init__.py     # Plugin implementation
└── tests/
    └── test_plugin.py      # Tests
```

## Step 1: Create pyproject.toml

The entry point tells VPO how to find your plugin:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "vpo-my-plugin"
version = "0.1.0"
description = "My VPO plugin"
requires-python = ">=3.10"
dependencies = [
    "video-policy-orchestrator>=0.1.0",
]

[project.optional-dependencies]
dev = ["pytest>=7.0", "ruff>=0.1.0"]

# This is the critical part - the entry point
[project.entry-points."vpo.plugins"]
my-plugin = "my_plugin:plugin"  # module:variable

[tool.hatch.build.targets.wheel]
packages = ["src/my_plugin"]
```

The entry point format is `name = "module:variable"` where:
- `name` is the plugin name (kebab-case)
- `module` is the Python module containing your plugin
- `variable` is the plugin instance variable name

## Step 2: Implement Your Plugin

### Analyzer Plugin (Read-Only)

Most plugins are analyzers that observe VPO operations:

```python
"""My VPO Plugin."""

from video_policy_orchestrator.plugin_sdk import (
    BaseAnalyzerPlugin,
    get_logger,
)

logger = get_logger(__name__)


class MyPlugin(BaseAnalyzerPlugin):
    """Plugin that analyzes scanned files."""

    name = "my-plugin"
    version = "0.1.0"
    description = "Does something useful with video files"
    events = ["file.scanned"]

    # API compatibility (accept all 1.x releases)
    min_api_version = "1.0.0"
    max_api_version = "1.99.99"

    def on_file_scanned(self, event):
        """Called after ffprobe introspection."""
        self.logger.info("Processing: %s", event.file_info.path)

        # Optionally return metadata to store with the file
        return {"my_field": "value"}


# Create the plugin instance (referenced by entry point)
plugin = MyPlugin()
```

### Mutator Plugin (File Modification)

Mutator plugins can modify files during plan execution:

```python
from video_policy_orchestrator.plugin_sdk import BaseMutatorPlugin
from video_policy_orchestrator.executor.interface import ExecutorResult


class MyMutator(BaseMutatorPlugin):
    """Plugin that modifies files."""

    name = "my-mutator"
    version = "0.1.0"
    events = ["plan.before_execute"]

    def on_plan_execute(self, event):
        """Called before execution - can modify the plan."""
        return None  # Return modified Plan or None

    def execute(self, plan, keep_backup=True):
        """Execute your modifications."""
        # Do something with the file
        return ExecutorResult(success=True, message="Done")


plugin = MyMutator()
```

## Step 3: Handle Events

### Available Events

| Event | When Fired | Return Value |
|-------|------------|--------------|
| `file.scanned` | After ffprobe introspection | Dict (metadata) or None |
| `policy.before_evaluate` | Before policy evaluation | None |
| `policy.after_evaluate` | After policy evaluation | None |
| `plan.before_execute` | Before plan execution | Modified Plan or None |
| `plan.after_execute` | After successful execution | None |
| `plan.execution_failed` | After execution failure | None |

### Event Data

Each event provides relevant data:

```python
def on_file_scanned(self, event):
    # FileScannedEvent attributes
    file_info = event.file_info  # FileInfo dataclass
    tracks = event.tracks        # List[TrackInfo]

    # FileInfo attributes
    path = file_info.path        # pathlib.Path
    filename = file_info.filename
    container = file_info.container  # "matroska", "mp4", etc.
    size_bytes = file_info.size_bytes
    duration_seconds = file_info.duration_seconds
```

## Step 4: Use Helper Functions

The SDK provides useful helpers:

```python
from video_policy_orchestrator.plugin_sdk import (
    get_logger,          # Configured logger
    get_config,          # VPO configuration
    get_data_dir,        # ~/.vpo/
    get_plugin_storage_dir,  # Plugin-specific storage
    is_mkv_container,    # Check container format
)

class MyPlugin(BaseAnalyzerPlugin):
    # ...

    def on_file_scanned(self, event):
        # Use the plugin's logger
        self.logger.info("Processing file")

        # Get plugin-specific storage
        storage = get_plugin_storage_dir(self.name)
        cache_file = storage / "cache.json"

        # Check container format
        if is_mkv_container(event.file_info.container):
            # MKV-specific logic
            pass
```

## Step 5: Write Tests

Use the SDK testing utilities:

```python
import pytest
from my_plugin import MyPlugin, plugin


class TestMyPlugin:
    def test_manifest(self):
        """Test plugin manifest is valid."""
        assert plugin.name == "my-plugin"
        assert plugin.version == "0.1.0"
        assert "file.scanned" in plugin.events

    def test_on_file_scanned(self):
        """Test event handler."""
        try:
            from video_policy_orchestrator.plugin_sdk.testing import (
                create_file_scanned_event,
                mock_file_info,
                mock_tracks,
            )

            event = create_file_scanned_event(
                file_info=mock_file_info(path="/test/movie.mkv"),
                tracks=mock_tracks(video=1, audio=2),
            )

            result = plugin.on_file_scanned(event)
            # Assert on result
        except ImportError:
            pytest.skip("VPO not installed")
```

Run tests:

```bash
pytest tests/
```

## Step 6: Verify Your Plugin

### Check Lint/Format

```bash
ruff check src/
ruff format src/
```

### Test Installation

```bash
# Install in development mode
pip install -e .

# Verify plugin loads
vpo plugins list

# Should show your plugin
```

### Test with Real Files

```bash
# Scan some files
vpo scan ~/Videos

# Check logs for your plugin's output
```

## Step 7: Publish to PyPI

### Prepare for Release

1. Update version in `pyproject.toml`
2. Ensure tests pass
3. Update README with usage instructions

### Build and Upload

```bash
# Build the package
python -m build

# Upload to TestPyPI first
python -m twine upload --repository testpypi dist/*

# Test installation from TestPyPI
pip install --index-url https://test.pypi.org/simple/ vpo-my-plugin

# Upload to PyPI
python -m twine upload dist/*
```

### Naming Convention

Use the `vpo-` prefix for discoverability:
- Package name: `vpo-my-plugin`
- Import name: `my_plugin`
- Plugin name: `my-plugin`

## Best Practices

### Error Handling

Never crash VPO - catch and log exceptions:

```python
def on_file_scanned(self, event):
    try:
        # Your logic here
        pass
    except Exception as e:
        self.logger.warning("Failed to process %s: %s", event.file_info.path, e)
        return None  # Continue without failing
```

### Performance

- Avoid blocking operations in event handlers
- Use caching for expensive computations
- Log sparingly to avoid output spam

### API Compatibility

Set conservative version ranges:

```python
min_api_version = "1.0.0"   # Minimum features needed
max_api_version = "1.99.99" # Accept all 1.x releases
```

### Logging

Use the plugin logger, not print():

```python
self.logger.debug("Detailed info")  # Only shown with -v
self.logger.info("Normal info")
self.logger.warning("Something unexpected")
self.logger.error("Something failed")
```

## Troubleshooting

### Plugin Not Loading

1. Check entry point in `pyproject.toml`
2. Verify module path matches package structure
3. Run `pip install -e .` again after changes

### Import Errors

Ensure VPO is installed:

```bash
pip install video-policy-orchestrator
```

### Version Incompatibility

If you see "API version incompatible":
1. Check your `min_api_version` and `max_api_version`
2. Update version ranges if needed
3. Use `--force-load-plugins` for testing

## Resources

- [Plugin API Reference](plugins.md) - Complete API documentation
- [Hello World Template](../examples/plugins/hello_world/) - Starter template
- [VPO Documentation](INDEX.md) - Full documentation index

## Related docs

- [plugins.md](plugins.md) - Plugin API reference and event details
- [tutorial.md](tutorial.md) - Getting started with VPO
- [usage/cli-usage.md](usage/cli-usage.md) - CLI command reference
- [overview/architecture.md](overview/architecture.md) - System architecture
