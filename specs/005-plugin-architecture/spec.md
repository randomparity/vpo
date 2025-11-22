# Feature Specification: Plugin Architecture & Extension Model

**Feature Branch**: `005-plugin-architecture`
**Created**: 2025-11-22
**Status**: Draft
**Input**: User description: "Introduce a plugin system so new policies and actions can be added independently from the core application."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Plugin Interface Definition (Priority: P1)

As a systems architect, I want stable interfaces for plugins so that extensions can be developed and versioned independently from the core application.

**Why this priority**: This is the foundation for the entire plugin system. Without well-defined interfaces, plugin authors cannot develop extensions reliably, and the core team cannot evolve the system without breaking third-party plugins.

**Independent Test**: Can be fully tested by implementing a minimal plugin that conforms to each interface and verifying it compiles/validates without errors.

**Acceptance Scenarios**:

1. **Given** the plugin SDK is installed, **When** a developer implements the AnalyzerPlugin interface, **Then** they can create a read-only plugin that inspects files/tracks and enriches metadata without modifying files.
2. **Given** the plugin SDK is installed, **When** a developer implements the MutatorPlugin interface, **Then** they can create a plugin that receives a plan and executes changes to media files.
3. **Given** a plugin implements the required interface methods, **When** the plugin is loaded, **Then** the system validates that all required methods are present and have correct signatures.
4. **Given** interface documentation exists, **When** a developer reads the plugin documentation, **Then** they understand the contract, lifecycle, and expected behavior for each plugin type.

---

### User Story 2 - Plugin Discovery & Loading (Priority: P1)

As a user, I want plugins to be auto-discovered from a directory or Python entry points so that installing a plugin is simple and doesn't require manual configuration.

**Why this priority**: Users need a way to install and use plugins without deep technical knowledge. Simple discovery mechanisms (drop a file in a folder, or pip install a package) make the plugin ecosystem accessible.

**Independent Test**: Can be tested by placing a plugin in the designated directory and verifying it appears in the installed plugins list without additional configuration.

**Acceptance Scenarios**:

1. **Given** a plugin file placed in the configured plugin directory, **When** the application starts, **Then** the plugin is automatically discovered and available for use.
2. **Given** a Python package with the correct entry point configured, **When** the package is installed via pip, **Then** the plugin is automatically discovered and available for use.
3. **Given** multiple plugins are installed, **When** the user runs `vpo plugins list`, **Then** they see a list of all installed plugins with name, version, type (analyzer/mutator), and status (enabled/disabled).
4. **Given** a plugin fails to load due to errors, **When** the application starts, **Then** the error is logged with details and other plugins continue loading normally.
5. **Given** multiple discovery sources (directory and entry points), **When** plugins are loaded, **Then** plugins from all sources are merged without duplicates (same plugin name from different sources raises a conflict warning).

---

### User Story 3 - Built-In Policy Plugin (Priority: P2)

As a user, I want the core policy engine implemented as a first-party plugin so that I can see a reference implementation and understand how to build my own plugins.

**Why this priority**: Dogfooding the plugin system by implementing core functionality as a plugin validates the architecture and provides users with a working example. This demonstrates the system is capable of handling real-world use cases.

**Independent Test**: Can be tested by disabling the built-in policy plugin and verifying the policy engine functionality becomes unavailable.

**Acceptance Scenarios**:

1. **Given** the built-in track ordering policy plugin, **When** examining its source code, **Then** a developer can understand how to implement analyzer and mutator functionality.
2. **Given** the built-in plugin is enabled (default), **When** running `vpo apply --policy`, **Then** the policy engine works as expected for track ordering, language preferences, and metadata changes.
3. **Given** the built-in plugin is disabled, **When** running `vpo apply --policy`, **Then** the system reports that no policy plugin is available.
4. **Given** an example third-party plugin template is provided, **When** a developer uses the template, **Then** they can create a new plugin with minimal boilerplate.

---

### User Story 4 - Plugin SDK Skeleton (Priority: P2)

As a plugin author, I want a minimal SDK or helper library so that I can implement new plugins with minimal boilerplate and focus on my plugin's unique functionality.

**Why this priority**: Reducing friction for plugin authors encourages ecosystem growth. A good SDK with helpers, base classes, and utilities makes plugin development faster and produces more consistent plugins.

**Independent Test**: Can be tested by creating a new plugin project using the SDK and verifying the project structure, imports, and base functionality work correctly.

**Acceptance Scenarios**:

1. **Given** the plugin_sdk package is installed, **When** a developer imports base classes, **Then** they have access to AnalyzerPlugin and MutatorPlugin base classes with default implementations.
2. **Given** the SDK provides a plugin template project, **When** a developer creates a new plugin project, **Then** the project includes proper structure, dependencies, and example code.
3. **Given** an example plugin project exists at examples/plugins/simple_reorder_plugin, **When** a developer examines the example, **Then** they see a complete, working plugin implementation demonstrating best practices.
4. **Given** the SDK provides utility functions, **When** a developer uses helpers for common tasks (logging, config access, error handling), **Then** their plugin integrates seamlessly with the core application.

---

### User Story 5 - Spec & Versioning Contract (Priority: P3)

As a maintainer, I want plugin API versioning documented so that breaking changes are controlled and plugin authors can plan for compatibility.

**Why this priority**: Long-term ecosystem health requires clear versioning policies. Plugin authors need confidence that their plugins won't break unexpectedly, and core maintainers need freedom to evolve the system.

**Independent Test**: Can be tested by verifying documentation exists and the system enforces version compatibility checks at plugin load time.

**Acceptance Scenarios**:

