# Plugin System Design

**Purpose:**
This document describes the design of VPO's plugin system for extending functionality.

> **Status:** Implemented (Plugin API v1.1.0). See [Plugin Author Guide](../plugin-author-guide.md) for current usage.

---

## Overview

The plugin system will allow third-party extensions to add functionality:
- **Analyzer plugins**: Enrich metadata, perform checks, tag content
- **Mutator plugins**: Modify containers, rewrite metadata, move files
- **Transcription plugins**: Speech-to-text, language detection

---

## Plugin Types

### Analyzer Plugins

Read-only plugins that analyze content and add metadata:

```python
class AnalyzerPlugin(Protocol):
    """Protocol for analyzer plugins."""

    name: str
    version: str

    def analyze(self, file_path: Path, tracks: list[TrackInfo]) -> AnalysisResult:
        """Analyze a file and return additional metadata."""
        ...
```

**Examples:**
- Language detection via audio analysis
- Commentary track identification
- Quality assessment (bitrate, encoding issues)

### Mutator Plugins

Plugins that can modify files:

```python
class MutatorPlugin(Protocol):
    """Protocol for mutator plugins."""

    name: str
    version: str

    def mutate(self, file_path: Path, changes: list[Change]) -> MutationResult:
        """Apply changes to a file."""
        ...
```

**Examples:**
- Metadata editors (mkvpropedit wrapper)
- Track remuxers
- File movers/renamers

### Transcription Plugins

Specialized plugins for speech-to-text:

```python
class TranscriptionPlugin(Protocol):
    """Protocol for transcription plugins."""

    name: str
    version: str

    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        """Transcribe audio to text with language detection."""
        ...
```

**Examples:**
- Whisper integration
- Cloud transcription services

---

## Plugin Discovery

Plugins will be discovered via:

### 1. Entry Points

Standard Python packaging mechanism:

```toml
# In plugin's pyproject.toml
[project.entry-points."vpo.plugins"]
my_analyzer = "my_plugin:MyAnalyzerPlugin"
```

### 2. Plugin Directories

Configurable directories for local plugins:

```yaml
# ~/.vpo/config.yaml
plugins:
  directories:
    - ~/.vpo/plugins
    - /opt/vpo-plugins
```

---

## Plugin Lifecycle

1. **Discovery**: Find all available plugins at startup
2. **Loading**: Import and instantiate plugin classes
3. **Validation**: Check version compatibility and requirements
4. **Registration**: Add to plugin registry
5. **Execution**: Call plugin methods during operations
6. **Cleanup**: Release resources on shutdown

---

## Versioning and Compatibility

### Plugin API Version

The core will define an API version. Plugins declare compatibility:

```python
class MyPlugin:
    api_version = "1.0"  # Compatible with VPO API 1.x
```

### Stability Guarantees

- Major version changes may break plugins
- Minor version changes add features, remain compatible
- Patch versions are always compatible

See [ADR-0003: Plugin Interface Stability](../decisions/ADR-0003-plugin-interface-stability.md).

---

## Security Considerations

- Plugins run with full process permissions
- Users should only install trusted plugins
- Future: Plugin sandboxing for untrusted code

---

## Implementation Notes

This feature is planned for Sprint 4 (Plugin Architecture).

Dependencies:
- Completed: Library scanner (002)
- Completed: Media introspection (003)
- Required: Policy engine (in progress)

---

## Related docs

- [Design Docs Index](DESIGN_INDEX.md)
- [Architecture Overview](../overview/architecture.md)
- [Policy Engine Design](design-policy-engine.md)
- [ADR-0003: Plugin Interface Stability](../decisions/ADR-0003-plugin-interface-stability.md)
