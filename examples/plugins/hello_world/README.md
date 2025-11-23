# Hello World VPO Plugin

A minimal example plugin for Video Policy Orchestrator (VPO). Use this as a template for your own plugins.

## Features

- Demonstrates the basic plugin structure
- Shows how to subscribe to `file.scanned` events
- Includes example metadata enrichment
- Includes basic tests

## Installation

### Development Install

```bash
cd examples/plugins/hello_world
pip install -e ".[dev]"
```

### Production Install

```bash
pip install vpo-hello-world
```

## Usage

After installation, verify the plugin is loaded:

```bash
vpo plugins list
```

You should see `hello-world` in the list.

Run a scan to see the plugin in action:

```bash
vpo scan /path/to/your/videos
```

The plugin will log a greeting for each scanned file.

## Customization

To create your own plugin:

1. Copy this entire directory
2. Rename `hello_world` to your plugin name
3. Update `pyproject.toml`:
   - Change `name` to your package name
   - Update the entry point key
   - Update author information
4. Modify `src/hello_world/__init__.py`:
   - Rename the class
   - Change the `name` attribute
   - Update `events` to subscribe to the events you need
   - Implement your event handlers

## Available Events

| Event | Trigger | Plugin Type |
|-------|---------|-------------|
| `file.scanned` | After ffprobe introspection | Analyzer |
| `policy.before_evaluate` | Before policy evaluation | Analyzer |
| `policy.after_evaluate` | After policy evaluation | Analyzer |
| `plan.before_execute` | Before plan execution | Mutator |
| `plan.after_execute` | After successful execution | Analyzer |
| `plan.execution_failed` | After execution failure | Analyzer |

## Testing

Run the included tests:

```bash
pytest tests/
```

## Project Structure

```
hello_world/
├── pyproject.toml          # Package configuration with entry point
├── README.md               # This file
├── src/
│   └── hello_world/
│       └── __init__.py     # Plugin implementation
└── tests/
    └── test_plugin.py      # Plugin tests
```

## Resources

- [Plugin Development Guide](../../../docs/plugins.md)
- [Plugin Author Guide](../../../docs/plugin-author-guide.md)
- [VPO Documentation](../../../docs/INDEX.md)

## License

MIT License - feel free to use this template for any purpose.
