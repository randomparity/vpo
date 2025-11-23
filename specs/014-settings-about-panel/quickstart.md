# Quickstart: Settings/About Panel

**Feature**: 014-settings-about-panel

## Prerequisites

- VPO development environment set up
- Daemon server running (`uv run vpo serve`)
- Web browser

## Quick Test

1. Start the daemon:
   ```bash
   uv run vpo serve
   ```

2. Open browser to: http://localhost:8080/about

3. Verify:
   - "About" link appears in navigation sidebar
   - Page shows version information
   - Page shows API URL
   - Page shows profile name (or "Default")
   - Documentation link works
   - Read-only indicator is visible

## API Testing

```bash
# Get about info as JSON
curl http://localhost:8080/api/about

# Expected response:
# {
#   "version": "0.1.0",
#   "git_hash": null,
#   "profile_name": "Default",
#   "api_url": "http://localhost:8080",
#   "docs_url": "https://github.com/randomparity/vpo/tree/main/docs",
#   "is_read_only": true
# }
```

## Running Tests

```bash
# Run About page tests
uv run pytest tests/unit/server/ui/test_about_routes.py -v

# Run all UI tests
uv run pytest tests/unit/server/ui/ -v
```

## Files Modified

| File | Change |
|------|--------|
| `server/ui/models.py` | Add "About" NavigationItem |
| `server/ui/routes.py` | Add about_handler and route |
| `server/app.py` | Add /api/about endpoint |
| `server/ui/templates/sections/about.html` | New template |
| `tests/unit/server/ui/test_about_routes.py` | New tests |

## Verification Checklist

- [ ] Navigation shows "About" link
- [ ] Clicking "About" loads the About page
- [ ] Version is displayed correctly
- [ ] Profile shows "Default" when no profile configured
- [ ] API URL matches current connection
- [ ] Documentation link opens GitHub docs
- [ ] Read-only notice is visible
- [ ] `/api/about` returns JSON response
