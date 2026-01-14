# Feature Specification: Polish, Packaging, and Plugin Ecosystem Readiness

**Feature Branch**: `009-polish-packaging-plugins`
**Created**: 2025-11-22
**Status**: Draft
**Input**: User description: "Polish, Packaging, and Plugin Ecosystem Readiness - Make the tool easy to install, document thoroughly, and finalize the plugin ecosystem story."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Package Installation via pip (Priority: P1)

As a user, I want to install the VPO tool via pip so that deployment is simple and follows Python ecosystem conventions.

**Why this priority**: Without proper packaging, users cannot easily install and use the tool. This is the fundamental delivery mechanism for a Python CLI tool.

**Independent Test**: Can be fully tested by running `pip install video-policy-orchestrator` from PyPI (or test PyPI) and verifying the `vpo` command is available and functional.

**Acceptance Scenarios**:

1. **Given** a clean Python 3.10+ environment, **When** user runs `pip install video-policy-orchestrator`, **Then** the package installs successfully with all dependencies
2. **Given** a successfully installed package, **When** user runs `vpo --help`, **Then** the CLI displays available commands and usage information
3. **Given** a successfully installed package, **When** user runs `vpo --version`, **Then** the installed version is displayed
4. **Given** the Rust extension is required, **When** user installs on common platforms (Linux x86_64, macOS arm64/x86_64), **Then** pre-built wheels are available and installation completes without requiring Rust toolchain

---

### User Story 2 - End-to-End Tutorial (Priority: P2)

As a new user, I want a step-by-step tutorial from install through scan, policy creation, to apply, so that I can get value quickly without reading extensive documentation.

**Why this priority**: Once users can install the tool, they need clear guidance to get started. A tutorial accelerates time-to-value and reduces support burden.

**Independent Test**: A new user can follow the tutorial from start to finish and successfully scan a sample video, apply a policy, and see results.

**Acceptance Scenarios**:

1. **Given** a user who has installed the tool, **When** they follow the tutorial, **Then** they can complete each step without additional documentation
2. **Given** the tutorial document, **When** a user reads the scan section, **Then** they understand the command syntax and expected output
3. **Given** the tutorial document, **When** a user reads the policy section, **Then** they can create a basic policy YAML file for common scenarios
4. **Given** the tutorial document, **When** a user reads the apply section, **Then** they understand how to apply policies and interpret results

---

### User Story 3 - Plugin Author Guide (Priority: P3)

As a plugin developer, I want a clear guide and template example so that I can build new functionality without modifying core code.

**Why this priority**: The plugin ecosystem enables community contributions and custom functionality. Clear documentation lowers the barrier to plugin development.

**Independent Test**: A developer can follow the guide to create a working "hello world" plugin that hooks into VPO events.

**Acceptance Scenarios**:

1. **Given** a developer familiar with Python, **When** they read the plugin author guide, **Then** they understand the plugin architecture and available hook points
2. **Given** the plugin template example, **When** a developer copies and modifies it, **Then** they have a functional plugin structure
3. **Given** a completed plugin, **When** the developer tests it locally, **Then** the plugin loads correctly and receives events
4. **Given** the plugin guide, **When** a developer needs to publish their plugin, **Then** they understand packaging and distribution options

---

### User Story 4 - Container Image Installation (Priority: P4)

As a user, I want to install the tool via a container image so that I don't need to manage dependencies like ffmpeg manually.

**Why this priority**: Container deployment simplifies dependency management and provides reproducible environments, but is secondary to native pip installation.

**Independent Test**: Can be fully tested by pulling the container image and running a scan on a mounted volume.

**Acceptance Scenarios**:

1. **Given** a system with Docker or Podman installed, **When** user pulls the VPO container image, **Then** the image downloads successfully
2. **Given** a pulled container image, **When** user runs the container with a video directory mounted, **Then** VPO can scan the mounted files
3. **Given** the container image, **When** user inspects it, **Then** it includes ffmpeg, ffprobe, and mkvtoolnix

---

### User Story 5 - Backlog and Roadmap (Priority: P5)

