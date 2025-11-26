# Feature Specification: VPO Init Command

**Feature Branch**: `030-init-command`
**Created**: 2025-11-25
**Status**: Draft
**Input**: User description: "Create new init command to initialize vpo - As a user, I want a simple method to initialize directories, appropriate policies, and application configuration TOML files in order to get a quick start using the application."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - First-Time Setup (Priority: P1)

As a new user who has just installed VPO, I want to run a single command that creates all necessary directories, configuration files, and starter policies so I can immediately begin using the application without manually creating files or reading extensive documentation.

**Why this priority**: This is the core value proposition - enabling new users to get started quickly. Without this, users must manually create directories and configuration, which is error-prone and creates friction in adoption.

**Independent Test**: Can be fully tested by running `vpo init` on a system with no existing VPO configuration and verifying all expected files and directories are created with valid content.

**Acceptance Scenarios**:

1. **Given** a system with no existing VPO directory (`~/.vpo` does not exist), **When** the user runs `vpo init`, **Then** the command creates the VPO data directory with default configuration file and starter policy, and displays a success message with next steps.

2. **Given** a system with no existing VPO directory, **When** the user runs `vpo init`, **Then** the created configuration file contains all available settings with sensible defaults and explanatory comments.

3. **Given** a system with no existing VPO directory, **When** the user runs `vpo init`, **Then** a default policy file is created that demonstrates common track ordering and language preferences.

---

### User Story 2 - Safe Re-initialization (Priority: P2)

As a user who already has VPO configured, I want the init command to protect my existing configuration while optionally allowing me to regenerate missing or corrupted files, so I don't accidentally lose my customizations.

**Why this priority**: Protecting user data is critical for trust. Users may accidentally run init or want to restore missing components without losing their work.

**Independent Test**: Can be tested by creating a VPO directory with custom configuration, running `vpo init`, and verifying the existing configuration is preserved.

**Acceptance Scenarios**:

1. **Given** a system with an existing VPO configuration directory, **When** the user runs `vpo init`, **Then** the command detects the existing configuration, displays what already exists, and exits without modifying any files.

2. **Given** a system with an existing VPO configuration directory, **When** the user runs `vpo init --force`, **Then** the command overwrites all configuration files with defaults, displaying a warning about what was replaced.

3. **Given** a system with a VPO directory missing the default policy file but having a valid config.toml, **When** the user runs `vpo init`, **Then** the command reports what exists and what is missing without making changes.

---

### User Story 3 - Custom Data Directory (Priority: P3)

As a user who wants to store VPO data in a non-default location (e.g., on an external drive or in a project-specific directory), I want to specify a custom path during initialization so my data is stored where I need it.

**Why this priority**: Flexibility for advanced users and specific deployment scenarios (NAS, multiple libraries, portable installations).

**Independent Test**: Can be tested by running `vpo init --data-dir /custom/path` and verifying all files are created in the specified location.

**Acceptance Scenarios**:

1. **Given** a user wants to use a custom data directory, **When** the user runs `vpo init --data-dir /custom/path`, **Then** all VPO files are created in the specified directory instead of the default `~/.vpo`.

2. **Given** the specified custom directory does not exist, **When** the user runs `vpo init --data-dir /custom/path`, **Then** the command creates the directory and all necessary subdirectories.

3. **Given** the specified custom directory path is invalid or inaccessible, **When** the user runs `vpo init --data-dir /invalid/path`, **Then** the command displays a clear error message explaining why the directory cannot be used.

---

### Edge Cases

- What happens when the user lacks write permissions to the target directory? The command displays a clear error message explaining the permission issue and suggests running with appropriate permissions.
- What happens when disk space is insufficient? The command fails gracefully with a message about available disk space (initialization requires minimal space, so this is unlikely but should be handled).
- What happens if the user interrupts the command mid-initialization? Partial files may exist; subsequent runs should detect and handle incomplete initialization.
- What happens when `~/.vpo` exists as a file instead of a directory? The command detects this conflict and displays an error message explaining the problem.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST create the VPO data directory (`~/.vpo` by default) if it does not exist.
- **FR-002**: System MUST create a configuration file (`config.toml`) with all available settings documented as comments and sensible default values.
- **FR-003**: System MUST create a `policies/` subdirectory for storing policy files.
- **FR-004**: System MUST create a `plugins/` subdirectory for storing user plugins.
- **FR-005**: System MUST create a default policy file (`policies/default.yaml`) demonstrating track ordering and language preferences.
- **FR-006**: System MUST detect when VPO is already initialized and refuse to overwrite without explicit `--force` flag.
- **FR-007**: System MUST accept a `--data-dir` option to specify an alternative data directory location.
- **FR-008**: System MUST display a summary of what was created and suggest next steps (e.g., "Run `vpo doctor` to verify your setup").
- **FR-009**: System MUST validate that the target directory is writable before attempting to create files.
- **FR-010**: System MUST support a `--dry-run` flag that shows what would be created without actually creating anything.

### Key Entities

- **VPO Data Directory**: The root directory containing all VPO configuration and data (`~/.vpo` by default). Contains configuration file, policies subdirectory, plugins subdirectory, database file (created on first scan), and logs directory.
- **Configuration File**: TOML file (`config.toml`) containing tool paths, behavior settings, server configuration, job settings, and other runtime options.
- **Default Policy**: YAML file (`policies/default.yaml`) providing a starting point for users to understand policy structure and customize for their needs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: New users can complete VPO initialization in under 30 seconds from first command invocation to ready-to-use state.
- **SC-002**: 100% of successful initializations result in a directory structure that passes `vpo doctor` validation.
- **SC-003**: Users can discover and understand all configuration options from the generated config.toml file without consulting external documentation.
- **SC-004**: Re-running init on an already-initialized system produces clear, actionable feedback within 2 seconds.
- **SC-005**: The default policy file enables users to run their first `vpo apply --dry-run` command without modification.

## Assumptions

- The default data directory location follows the existing VPO convention (`~/.vpo`).
- The configuration file format is TOML, consistent with existing VPO configuration.
- Policy files use YAML format, consistent with existing VPO policies.
- The init command will be added to the existing Click-based CLI structure.
- Users have basic familiarity with command-line interfaces.
- The generated configuration file will include all settings currently supported by VPO's configuration system (tools, behavior, server, jobs, plugins, logging, language, etc.).