1. **Given** the plugin API documentation, **When** examining version information, **Then** maintainers and plugin authors can see the current API version and compatibility requirements.
2. **Given** a plugin declares a supported API version range, **When** the plugin loads, **Then** the system validates compatibility and warns or errors if versions don't match.
3. **Given** the deprecation guidelines exist, **When** a maintainer plans to remove or change an API, **Then** they follow the documented process for deprecation notices and migration periods.
4. **Given** an API breaking change is needed, **When** the change is made, **Then** the API version is incremented and release notes document the migration path.

---

### Edge Cases

- What happens when two plugins have the same name? The system raises a conflict warning and loads only the first discovered plugin; user can resolve by renaming or removing one plugin.
- What happens when a plugin depends on a specific core version? The system checks version compatibility at load time and disables incompatible plugins with a clear error message.
- How does the system handle plugins that crash during execution? The plugin execution is wrapped in error handling; failures are logged and the core application continues with degraded functionality.
- What happens when a plugin directory doesn't exist? The system creates the directory on first use or skips silently if configured to use entry points only.
- How does the system handle circular dependencies between plugins? Plugins are loaded in isolation; inter-plugin dependencies are not supported in the initial version.
- What happens when a mutator plugin makes changes that violate another plugin's expectations? Plugins execute in a defined order; later plugins operate on the results of earlier plugins.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST define an AnalyzerPlugin interface for read-only plugins that inspect files/tracks and enrich metadata.
- **FR-002**: System MUST define a MutatorPlugin interface for plugins that receive a plan and execute changes to media files.
- **FR-003**: System MUST discover plugins from configurable directories (default: `~/.vpo/plugins/`).
- **FR-004**: System MUST discover plugins from Python entry points (entry point group: `vpo.plugins`).
- **FR-005**: System MUST provide a `vpo plugins list` command showing all installed plugins with name, version, type, and status.
- **FR-006**: System MUST validate plugin interfaces at load time and reject plugins that don't implement required methods.
- **FR-007**: System MUST gracefully handle plugin load failures without crashing the core application.
- **FR-008**: System MUST log plugin discovery, loading, and errors for debugging.
- **FR-008a**: System MUST warn and require user acknowledgment on first load of directory-based plugins; acknowledged plugins are recorded to avoid repeated prompts.
- **FR-009**: System MUST implement the core policy engine as a built-in plugin that can be enabled/disabled.
- **FR-010**: System MUST provide a video_policy_orchestrator.plugin_sdk package with base classes and utilities.
- **FR-011**: System MUST provide an example plugin project at examples/plugins/simple_reorder_plugin.
- **FR-012**: System MUST document the plugin API version and maintain version compatibility information.
- **FR-013**: System MUST check plugin API version compatibility at load time.
- **FR-014**: System MUST allow plugins to declare their supported API version range.
- **FR-015**: System MUST block loading of plugins with version compatibility issues by default; a CLI flag allows overriding this to load incompatible plugins with warnings.
- **FR-016**: System MUST provide documentation for plugin development in docs/plugins.md.
- **FR-017**: System MUST define a plugin execution order and ensure predictable execution sequence; plugins self-register for specific events they want to handle.
- **FR-018**: System MUST isolate plugin failures so one failing plugin doesn't prevent others from running.

### Key Entities

- **AnalyzerPlugin**: A plugin type that inspects files and tracks, enriching metadata without making modifications. Key attributes include: name, version, supported API version, analyze method.
- **MutatorPlugin**: A plugin type that receives a plan and executes changes to media files. Key attributes include: name, version, supported API version, execute method, rollback capability.
- **PluginRegistry**: Central catalog of discovered plugins. Manages discovery from multiple sources, deduplication, and provides access to loaded plugins.
- **PluginManifest**: Metadata describing a plugin. Attributes include: name, version, description, author, plugin type, supported API versions, dependencies.
- **APIVersion**: Versioning information for the plugin interface. Follows semantic versioning; plugins declare minimum and maximum supported versions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Plugin discovery completes within 1 second for up to 50 installed plugins.
- **SC-002**: 100% of plugin load failures are logged with actionable error messages.
- **SC-003**: Developers can create a minimal working plugin in under 30 minutes using the SDK and documentation.
- **SC-004**: The built-in policy plugin passes all existing policy engine tests when loaded as a plugin.
- **SC-005**: The example plugin project compiles and runs without modification.
- **SC-006**: Plugin API documentation covers 100% of public interfaces and methods.
- **SC-007**: Plugin version compatibility is validated at load time with clear user feedback for mismatches.

## Clarifications

### Session 2025-11-22

- Q: When are plugins invoked in the core workflow? → A: Plugins self-register for specific events they want to handle
- Q: Should incompatible plugins be loaded or blocked? → A: Block loading by default, allow override via CLI flag
- Q: Should the system warn about plugins from unknown sources? → A: Warn on first load of directory-based plugins, require user acknowledgment

## Assumptions

- The Python entry point system (setuptools/importlib.metadata) is available and suitable for plugin discovery.
- Plugins are single-Python-package or single-file implementations (no complex multi-package plugins initially).
- The existing policy engine code (from 004-policy-engine) can be refactored into a plugin structure.
- Users have basic Python knowledge sufficient to install packages and create simple modules.
- Plugin authors will follow semantic versioning conventions.

## Out of Scope

- Plugin marketplace or online distribution system.
- Remote plugin loading (all plugins must be locally installed).
- GUI for plugin management (CLI only in this feature).
- Hot-reloading of plugins (requires application restart).
- Plugin sandboxing or security isolation (plugins run with full application permissions).
- Inter-plugin communication or dependency injection between plugins.
- Plugin configuration UI (plugins use config files or environment variables).
- Automatic plugin updates.