As a product owner, I want a groomed backlog and roadmap so that future enhancements are clearly staged and community contributors know where to focus.

**Why this priority**: While important for long-term project health, this is administrative work that doesn't block user functionality.

**Independent Test**: Contributors can view the roadmap and understand the project's direction and how to contribute.

**Acceptance Scenarios**:

1. **Given** a potential contributor, **When** they view the GitHub repository, **Then** they can see open issues organized by priority/epic
2. **Given** the README.md, **When** a user reads the Roadmap section, **Then** they understand planned features and project direction
3. **Given** the backlog, **When** a contributor wants to help, **Then** they can identify "good first issue" opportunities

---

### Edge Cases

- What happens when pip install fails due to missing Rust toolchain on an unsupported platform?
- How does the container handle permission issues with mounted volumes?
- What happens when the tutorial sample policy references features not yet released?
- How are plugin version compatibility conflicts handled?
- What happens if a user tries to install on Python < 3.10?

## Requirements *(mandatory)*

### Functional Requirements

**Packaging & Distribution**
- **FR-001**: Package MUST be installable via `pip install video-policy-orchestrator` from PyPI
- **FR-002**: Package MUST include pre-built wheels for common platforms (Linux x86_64, macOS arm64, macOS x86_64); Windows support deferred to future release based on demand
- **FR-003**: Package MUST declare accurate dependencies in metadata for automatic resolution
- **FR-004**: Package MUST include the compiled Rust extension in platform wheels
- **FR-005**: Container image MUST include ffmpeg, ffprobe, and mkvtoolnix pre-installed
- **FR-006**: Container image MUST support mounting external volumes for video file access
- **FR-007**: Container image MUST be published to a public registry (Docker Hub or GitHub Container Registry)

**Documentation**
- **FR-008**: Tutorial document MUST cover installation, scanning, policy creation, and policy application
- **FR-009**: Tutorial MUST include sample commands that users can copy and run
- **FR-010**: Tutorial MUST explain expected output and how to interpret results
- **FR-011**: Plugin author guide MUST document the plugin architecture and available hook points
- **FR-012**: Plugin author guide MUST include a complete "hello world" example
- **FR-013**: Plugin guide MUST explain plugin packaging and distribution

**Project Management**
- **FR-014**: GitHub Issues MUST be organized with labels for epics/milestones
- **FR-015**: README.md MUST include a Roadmap section with future planned features
- **FR-016**: Repository MUST identify "good first issue" opportunities for new contributors

### Key Entities

- **Package Artifact**: The distributable unit (wheel, sdist) containing the VPO code and Rust extension
- **Container Image**: Docker/OCI image with VPO and all external tool dependencies
- **Tutorial Document**: Step-by-step guide in docs/tutorial.md
- **Plugin Author Guide**: Developer documentation in docs/plugin-author-guide.md
- **Plugin Template**: Example code in examples/plugins/hello_world/ demonstrating minimal plugin structure

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can install VPO on supported platforms in under 2 minutes without manual dependency management
- **SC-002**: New users can complete the end-to-end tutorial in under 30 minutes
- **SC-003**: A Python developer can create a working plugin within 1 hour using the guide and template
- **SC-004**: The container image size is under 500MB to enable reasonable download times
- **SC-005**: 100% of documented commands in the tutorial execute successfully on a fresh installation
- **SC-006**: Plugin template passes all linting and type-checking requirements out of the box
- **SC-007**: All roadmap items are linked to GitHub Issues or Discussions for tracking

## Clarifications

### Session 2025-11-22

- Q: What is the Windows platform support scope? → A: Defer Windows from initial scope, add later based on demand
- Q: How should tutorial sample media be provided? → A: Users supply own video files; tutorial specifies format requirements

## Assumptions

- PyPI is the primary distribution channel for the Python package
- GitHub Container Registry (ghcr.io) will be used for container images
- The project already has a working plugin system to document (per existing `src/vpo/plugin/` structure)
- Tutorial will direct users to use their own video files, specifying supported format requirements (MKV, MP4 with multiple tracks recommended)
- Platform wheels will be built using GitHub Actions CI/CD
- The Rust extension build uses maturin which supports wheel building
