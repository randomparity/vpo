# Research: Settings/About Panel for Web UI

**Feature**: 014-settings-about-panel
**Date**: 2025-11-23

## Research Tasks

### 1. How to retrieve version information at runtime

**Decision**: Use existing `__version__` from package `__init__.py`

**Rationale**: The codebase already exposes `__version__ = "0.1.0"` in `src/vpo/__init__.py`. The health endpoint in `server/app.py` already imports and uses this value. For git commit hash, we can optionally read from a generated file or environment variable if available, with fallback to "unavailable".

**Alternatives considered**:
- `pkg_resources` / `importlib.metadata`: More complex, not needed since `__version__` is directly accessible
- Git subprocess at runtime: Adds external dependency, may not work in packaged distributions

### 2. How to retrieve current profile information

**Decision**: Access profile from application context or environment

**Rationale**: The daemon `serve` command can optionally accept a `--profile` flag. The profile name (if any) should be stored in the app context at startup and retrieved by the About page. If no profile is active, display "Default".

**Alternatives considered**:
- Read from filesystem on each request: Inefficient, profile is set at startup
- Global variable: Less testable than app context

### 3. How to determine the API base URL

**Decision**: Construct from request context (host/scheme) or use configured value

**Rationale**: The request object provides host and scheme information. For user display, showing the URL they're currently connected to is most useful. Can also read from config if an explicit external URL is configured.

**Alternatives considered**:
- Hardcoded value: Violates Configuration as Data principle
- Environment variable only: Less flexible than request context

### 4. Integration with existing navigation structure

**Decision**: Add "About" to `NAVIGATION_ITEMS` list in `server/ui/models.py`

**Rationale**: The existing navigation system uses a simple list of `NavigationItem` dataclasses. Adding a new item follows the established pattern exactly. The template (`base.html`) iterates over this list automatically.

**Alternatives considered**:
- Separate footer link: Less discoverable, inconsistent with other sections
- Settings modal: Overcomplicated for read-only info

### 5. Documentation links to include

**Decision**: Link to GitHub repository README and docs folder

**Rationale**: The project has documentation in `/docs/` and a README.md at root. Link to the GitHub-hosted versions for easy access. Use relative links where possible for local development.

**Alternatives considered**:
- Hosted docs site: Not currently available
- Inline documentation: Would bloat the About page

## Technical Findings

### Existing Patterns to Follow

1. **Route handler pattern** (`routes.py`):
   ```python
   async def about_handler(request: web.Request) -> dict:
       return _create_template_context(
           active_id="about",
           section_title="About",
           # Additional context for version, profile, etc.
       )
   ```

2. **Template context extension**: The `TemplateContext` class may need additional fields for about-specific data, or we pass them via `section_content` or a custom template.

3. **Navigation item addition** (`models.py`):
   ```python
   NavigationItem(id="about", label="About", path="/about"),
   ```

### Data to Display

| Field | Source | Fallback |
|-------|--------|----------|
| Version | `vpo.__version__` | "0.1.0" (always available) |
| Git Hash | Environment `VPO_GIT_HASH` or built-in | "unavailable" |
| Profile | App context `app.get("profile")` | "Default" |
| API URL | `request.url.origin()` | Current request URL |
| Docs Link | Hardcoded GitHub URL | Always available |

## Conclusion

No blocking unknowns. All required information is accessible through existing code patterns. Implementation can proceed using:
- Existing navigation/template infrastructure
- Package `__version__` for version info
- App context for profile (set at startup by serve command)
- Request context for API URL
- Static GitHub URLs for documentation
