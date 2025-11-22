# Quickstart: Audio Transcription & Language Detection

**Feature**: 007-audio-transcription
**Date**: 2025-11-22

## Overview

This quickstart guides you through using VPO's audio transcription feature to detect and correct language tags on audio tracks.

## Prerequisites

1. VPO installed and configured
2. ffmpeg available in PATH (for audio extraction)
3. Whisper plugin installed (for local transcription)

## Installation

### Install Whisper Plugin (Optional Dependency)

```bash
# Install openai-whisper for local transcription
pip install openai-whisper

# Or with GPU support (CUDA)
pip install openai-whisper torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### Verify Installation

```bash
vpo doctor
# Should show: Transcription plugin: whisper-local (base model)
```

## Basic Usage

### 1. Detect Language on a Single File

```bash
# Analyze audio tracks and show detected languages
vpo transcribe detect /path/to/movie.mkv

# Output:
# Track 1 (audio, aac):
#   Current language: und
#   Detected language: en (English)
#   Confidence: 94.2%
```

### 2. Update Language Tags

```bash
# Preview changes (dry-run)
vpo transcribe detect --dry-run --update /path/to/movie.mkv

# Apply changes
vpo transcribe detect --update /path/to/movie.mkv
```

### 3. Check Transcription Status

```bash
# Library overview
vpo transcribe status

# Specific file
vpo transcribe status /path/to/movie.mkv
```

## Policy-Based Workflow

### 1. Create a Transcription Policy

```yaml
# transcription-policy.yaml
name: auto-language-detection
version: 1

audio:
  transcription:
    enabled: true
    update_language_from_transcription: true
    confidence_threshold: 0.85
    detect_commentary: true
    reorder_commentary: true
```

### 2. Preview Policy Application

```bash
vpo apply --policy transcription-policy.yaml --dry-run /path/to/movie.mkv
```

### 3. Apply to Library

```bash
# Apply to all files in directory
vpo apply --policy transcription-policy.yaml /path/to/movies/
```

## Configuration

### Global Settings

Add to `~/.vpo/config.yaml`:

```yaml
transcription:
  plugin: whisper-local
  model_size: base          # Options: tiny, base, small, medium, large
  sample_duration: 60       # Seconds to sample (0 = full track)
  gpu_enabled: true
```

### Model Size Guide

| Model | RAM | Speed | Accuracy | Best For |
|-------|-----|-------|----------|----------|
| tiny | ~1GB | Fastest | ~70% | Quick scanning, low resources |
| base | ~1.5GB | Fast | ~80% | **Default - good balance** |
| small | ~2.5GB | Medium | ~85% | Higher accuracy needs |
| medium | ~5GB | Slow | ~90% | GPU recommended |
| large | ~10GB | Slowest | ~95% | Maximum accuracy, GPU required |

## Common Workflows

### Fix Undefined Language Tags

```bash
# Find files with undefined audio languages
vpo inspect --json /path/to/library | jq '.[] | select(.tracks[].language == "und")'

# Run language detection on those files
vpo transcribe detect --update /path/to/library/
```

### Identify Commentary Tracks

```bash
# Create policy for commentary detection
cat > commentary-policy.yaml << EOF
audio:
  transcription:
    enabled: true
    detect_commentary: true
    reorder_commentary: true
EOF

# Apply to library
vpo apply --policy commentary-policy.yaml /path/to/library/
```

### Batch Processing with Confidence Threshold

```bash
# Only update when very confident (90%+)
vpo transcribe detect --update --threshold 0.9 /path/to/library/
```

## Troubleshooting

### "Transcription plugin not available"

```bash
# Check if Whisper is installed
python -c "import whisper; print(whisper.__version__)"

# If not, install it
pip install openai-whisper
```

### Low Confidence Scores

- Try a larger model: `model_size: small` or `model_size: medium`
- Increase sample duration: `sample_duration: 120`
- Check audio quality (very noisy audio may not be detectable)

### Slow Performance

- Use GPU if available: `gpu_enabled: true`
- Use smaller model: `model_size: tiny`
- Reduce sample duration: `sample_duration: 30`

### Clear and Re-detect

```bash
# Clear existing results
vpo transcribe clear /path/to/movie.mkv

# Re-run detection
vpo transcribe detect --update /path/to/movie.mkv
```

## Next Steps

- Read the [TranscriptionPlugin Protocol](contracts/transcription-plugin.md) to create custom plugins
- See the [CLI Reference](contracts/cli-transcribe.md) for all command options
- Review the [Data Model](data-model.md) for database schema details
