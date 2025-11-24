# Quickstart: Library Filters and Search

**Feature**: 019-library-filters-search
**Prerequisites**: VPO daemon running (`vpo serve`)

## Quick Test

1. **Start the daemon** (if not running):
   ```bash
   uv run vpo serve --port 8080
   ```

2. **Open Library view**:
   ```
   http://localhost:8080/library
   ```

3. **Test text search**:
   - Type a filename or title fragment in the search box
   - Results filter as you type (with 300ms debounce)

4. **Test resolution filter**:
   - Select "1080p" from the Resolution dropdown
   - Table shows only files with 1080p video

5. **Test audio language filter**:
   - Select one or more languages from the Audio dropdown
   - Files with any selected language are shown

6. **Test subtitle filter**:
   - Select "Has subtitles" from the Subtitles dropdown
   - Only files with subtitle tracks are shown

7. **Test "Clear filters"**:
   - Apply multiple filters
   - Click "Clear filters" button
   - All filters reset, full library displayed

8. **Test URL sharing**:
   - Apply filters
   - Copy the URL (includes query parameters)
   - Open in new tab/share with others
   - Filters are restored from URL

## Development Commands

```bash
# Run tests
uv run pytest tests/unit/server/ui/test_models.py -v
uv run pytest tests/integration/server/test_library_api.py -v

# Start daemon with auto-reload (development)
uv run vpo serve --port 8080 --reload

# Lint
uv run ruff check src/video_policy_orchestrator/server/
uv run ruff format src/video_policy_orchestrator/server/
```

## Key Files

| File | Purpose |
|------|---------|
| `server/ui/models.py` | LibraryFilterParams, LibraryContext extensions |
| `server/ui/routes.py` | API handler for /api/library |
| `db/models.py` | get_files_filtered() SQL query |
| `server/ui/templates/sections/library.html` | Filter controls HTML |
| `server/static/js/library.js` | Filter logic, debounce, URL sync |

## Testing Checklist

- [ ] Search finds files by filename
- [ ] Search finds files by title
- [ ] Search is case-insensitive
- [ ] Resolution filter works for each category
- [ ] Audio language multi-select uses OR logic
- [ ] Subtitle presence filter works both ways
- [ ] Filters combine correctly (AND across filters)
- [ ] Pagination resets on filter change
- [ ] URL reflects current filter state
- [ ] Loading from URL restores filters
- [ ] Empty state shows when no matches
- [ ] "Clear filters" resets all filters
