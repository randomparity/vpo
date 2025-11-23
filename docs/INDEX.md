# Documentation Index

**Purpose:**
This index is the high-level map for all project documentation.
Every new doc should be linked here under the appropriate section.

---

## 1. Overview

High-level context for humans and agents: what this project is, what it does, and how the major pieces fit together.

- [overview/project-overview.md](overview/project-overview.md)
  Summary of the video policy project: goals, non-goals, major features, and target environments.

- [overview/architecture.md](overview/architecture.md)
  System architecture: scanners, policy engine, media tools (ffmpeg/mkvtoolnix), database, plugin system, and agent workflows.

- [overview/data-model.md](overview/data-model.md)
  Canonical data model for media items, tracks, policies, and policy applications (including IDs, timestamps, and status fields).

- [glossary.md](glossary.md)
  Definitions of key terms such as *media item*, *track*, *policy*, *scan run*, *plugin*, *dry run*, etc.

---

## 2. Usage & How-to

Docs focused on tasks and workflows: how to run the tools, configure them, and perform common operations.

- [tutorial.md](tutorial.md)
  Getting started guide: install VPO, scan your library, create and apply your first policy.

- [usage/cli-usage.md](usage/cli-usage.md)
  CLI entry points, subcommands, options, environment variables, and examples.

- [usage/configuration.md](usage/configuration.md)
  Configuration layout: config file, environment variables, tool paths, and extension filtering.

- [usage/transcode-policy.md](usage/transcode-policy.md)
  Transcode policy settings: video codecs, quality, resolution scaling, audio preservation.

- [usage/jobs.md](usage/jobs.md)
  Job queue management: listing, starting workers, canceling, and cleanup.

- [usage/external-tools.md](usage/external-tools.md)
  Guide to installing, configuring, and troubleshooting external tools (ffmpeg, mkvtoolnix).

- [usage/workflows.md](usage/workflows.md)
  End-to-end workflows for scanning libraries and inspecting files.

- [plugins.md](plugins.md)
  Plugin development guide: creating analyzers and mutators, events, versioning, and SDK usage.

---

## 3. Design & Internals

Design docs describing how subsystems work and the constraints/tradeoffs involved.
Use these when changing behavior or adding new subsystems.

**See also:** [Design Docs Index](design/DESIGN_INDEX.md)

- [design/design-database.md](design/design-database.md)
  Database schema and access patterns: tables, indices, foreign keys, and common queries.

- [design/design-media-scanner.md](design/design-media-scanner.md)
  How the directory scanner works: discovery rules, file filters, incremental re-scans, and Rust/Python architecture.

- [design/design-policy-engine.md](design/design-policy-engine.md) *(planned feature)*
  Policy representation, evaluation order, idempotence, and conflict resolution rules.

- [design/design-plugins.md](design/design-plugins.md) *(planned feature)*
  Plugin architecture: interfaces, lifecycle, versioning, and compatibility guarantees.

- [internals/error-handling.md](internals/error-handling.md)
  Error classification, custom exceptions, exit codes, and error reporting patterns.

- [internals/logging-and-metrics.md](internals/logging-and-metrics.md) *(planned feature)*
  Logging format (structured logs), log fields, and metrics for monitoring batch runs.

- [internals/time-and-timezones.md](internals/time-and-timezones.md)
  Rules for using UTC, timezone-aware datetimes, and serialization.

---

## 4. Architectural Decisions (ADRs)

Each ADR file documents a single decision: context, options, decision, and consequences.

- [decisions/ADR-0001-utc-everywhere.md](decisions/ADR-0001-utc-everywhere.md)
  Store all timestamps as timezone-aware UTC, with local-time conversion only at the edges.

- [decisions/ADR-0002-policy-schema-versioning.md](decisions/ADR-0002-policy-schema-versioning.md) *(proposed)*
  Versioned policy schema and migration approach when semantics change.

- [decisions/ADR-0003-plugin-interface-stability.md](decisions/ADR-0003-plugin-interface-stability.md) *(proposed)*
  Guarantees and expectations for plugin interface changes and version bumps.

> **When adding a new ADR:**
> - Use the filename pattern: `ADR-####-short-title.md`
> - Update this section with the new ADR and a one-line summary.

---

## 5. Agents & Automated Development

Guides and prompts specifically for LLM/agent workflows in this repository.

- [agents/agent-prompts.md](agents/agent-prompts.md)
  Reusable prompts for common development tasks like adding CLI commands, database tables, or introspectors.

- [agents/agent-playbook.md](agents/agent-playbook.md)
  Step-by-step instructions for how agents should work on this repo, including checklists and common pitfalls.

---

## 6. Contributing & Conventions

Guides for humans and agents on how to change the codebase.

- [../CONTRIBUTING.md](../CONTRIBUTING.md) *(optional)*
  Contribution guidelines, coding standards, and review expectations.

- [internals/error-handling.md](internals/error-handling.md) *(listed above)*
  Can be referenced for "how we handle errors" when writing new code.

---

## 7. How to Add New Docs

When adding any new documentation:

1. Put the file under one of the existing subdirectories:
   - `overview/`, `usage/`, `design/`, `decisions/`, `internals/`, `agents/`, or `glossary.md`.
2. Add a link to the new doc in the appropriate section of this `INDEX.md`.
3. Add a `## Related docs` section at the bottom of the new file with 3–5 links to closely related docs.

This keeps the documentation graph small, well-connected, and easy for both humans and agents to navigate.
