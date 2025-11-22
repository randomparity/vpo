# FFmpeg Container Build

This directory contains a Dockerfile for building a comprehensive FFmpeg installation with extensive codec support, along with wrapper scripts for seamless integration with VPO.

## Features

The container builds FFmpeg from source with:

- **Video codecs**: x264, x265, VP9, AOM-AV1, SVT-AV1, dav1d
- **Audio codecs**: MP3 (LAME), Opus, Vorbis, Speex, AAC (fdk-aac)
- **Filters**: libass subtitles, frei0r, vidstab, placebo
- **Hardware acceleration**: VAAPI, VDPAU, NVENC
- **Quality assessment**: VMAF (Netflix)
- **Streaming**: SRT, RIST, RTMP, SSH

## Container Runtime Support

Both **podman** and **docker** are supported. The Makefile and wrapper scripts automatically detect the available runtime, preferring podman when both are installed.

## Building the Image

```bash
# From repository root
make docker-ffmpeg-build

# Or manually with podman/docker
podman build -t ffmpeg-full docker/ffmpeg/
```

The build takes approximately 30-60 minutes depending on your hardware (uses 8 parallel jobs by default).

## Quick Commands

```bash
# Check ffmpeg version
make docker-ffmpeg-version

# Interactive shell in container
make docker-ffmpeg-shell
```

## Using with VPO

### Method 1: Environment Variables (Recommended)

Set the wrapper scripts as VPO's tool paths:

```bash
# Add to your shell profile (~/.bashrc, ~/.zshrc, etc.)
export VPO_FFMPEG_PATH="/path/to/vpo/docker/ffmpeg/ffmpeg-docker"
export VPO_FFPROBE_PATH="/path/to/vpo/docker/ffmpeg/ffprobe-docker"
```

Verify the configuration:

```bash
vpo doctor --verbose
```

### Method 2: Configuration File

Add to `~/.vpo/config.toml`:

```toml
[tools]
ffmpeg = "/path/to/vpo/docker/ffmpeg/ffmpeg-docker"
ffprobe = "/path/to/vpo/docker/ffmpeg/ffprobe-docker"
```

## Wrapper Scripts

The wrapper scripts (`ffmpeg-docker` and `ffprobe-docker`) handle:

- Container runtime detection (podman preferred)
- Automatic volume mounting for input/output files
- Working directory preservation
- Exit code passthrough

### Direct Usage

```bash
# Run ffprobe on a file
./docker/ffmpeg/ffprobe-docker -v quiet -print_format json -show_streams video.mkv

# Run ffmpeg conversion
./docker/ffmpeg/ffmpeg-docker -i input.mkv -c:v libx265 output.mkv
```

### Custom Image Name

Override the default image name (`ffmpeg-full`) via environment variable:

```bash
export FFMPEG_IMAGE=my-custom-ffmpeg
./docker/ffmpeg/ffmpeg-docker -version
```

## Build Customization

The Dockerfile supports build arguments:

```bash
# Use a specific FFmpeg branch
podman build --build-arg FFMPEG_BRANCH=release/7.0 -t ffmpeg-full docker/ffmpeg/

# Adjust parallel build jobs
podman build --build-arg MAKE_JOBS=4 -t ffmpeg-full docker/ffmpeg/
```

## Troubleshooting

### Image not found

Ensure the image is built first:

```bash
make docker-ffmpeg-build
```

### Permission denied on files

When using podman in rootless mode, ensure your user has access to the files being processed. The wrapper scripts mount directories with the same paths inside the container.

### SELinux issues (Fedora/RHEL)

If you encounter permission errors on SELinux-enabled systems, you may need to add the `:Z` flag to volume mounts. Edit the wrapper scripts to change:

```bash
MOUNT_ARGS+=("-v" "${dir}:${dir}")
```

to:

```bash
MOUNT_ARGS+=("-v" "${dir}:${dir}:Z")
```
