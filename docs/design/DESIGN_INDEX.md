# Design Docs Index

**Purpose:**
This index lists all *design* and *internals* documentation for the video policy project.
Use it when you're changing behavior, adding subsystems, or making architectural decisions.

Design docs are focused on **how** things work and **why** they were built that way.

---

## 1. Core Design Docs

High-level designs of the major subsystems.

- [design-database.md](design-database.md)
  - Logical schema for media items, tracks, policies, and policy runs.
  - Constraints and indexes (e.g. uniqueness of media IDs, foreign keys between tracks and media items).
  - Query patterns to support reporting and debugging (e.g. "what changed in this run?").
  - Migration strategy as fields and relationships evolve.

- [design-media-scanner.md](design-media-scanner.md)
  - How directory trees and files are discovered via Rust core.
  - Filtering rules (file extensions, symlinks).
  - Incremental scans and re-scans using modification time comparison.
  - Hybrid Python/Rust architecture for performance.

- [design-policy-engine.md](design-policy-engine.md) *(planned feature)*
  - How policies are represented (schema/DSL).
  - Evaluation order (e.g. per-file, per-track, pipelines).
  - Idempotence guarantees: running the same policy twice over the same file must not corrupt or duplicate data.
  - Conflict resolution when multiple rules affect the same track or metadata field.

- [design-plugins.md](design-plugins.md) *(planned feature)*
  - Definition of plugin interfaces (`AnalyzerPlugin`, `MutatorPlugin`, `TranscriptionPlugin`).
  - Allowed responsibilities vs. responsibilities that must stay in the core engine.
  - Plugin discovery/registration mechanism.
  - Compatibility/versioning rules for plugin authors.

---

## 2. Cross-Cutting Internal Concerns

Design docs that cut across multiple subsystems.

- [../internals/error-handling.md](../internals/error-handling.md)
  - Error taxonomy (expected vs. unexpected).
  - Custom exception classes (`MediaIntrospectionError`, `DatabaseLockedError`).
  - When to fail fast vs. log-and-skip vs. retry.
  - How errors are reported in the CLI with exit codes.

- [../internals/time-and-timezones.md](../internals/time-and-timezones.md)
  - Rules for using UTC and timezone-aware datetimes.
  - Where conversions to local time are allowed (presentation only).
  - Serialization format (ISO-8601) for timestamps in logs, DB, and APIs.

- [../internals/logging-and-metrics.md](../internals/logging-and-metrics.md) *(planned feature)*
  - Structured logging format (fields like `run_id`, `media_id`, `policy_id`).
  - Metrics for performance and reliability (throughput, error rates, per-policy timings).
  - Log levels and sampling strategies for large batch runs.

---

## 3. Planned / Optional Design Docs

These are suggested slots for future design docs as the project grows.
When you create one of these, replace the placeholder summary with a concrete description.

- `design-job-runner.md` *(planned)*
  - Orchestration of batch runs: scheduling, parallelism model, safe shutdown.
  - How per-run configuration and state are tracked.

- `design-api-and-cli-layer.md` *(planned)*
  - Design of the user-facing API/CLI surface: commands, flags, error messages.
  - Versioning strategy for user-facing interfaces.

- `design-config-system.md` *(planned)*
  - Hierarchy and precedence of configuration sources (env vars, files, CLI flags).
  - Validation and schema for configuration items.

---

## 4. How to Add a New Design Doc

When adding a new design document:

1. **Choose a location and name**
   - Place it in this directory: `docs/design/`.
   - Use a descriptive, kebab-case filename: `design-something-descriptive.md`.
2. **Update this index**
   - Add a new bullet under the appropriate section above (or create a new section if truly necessary).
   - Provide a short, 1–3 line summary of what the doc covers.
3. **Connect it to the rest of the doc graph**
   - At the bottom of the new design doc, add a `## Related docs` section linking to:
     - This index (`[Design docs index](./DESIGN_INDEX.md)`), and
     - Any strongly related overview, usage, internals, or ADR docs.
4. **Keep scope focused**
   - Each design doc should describe one subsystem or cross-cutting concern.
   - If you find yourself mixing topics, split into two design docs and cross-link them.

This process keeps design documentation small, discoverable, and easy for both humans and agents to ingest and maintain.

---

## Related docs

- [Documentation Index](../INDEX.md)
- [Architecture Overview](../overview/architecture.md)
- [Data Model](../overview/data-model.md)
