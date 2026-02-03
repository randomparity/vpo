# ADR-0002: Policy Schema Versioning

**Status:** Accepted
**Date:** 2026-02-03
**Decision Makers:** Project maintainers

---

## Context

VPO will support user-defined policies in YAML/JSON format. As the project evolves:
- Policy schema may change (new fields, changed semantics)
- Users will have existing policy files
- Breaking changes could cause unexpected behavior

We need a strategy for evolving the policy format while maintaining compatibility.

---

## Decision

**To be determined** when the policy engine is implemented.

### Proposed Approach

Include a `version` field in all policy files:

```yaml
version: 1
name: "My Policy"
# ... policy content
```

The policy engine will:
1. Read the version field
2. Apply appropriate parser/migrator for that version
3. Optionally auto-upgrade to current version

---

## Options to Consider

### Option A: Strict Versioning

- Reject policies with unsupported versions
- Require explicit migration

### Option B: Automatic Migration

- Auto-upgrade old policies on load
- Optionally save upgraded version

### Option C: Multi-Version Support

- Support multiple schema versions indefinitely
- No forced migration

---

## Consequences

To be documented when the decision is made.

---

## Related docs

- [Policy Engine Design](../design/design-policy-engine.md)
- [Project Overview](../overview/project-overview.md)
