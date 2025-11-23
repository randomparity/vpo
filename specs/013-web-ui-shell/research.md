# Research: Web UI Shell with Global Navigation

**Feature**: 013-web-ui-shell
**Date**: 2025-11-23

## Research Questions

### Q1: HTML Templating Approach for aiohttp

**Decision**: Use aiohttp-jinja2 with Jinja2 templates

**Rationale**:
- aiohttp-jinja2 is the standard templating integration for aiohttp
- Jinja2 is mature, well-documented, and widely used in Python web development
- Server-side rendering ensures fast initial page loads and SEO-friendliness
- Template inheritance (base.html) provides clean layout management
- No build step required (unlike React, Vue, etc.)

**Alternatives Considered**:
1. **Raw string templates**: Too error-prone, no escaping, poor maintainability
2. **Mako templates**: Less common, team familiarity with Jinja2 likely higher
3. **React/Vue SPA**: Overkill for operator dashboard, adds build complexity, increases bundle size
4. **HTMX**: Good for progressive enhancement but adds dependency for minimal benefit in this shell

**Implementation**: Add `aiohttp-jinja2>=1.6` and `jinja2>=3.1` to dependencies

---

### Q2: CSS Approach for Responsive Layout

**Decision**: Custom CSS with CSS Grid/Flexbox, no framework

**Rationale**:
- Minimal CSS footprint for a simple 5-section navigation shell
- CSS Grid handles the layout natively (sidebar + content or header + content)
- No external dependencies to manage or update
- Full control over styling and responsive breakpoints
- Avoids framework bloat (Bootstrap, Tailwind) for minimal UI

**Alternatives Considered**:
1. **Bootstrap**: Heavy (>200KB), overkill for navigation shell
2. **Tailwind CSS**: Requires build step, utility classes clutter templates
3. **PicoCSS/MVP.css**: Lightweight but may conflict with future feature styling
4. **Bulma**: Medium weight, still more than needed

**Implementation**: Single `main.css` file with:
- CSS custom properties for theming
- CSS Grid for layout
- Media queries at 768px and 1024px breakpoints
- BEM-style class naming for maintainability

---

### Q3: Navigation Position (Top vs Sidebar)

**Decision**: Left sidebar navigation

**Rationale**:
- Sidebar provides consistent vertical space for navigation labels
- Easier to add more sections in the future without horizontal crowding
- Common pattern for admin/operator dashboards (GitHub, AWS Console, etc.)
- Content area can use full horizontal width
- Mobile/tablet: sidebar collapses but remains accessible

**Alternatives Considered**:
1. **Top navigation**: Horizontal space limited, harder to scale
2. **Hamburger menu**: Hidden by default, reduces discoverability

**Implementation**:
- Fixed-width sidebar (200-240px) on desktop
- Collapsible sidebar on tablet (768-1024px)
- Navigation links with icons (optional) and text labels

---

### Q4: Client-Side Navigation Enhancement

**Decision**: Minimal vanilla JavaScript for active state, no SPA routing

**Rationale**:
- Server-rendered pages are simple and fast
- JavaScript only needed to highlight current section based on URL
- Avoid adding complexity of client-side routing (History API, state management)
- Each section is a separate URL for bookmarkability and browser history support

**Alternatives Considered**:
1. **Full SPA with client routing**: Unnecessary complexity for placeholder pages
2. **HTMX for partial updates**: Adds dependency, benefits unclear for static placeholders
3. **No JavaScript**: Would work, but loses some UX polish (smooth transitions)

**Implementation**: Single `nav.js` file (~30 lines):
- Detect current path on page load
- Apply `.active` class to matching nav link
- Optional: smooth scroll behavior, transitions

---

### Q5: Static File Serving Strategy

**Decision**: Serve static files via aiohttp's built-in static file support

**Rationale**:
- aiohttp has native `add_static()` route handler
- No need for external static file server (nginx) during development
- Production can optionally front with nginx/CDN but same code works
- Static files co-located with source for easy packaging

**Alternatives Considered**:
1. **Separate static server**: Adds deployment complexity
2. **Embed in Python package**: Harder to modify, cache busting issues
3. **CDN-only**: Requires external infrastructure

**Implementation**:
- `app.router.add_static('/static', static_path)` in app setup
- Static files at `src/video_policy_orchestrator/server/static/`
- Templates reference `/static/css/main.css`, `/static/js/nav.js`

---

### Q6: Error Handling for Unknown Routes

**Decision**: Custom 404 page with navigation, redirect root to /jobs

**Rationale**:
- Unknown routes should show friendly error, not raw aiohttp error
- Keep navigation visible so users can recover
- Root URL (`/`) redirects to Jobs (default section per spec)

**Alternatives Considered**:
1. **JSON error response**: Not user-friendly for browser access
2. **Generic aiohttp 404**: No navigation, dead end

**Implementation**:
- Custom middleware for 404 handling
- 404 template extends base.html (keeps nav)
- Root route (`/`) returns HTTP 302 redirect to `/jobs`

---

## Dependency Changes

### New Dependencies (pyproject.toml)

```toml
dependencies = [
    # ... existing ...
    "aiohttp-jinja2>=1.6",
    "jinja2>=3.1",
]
```

### Rationale

- `aiohttp-jinja2`: Integrates Jinja2 with aiohttp, provides `@aiohttp_jinja2.template` decorator
- `jinja2`: Templating engine (already a transitive dependency of aiohttp-jinja2 but explicit is better)

---

## Key Implementation Patterns

### Template Inheritance

```
base.html (nav + layout)
  └── sections/jobs.html (extends base)
  └── sections/library.html (extends base)
  └── ...
  └── errors/404.html (extends base)
```

### Route Structure

| Path | Handler | Description |
|------|---------|-------------|
| `/` | `root_redirect` | 302 redirect to `/jobs` |
| `/jobs` | `section_handler("jobs")` | Jobs section |
| `/library` | `section_handler("library")` | Library section |
| `/transcriptions` | `section_handler("transcriptions")` | Transcriptions section |
| `/policies` | `section_handler("policies")` | Policies section |
| `/approvals` | `section_handler("approvals")` | Approvals section |
| `/static/{path}` | Static handler | CSS, JS, images |
| `/health` | Existing | Health check (API) |

### CSS Layout Grid

```css
.app-shell {
  display: grid;
  grid-template-columns: 240px 1fr;
  min-height: 100vh;
}

@media (max-width: 1023px) {
  .app-shell {
    grid-template-columns: 200px 1fr;
  }
}

@media (max-width: 767px) {
  /* Below minimum supported - graceful degradation */
  .app-shell {
    grid-template-columns: 1fr;
  }
}
```

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Template changes require server restart | Development mode with auto-reload (aiohttp.web.run_app with reload) |
| Static files cached incorrectly | Add query string versioning or Cache-Control headers |
| CSS conflicts with future features | Use scoped class names, CSS custom properties |
| Navigation order changes | Define nav items in configuration, not hardcoded |

---

## Conclusion

All research questions resolved. No blocking unknowns remain. Ready for Phase 1 design.
