# VPO Container Image

This directory contains the Dockerfile for building the Video Policy Orchestrator container image with all dependencies pre-installed.

## Quick Start

```bash
# Pull the image
docker pull ghcr.io/randomparity/vpo:latest

# Scan a video directory
docker run --rm -v ~/Videos:/data ghcr.io/randomparity/vpo:latest scan /data

# Inspect a file
docker run --rm -v ~/Videos:/data ghcr.io/randomparity/vpo:latest inspect /data/movie.mkv

# Check available tools
docker run --rm ghcr.io/randomparity/vpo:latest doctor
```

## Building Locally

```bash
# From repository root
docker build -t vpo:local -f docker/vpo/Dockerfile .

# Test the build
docker run --rm vpo:local --version
docker run --rm vpo:local doctor
```

## Usage

### Volume Mounts

Mount your video directory to `/data` inside the container:

```bash
docker run --rm -v /path/to/videos:/data vpo:latest scan /data
```

### Persisting the Database

By default, the database is stored inside the container and lost when the container exits. To persist it:

```bash
docker run --rm \
  -v /path/to/videos:/data \
  -v ~/.vpo:/home/vpo/.vpo \
  vpo:latest scan /data
```

### Running with Policies

Mount both your videos and policy file:

```bash
docker run --rm \
  -v /path/to/videos:/data \
  -v /path/to/policy.yaml:/policy.yaml:ro \
  vpo:latest apply --policy /policy.yaml /data/movie.mkv --dry-run
```

### Interactive Shell

For debugging or exploration:

```bash
docker run --rm -it --entrypoint /bin/bash vpo:latest
```

## Permissions

The container runs as a non-root user (`vpo`) for security. If you encounter permission errors with mounted volumes:

1. **Linux**: Ensure the mounted directories are readable/writable by UID 1000:
   ```bash
   # Check your UID
   id -u

   # If different from 1000, run with your UID
   docker run --rm --user $(id -u):$(id -g) -v ~/Videos:/data vpo:latest scan /data
   ```

2. **macOS/Windows**: Docker Desktop handles permissions automatically.

## Image Contents

The image includes:

- **Python 3.12** - Runtime environment
- **VPO** - Video Policy Orchestrator CLI
- **FFmpeg** - Media analysis and transcoding (includes ffprobe)
- **MKVToolNix** - MKV container manipulation (mkvmerge, mkvpropedit)

## Size

Target image size: < 500MB

Current size can be checked with:
```bash
docker images ghcr.io/randomparity/vpo:latest --format "{{.Size}}"
```

## Tags

- `latest` - Latest stable release
- `vX.Y.Z` - Specific version (e.g., `v0.1.0`)
- `main` - Built from main branch (may be unstable)

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VPO_LOG_LEVEL` | Log verbosity (debug, info, warning, error) | `info` |
| `VPO_LOG_JSON` | Use JSON log format | `false` |

Example:
```bash
docker run --rm -e VPO_LOG_LEVEL=debug vpo:latest doctor
```

## Troubleshooting

### "Permission denied" errors

See the Permissions section above.

### "No video files found"

Ensure the path inside the container is correct:
```bash
# List files in the mounted volume
docker run --rm -v ~/Videos:/data --entrypoint ls vpo:latest -la /data
```

### Container exits immediately

The container runs VPO commands and exits. Use `-it` for interactive sessions:
```bash
docker run --rm -it --entrypoint /bin/bash vpo:latest
```

## Related Documentation

- [Tutorial](../../docs/tutorial.md) - Getting started with VPO
- [CLI Usage](../../docs/usage/cli-usage.md) - Command reference
- [Configuration](../../docs/usage/configuration.md) - Configuration options
