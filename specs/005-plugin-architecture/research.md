# Research: Plugin Architecture & Extension Model

**Feature**: 005-plugin-architecture
**Date**: 2025-11-22

## Research Topics

### 1. Python Plugin Discovery Mechanisms

**Decision**: Use dual discovery: `importlib.metadata` entry points (primary) + directory scanning (secondary)

**Rationale**:
- Entry points are the Python standard for plugin discovery (PEP 621)
- `importlib.metadata` is stdlib in Python 3.10+ (no external dependency)
- Directory scanning enables drop-in development without package installation
- Both mechanisms are well-established patterns in Python ecosystem

**Alternatives Considered**:
| Alternative | Rejected Because |
|-------------|------------------|
| Entry points only | Poor developer experience for local testing |
| Directory only | No standard packaging integration |
| stevedore library | External dependency for something stdlib handles |
| pkg_resources | Deprecated in favor of importlib.metadata |

**Implementation Notes**:
- Entry point group: `vpo.plugins`
- Directory default: `~/.vpo/plugins/`
- Load order: entry points first (higher trust), then directory plugins

### 2. Plugin Interface Design Pattern

**Decision**: Use Python `typing.Protocol` for plugin interfaces

**Rationale**:
- Protocols enable structural subtyping (duck typing with type checking)
- No runtime inheritance requirement—plugins are loosely coupled
- Works well with existing VPO patterns (see `Executor` protocol in executor/interface.py)
- Type checkers (mypy, pyright) can validate plugin implementations

**Alternatives Considered**:
| Alternative | Rejected Because |
|-------------|------------------|
| Abstract Base Classes (ABC) | Requires explicit inheritance, tighter coupling |
| Plain duck typing | No static type checking, harder to document interface |
| Zope interfaces | External dependency, overkill for this use case |

**Implementation Notes**:
- Two protocols: `AnalyzerPlugin` (read-only) and `MutatorPlugin` (modifying)
- Plugins may implement one or both interfaces
- Include `@runtime_checkable` for isinstance() validation at load time

### 3. Event-Based Plugin Registration

**Decision**: Simple event subscription model with string event names

**Rationale**:
- Plugins declare which events they handle via class attribute or method
- Core fires events at defined points; registered plugins receive call
- Simpler than full observer pattern—no complex event objects initially
- Easy to extend with new events without breaking existing plugins

**Events for Initial Implementation**:
| Event | Trigger Point | Plugin Type |
|-------|---------------|-------------|
| `file.scanned` | After file introspection | AnalyzerPlugin |
| `policy.evaluate` | During policy evaluation | AnalyzerPlugin |
| `plan.execute` | During plan execution | MutatorPlugin |
| `plan.complete` | After execution success | AnalyzerPlugin |

**Alternatives Considered**:
| Alternative | Rejected Because |
|-------------|------------------|
| Fixed hook points | Less flexible, harder to add new hooks |
| Full pub/sub system | Over-engineered for current needs |
| Middleware chain | Better for request/response, not batch processing |

### 4. Plugin API Versioning Strategy

**Decision**: Semantic versioning with declared compatibility range

**Rationale**:
- Plugin declares `min_api_version` and `max_api_version`
- Core has `PLUGIN_API_VERSION` constant (semver string)
- Load-time check: plugin loads if core version in range
- Follows Constitution X (Policy Stability) and XI (Plugin Isolation)

**Version Compatibility Rules**:
- MAJOR bump: Breaking interface changes (require plugin updates)
- MINOR bump: New events/methods added (backward compatible)
- PATCH bump: Bug fixes (no interface changes)

**Implementation Notes**:
- Initial API version: `1.0.0`
- Plugins default to `min=1.0.0, max=1.x.x` (minor-compatible)
- CLI flag `--force-load-plugins` to override version check

### 5. Directory Plugin Security Model

**Decision**: First-load acknowledgment for directory-based plugins

**Rationale**:
- Directory plugins are higher risk (arbitrary local code)
- Entry point plugins come from pip packages (some vetting)
- Acknowledgment creates audit trail without blocking automation
- Recorded in SQLite to avoid repeated prompts

**Acknowledgment Flow**:
1. New directory plugin detected
2. Display warning: "Plugin 'X' found in directory. This plugin runs with full permissions."
3. Prompt: "Allow this plugin? [y/N]"
4. If yes: record `(plugin_name, plugin_hash, acknowledged_at)` in DB
5. On subsequent loads: check hash, skip prompt if unchanged

**Alternatives Considered**:
| Alternative | Rejected Because |
|-------------|------------------|
| No warnings | Violates user security expectations |
| Signature verification | Complex, requires key infrastructure |
| Allowlist config file | Less discoverable than interactive prompt |

### 6. Plugin Manifest Format

**Decision**: YAML manifest file or Python class attributes

**Rationale**:
- Support both: YAML file for complex metadata, class attributes for simple plugins
- YAML manifest: `plugin.yaml` in plugin directory
- Class attributes: `name`, `version`, `api_version`, `events` on plugin class
- Class attributes take precedence (allow dynamic values)

**Manifest Schema** (YAML):
```yaml
name: my-plugin
version: 1.0.0
description: Short description
author: Author Name
api_version:
  min: "1.0.0"
  max: "1.99.99"
plugin_type: analyzer  # or mutator, or both
events:
  - file.scanned
  - policy.evaluate
```

### 7. Built-in Policy Engine Refactoring

**Decision**: Extract policy engine into `plugins/policy_engine/` as reference implementation

**Rationale**:
- Dogfoods the plugin system (validates architecture)
- Provides concrete example for plugin authors
- Policy engine naturally fits AnalyzerPlugin (evaluation) + MutatorPlugin (execution)
- Existing tests continue to pass (same functionality, new structure)

**Migration Path**:
1. Create `PolicyEnginePlugin` class implementing both interfaces
2. Wire existing `policy/evaluator.py` logic into plugin
3. Register as built-in plugin (always loaded, can be disabled)
4. Update `vpo apply` to use plugin system for policy execution

### 8. Plugin SDK Design

**Decision**: Provide `vpo.plugin_sdk` with base classes and helpers

**SDK Components**:
| Component | Purpose |
|-----------|---------|
| `BaseAnalyzerPlugin` | Default implementations of AnalyzerPlugin methods |
| `BaseMutatorPlugin` | Default implementations of MutatorPlugin methods |
| `get_logger()` | Pre-configured logger for plugin use |
| `get_config()` | Access to VPO configuration |
| `PluginTestCase` | pytest fixtures for testing plugins |

**Rationale**:
- Reduces boilerplate for plugin authors
- Ensures consistent logging/config access patterns
- Test utilities encourage well-tested plugins
- Base classes provide sensible defaults (can be overridden)

## Resolved Clarifications

All NEEDS CLARIFICATION items from Technical Context have been resolved through this research.

## References

- PEP 621: Storing project metadata in pyproject.toml
- Python `importlib.metadata` documentation
- VPO Constitution (principles I-XVIII)
- Existing `Executor` protocol pattern in codebase
