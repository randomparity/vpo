# Simple Reorder Plugin

An example VPO (Video Policy Orchestrator) plugin that demonstrates how to create an analyzer plugin using the VPO Plugin SDK.

## What This Plugin Does

This plugin provides a simple analysis function that reports on subtitle track positions in media files. It's designed to be a minimal example showing how to:

1. Create a plugin using the Plugin SDK base classes
2. Handle `file.scanned` events
3. Return metadata enrichment from an analyzer
4. Register as a VPO plugin via entry points

## Installation

### From Source (Development)

```bash
# Clone the VPO repository
cd examples/plugins/simple_reorder_plugin

# Install in development mode
pip install -e .
```

### Via pip

```bash
pip install simple-reorder-plugin
```

## Usage

Once installed, the plugin is automatically discovered by VPO:

```bash
# List installed plugins
vpo plugins list

# The plugin activates on file scans
vpo scan /path/to/videos
```

## Plugin Output

When a file is scanned, this plugin logs:
- Number of subtitle tracks found
- Position of first subtitle track relative to video tracks
- Whether subtitles appear immediately after video (preferred) or are scattered

## Code Structure

```
simple_reorder_plugin/
├── pyproject.toml     # Package configuration with entry point
├── README.md          # This file
└── src/
    └── simple_reorder/
        └── __init__.py  # Plugin implementation
```

## Creating Your Own Plugin

Use this plugin as a template:

1. Copy this directory to a new location
2. Rename `simple_reorder` to your plugin name
3. Update `pyproject.toml` with your plugin details
4. Modify `__init__.py` to implement your logic
5. Install and test: `pip install -e . && vpo plugins list`

## Plugin Interface

This plugin implements the `AnalyzerPlugin` protocol:

```python
from vpo.plugin_sdk import BaseAnalyzerPlugin

class SimpleReorderPlugin(BaseAnalyzerPlugin):
    name = "simple-reorder"
    version = "1.0.0"
    events = ["file.scanned"]

    def on_file_scanned(self, event):
        # Analyze the scanned file
        # Return metadata dict or None
        return {"analyzed": True}
```

## Testing

```bash
# Run the plugin's tests
pytest tests/

# Or use the VPO SDK test utilities
from vpo.plugin_sdk.testing import PluginTestCase
```

## License

MIT License - see the VPO project for full license text.

## Related Documentation

- [VPO Plugin Development Guide](../../../docs/plugins.md)
- [Plugin SDK API Reference](../../../specs/005-plugin-architecture/contracts/)
- [VPO Main Documentation](../../../docs/INDEX.md)
