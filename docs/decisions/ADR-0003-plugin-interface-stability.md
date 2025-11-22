# ADR-0003: Plugin Interface Stability

**Status:** Proposed
**Date:** TBD
**Decision Makers:** Project maintainers

> **Note:** This ADR is a placeholder for a future decision. The plugin system has not yet been implemented.

---

## Context

VPO will support a plugin system for extensibility. Plugin authors need to know:
- What interface guarantees they can rely on
- How breaking changes will be communicated
- When they need to update their plugins

---

## Decision

**To be determined** when the plugin system is implemented.

### Proposed Approach

Define stability levels for plugin APIs:

| Level | Meaning | Breaking Changes |
|-------|---------|------------------|
| Stable | Production ready | Major versions only |
| Beta | Feature complete | Minor versions may break |
| Alpha | Experimental | Any version may break |

Include API version in plugin protocol:

```python
class MyPlugin:
    api_version = "1.0"  # Requires VPO API 1.x
```

---

## Options to Consider

### Option A: Semantic Versioning

- Follow semver strictly
- Major bumps allow breaking changes
- Document deprecation path

### Option B: Explicit API Versions

- Separate API version from VPO version
- Support multiple API versions
- Explicit compatibility matrix

### Option C: Interface Evolution

- Only add to interfaces, never remove
- Use optional fields for new capabilities
- Never break existing plugins

---

## Consequences

To be documented when the decision is made.

---

## Related docs

- [Plugin System Design](../design/design-plugins.md)
- [Architecture Overview](../overview/architecture.md)
