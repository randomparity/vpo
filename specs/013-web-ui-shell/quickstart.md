# Quickstart: Web UI Shell with Global Navigation

**Feature**: 013-web-ui-shell
**Date**: 2025-11-23

## Prerequisites

- VPO installed with daemon mode (feature 012-daemon-systemd-server)
- Python 3.10+
- Modern web browser (Chrome, Firefox, Safari, Edge)

## Installation

The Web UI is included with VPO. No additional installation required.

If building from source, ensure dependencies are installed:

```bash
uv pip install -e ".[dev]"
```

## Starting the Web UI

Start the VPO daemon server:

```bash
vpo serve
```

By default, the server binds to `127.0.0.1:8321`.

## Accessing the Web UI

Open your browser and navigate to:

```
http://localhost:8321/
```

You will be redirected to the Jobs section (`/jobs`).

## Navigation

The sidebar provides links to all sections:

| Section | URL | Description |
|---------|-----|-------------|
| Jobs | `/jobs` | View and manage processing jobs |
| Library | `/library` | Browse media library |
| Transcriptions | `/transcriptions` | View transcription results |
| Policies | `/policies` | Manage policies |
| Approvals | `/approvals` | Review pending approvals |

Click any link to navigate. The current section is highlighted.

## Configuration

### Custom Port

```bash
vpo serve --port 9000
```

Access UI at `http://localhost:9000/`

### Network Access

To allow access from other machines:

```bash
vpo serve --bind 0.0.0.0 --port 8321
```

**Warning**: Only bind to `0.0.0.0` on trusted networks. No authentication is implemented.

## Responsive Behavior

The UI is designed for:
- **Desktop** (1024px+): Full sidebar visible
- **Tablet** (768-1023px): Compact sidebar
- **Below 768px**: Graceful degradation (not optimized)

## Troubleshooting

### UI Not Loading

1. Verify server is running: `curl http://localhost:8321/health`
2. Check server logs for errors
3. Ensure port is not blocked by firewall

### CSS/JS Not Loading

1. Check browser developer console for 404 errors
2. Verify static files exist in installation
3. Clear browser cache

### Navigation Not Highlighting

1. Ensure JavaScript is enabled
2. Check browser console for JS errors

## Development

For template development, restart the server after changes:

```bash
# Make template changes
# Restart server
vpo serve
```

## Next Steps

This shell provides placeholder content. Full functionality will be added in future features:
- Jobs: Job queue management
- Library: Media file browser
- Transcriptions: Transcription viewer
- Policies: Policy editor
- Approvals: Approval workflow
