# Glossary

**Purpose:**
Definitions of key terms, codecs, and technical terminology used throughout VPO documentation and codebase. This guide helps novices understand media processing concepts.

**Contents:**
- [VPO Concepts](#vpo-concepts)
- [Video Codecs](#video-codecs)
- [Audio Codecs](#audio-codecs)
- [Subtitle Codecs](#subtitle-codecs)
- [Video Processing Terms](#video-processing-terms)
- [Audio Processing Terms](#audio-processing-terms)
- [Container & Muxing Terms](#container--muxing-terms)
- [External Tools](#external-tools)
- [Hardware Acceleration](#hardware-acceleration)
- [Abbreviations](#abbreviations)

---

## VPO Concepts

### Container Format

The file format that holds video, audio, and subtitle tracks together. Examples include Matroska (`.mkv`), MP4 (`.mp4`), and AVI (`.avi`). VPO extracts this information via ffprobe.

### Content Hash

A partial hash computed from the first and last 64KB of a file, combined with file size. Used for efficient change detection without hashing entire files. Format: `xxh64:<head_hash>:<tail_hash>:<file_size>`.

### Dry Run

A mode where VPO simulates operations without making actual changes. Use `--dry-run` with scan commands to preview what would happen.

### Introspection

The process of examining a media file to extract metadata about its container format and tracks. Performed by the Media Introspector component using ffprobe.

### Job

A long-running operation such as transcoding or batch file processing. Jobs can be queued, monitored, and cancelled.

### Media Item

A single video file in the library, represented in the database with its path, size, timestamps, and associated tracks.

### Plugin

An extension module that adds functionality to VPO. Plugin types include:
- **Analyzer plugins:** Add metadata, perform checks, tag content
- **Mutator plugins:** Modify containers, rewrite metadata, move files
- **Transcription plugins:** Speech-to-text, language detection

### Policy

A set of rules defining how a video library should be organized. Policies specify track ordering preferences, default track selection, naming conventions, and transformation rules.

### Scan

The process of discovering video files in directories, computing content hashes, and storing metadata in the database. Scans are incremental—unchanged files are skipped.

### Scan Run

A single execution of the scan command, which processes one or more directories and records results in the database.

### Track

A single stream within a media file. Track types include:
- **video:** Video streams (H.264, HEVC, AV1, etc.)
- **audio:** Audio streams (AAC, Opus, DTS, etc.)
- **subtitle:** Text or image-based subtitles (SRT, ASS, PGS, etc.)
- **attachment:** Embedded files like fonts

### Track Index

The zero-based position of a track within a media file. Used to identify specific tracks when applying policies.

### Track Flags

Boolean properties on tracks:
- **default:** The track selected by default on playback
- **forced:** The track shown regardless of user preference (e.g., foreign language dialogue)

---

## Video Codecs

Video codecs compress and decompress video data. VPO uses alias matching, so any of the listed aliases will match.

| Codec | Aliases | Description |
|-------|---------|-------------|
| **H.264/AVC** | h264, h.264, avc, avc1, x264 | The most widely compatible video codec. Best choice for maximum device support. Larger files than HEVC. |
| **HEVC/H.265** | hevc, h265, h.265, x265, hvc1, hev1 | High Efficiency Video Coding. ~50% smaller files than H.264 at same quality. Good modern device support. |
| **VP9** | vp9, vp09 | Google's royalty-free codec. Common for YouTube/web delivery. Good compression. |
| **AV1** | av1, av01, libaom-av1 | Newest codec with best compression (~30% smaller than HEVC). Royalty-free. Slower to encode. |
| **MPEG-4 Part 2** | mpeg4, mp4v | Legacy codec. Rarely used for new content. |

**MP4-compatible video codecs:** h264, avc, avc1, hevc, h265, hvc1, hev1, av1, av01, mpeg4, mp4v, vp9

---

## Audio Codecs

Audio codecs compress and decompress audio data. Lossless codecs preserve perfect quality; lossy codecs achieve smaller files with some quality loss.

| Codec | Aliases | Type | MP4 Compatible | Description |
|-------|---------|------|----------------|-------------|
| **AAC** | aac, aac_latm, mp4a | Lossy | Yes | Standard lossy codec for MP4. Good quality at 128-256 kbps. |
| **AC3 (Dolby Digital)** | ac3, ac-3, a52 | Lossy | Yes | Standard for DVD surround sound. Max 640 kbps. |
| **EAC3 (Dolby Digital Plus)** | eac3, e-ac-3, ec3 | Lossy | Yes | Enhanced AC3 with higher bitrates and object audio support. |
| **TrueHD** | truehd, mlp | Lossless | No | Dolby's lossless codec for Blu-ray. Preserves master audio quality. |
| **DTS** | dts, dca | Lossy | No | Competing surround format to AC3. Common on DVDs. |
| **DTS-HD MA** | dts-hd ma, dts-hd, dtshd, dts_hd, dts-hd.ma | Lossless | No | DTS lossless codec for Blu-ray. Master Audio quality. |
| **FLAC** | flac | Lossless | Limited | Free Lossless Audio Codec. Open-source, widely supported. |
| **Opus** | opus | Lossy | Yes | Modern codec with excellent quality at low bitrates. Best for voice/streaming. |
| **MP3** | mp3, mp3float | Lossy | Yes | Legacy codec. Widely compatible but superseded by AAC/Opus. |
| **Vorbis** | vorbis | Lossy | No | Open-source lossy codec. Common in WebM/OGG containers. |
| **ALAC** | alac | Lossless | Yes | Apple Lossless. Native Apple device support. |
| **PCM** | pcm, pcm_s16le, pcm_s24le, pcm_s32le, pcm_f32le | Uncompressed | No | Uncompressed audio. Large files, perfect quality. |

**Notes:**
- TrueHD and DTS-HD MA require MKV container (not MP4 compatible)
- VPO defaults to transcoding incompatible codecs to AAC when converting to MP4

---

## Subtitle Codecs

Subtitle codecs store text or images for displaying captions and translations.

| Codec | Aliases | Type | MP4 Compatible | Description |
|-------|---------|------|----------------|-------------|
| **SubRip/SRT** | subrip, srt | Text | Needs conversion | Simple text format with timestamps. Most common format. |
| **ASS/SSA** | ass, ssa | Styled text | No | Advanced SubStation Alpha. Supports fonts, colors, positioning. |
| **PGS** | hdmv_pgs_subtitle, pgssub, pgs | Bitmap | No | Blu-ray presentation graphics. Image-based subtitles. |
| **VobSub** | dvd_subtitle, dvdsub, vobsub | Bitmap | No | DVD subtitles. Image-based, cannot be converted to text. |
| **mov_text** | mov_text, tx3g | Text | Yes | Native MP4 text subtitle format. |
| **WebVTT** | webvtt | Text | Yes | Web Video Text Tracks. Used for HTML5 video. |

**Notes:**
- Text-based subtitles (SRT, ASS) can be converted to mov_text for MP4
- Bitmap subtitles (PGS, VobSub) cannot be converted to text without OCR
- MKV container accepts all subtitle formats

---

## Video Processing Terms

### Bitrate

The amount of data used per second of video. Measured in Mbps (megabits per second) or kbps (kilobits per second). Higher bitrate = larger file, potentially better quality.

### CRF (Constant Rate Factor)

A quality-based encoding mode that produces variable bitrate output. Lower CRF = better quality, larger file.

| Codec | Default CRF | Range | Notes |
|-------|-------------|-------|-------|
| H.264 | 23 | 0-51 | 18-23 is visually lossless range |
| HEVC | 28 | 0-51 | ~23-28 is visually lossless range |
| VP9 | 31 | 0-63 | Higher values than x264/x265 |
| AV1 | 30 | 0-63 | Similar scale to VP9 |

### HDR (High Dynamic Range)

Extended brightness and color range beyond standard video. Includes formats like HDR10, Dolby Vision, and HLG. Requires compatible display.

### Preset

Controls encoding speed vs compression efficiency tradeoff. From fastest to slowest:
`ultrafast`, `superfast`, `veryfast`, `faster`, `fast`, `medium`, `slow`, `slower`, `veryslow`

Slower presets produce smaller files at the same quality but take longer to encode.

### Resolution

Video dimensions in pixels. Common presets:

| Preset | Dimensions | Common Name |
|--------|------------|-------------|
| 480p | 854×480 | SD |
| 720p | 1280×720 | HD |
| 1080p | 1920×1080 | Full HD |
| 1440p | 2560×1440 | 2K / QHD |
| 4K | 3840×2160 | Ultra HD |
| 8K | 7680×4320 | 8K UHD |

### Scaling

Reducing video resolution to decrease file size. VPO supports these algorithms:
- **lanczos**: Best quality for downscaling (default)
- **bicubic**: Good quality, faster than lanczos
- **bilinear**: Fast, acceptable quality

### Tune

Content-specific optimization for encoders:
- **film**: Live-action content with natural grain
- **animation**: Flat colors, sharp edges
- **grain**: Preserves film grain
- **stillimage**: Slide shows, static content
- **fastdecode**: Optimizes for playback speed
- **zerolatency**: Live streaming, minimal delay

### VFR (Variable Frame Rate)

Video with non-constant frame timing. Common in screen recordings and some cameras. Can cause audio sync issues during transcoding.

---

## Audio Processing Terms

### Channel Layout

Arrangement of audio channels for playback:
- **Mono**: 1 channel (center)
- **Stereo**: 2 channels (left, right)
- **5.1 Surround**: 6 channels (front L/R, center, rear L/R, LFE subwoofer)
- **7.1 Surround**: 8 channels (5.1 + side L/R)

### Downmix

Converting multi-channel audio to fewer channels (e.g., 5.1 → stereo). VPO can create downmixed tracks while preserving original surround tracks.

### Lossless vs Lossy

- **Lossless**: Perfect copy of original (TrueHD, DTS-HD MA, FLAC, ALAC, PCM)
- **Lossy**: Some quality loss for smaller size (AAC, AC3, MP3, Opus)

### Passthrough / Stream Copy

Copying audio without re-encoding. Preserves original quality and is very fast. Use when codec is already compatible with target container.

---

## Container & Muxing Terms

### Demuxing

Separating tracks from a container into individual streams. Opposite of muxing.

### MKV / Matroska

A flexible, open-standard container format that can hold unlimited video, audio, subtitle, and attachment tracks. VPO has enhanced support for MKV files.

### Muxing

Combining multiple tracks (video, audio, subtitles) into a single container file. Does not re-encode content.

### Remuxing

Copying tracks from one container to another without re-encoding. Fast operation that preserves quality. Example: MKV → MP4 (if codecs are compatible).

### Stream Mapping

Specifying which input tracks to include in output. Used in FFmpeg to select specific streams.

---

## External Tools

### ffmpeg

A powerful command-line tool for video/audio transcoding, muxing, and filtering. VPO uses ffmpeg for transcoding and metadata editing.

### ffprobe

A command-line tool (part of ffmpeg) that analyzes media files and outputs detailed stream information. VPO uses ffprobe to extract track metadata.

### mkvmerge

A tool from MKVToolNix for creating Matroska files by combining tracks from multiple sources. VPO uses mkvmerge for MKV-specific operations.

### mkvpropedit

A tool from MKVToolNix for editing Matroska file properties without remuxing. VPO uses mkvpropedit for fast metadata edits.

---

## Hardware Acceleration

Hardware encoders use dedicated GPU silicon for video encoding, providing faster speeds with some quality tradeoff compared to software encoders.

### NVENC

NVIDIA GPU hardware encoder. Available on GeForce GTX/RTX and Quadro cards. Supports H.264, HEVC, and AV1 (RTX 40 series+).

### QSV (Quick Sync Video)

Intel integrated GPU hardware encoder. Available on Intel CPUs with integrated graphics. Supports H.264, HEVC, and AV1 (Arc/newer).

### VAAPI (Video Acceleration API)

Linux video acceleration framework. Works with Intel, AMD, and some NVIDIA GPUs on Linux. VPO uses VAAPI as fallback on Linux systems.

**VPO encoder priority:** NVENC → QSV → VAAPI → Software (CPU)

---

## Abbreviations

| Abbreviation | Meaning |
|--------------|---------|
| AAC | Advanced Audio Coding |
| AC3 | Audio Codec 3 (Dolby Digital) |
| ADR | Architecture Decision Record |
| AV1 | AOMedia Video 1 |
| AVC | Advanced Video Coding (H.264) |
| CLI | Command-Line Interface |
| CRF | Constant Rate Factor |
| DAR | Display Aspect Ratio |
| DB | Database |
| DTS | Digital Theater Systems |
| EAC3 | Enhanced AC3 (Dolby Digital Plus) |
| ER | Entity-Relationship (diagram) |
| FK | Foreign Key |
| FLAC | Free Lossless Audio Codec |
| HDR | High Dynamic Range |
| HEVC | High Efficiency Video Coding (H.265) |
| JSON | JavaScript Object Notation |
| LFE | Low-Frequency Effects (subwoofer channel) |
| MA | Master Audio (DTS-HD MA) |
| MKV | Matroska Video |
| NVENC | NVIDIA Encoder |
| PAR | Pixel Aspect Ratio |
| PCM | Pulse Code Modulation |
| PGS | Presentation Graphic Stream |
| PK | Primary Key |
| QSV | Quick Sync Video |
| SAR | Sample Aspect Ratio |
| SDR | Standard Dynamic Range |
| SRT | SubRip Text |
| SSA | SubStation Alpha |
| UTC | Coordinated Universal Time |
| VAAPI | Video Acceleration API |
| VFR | Variable Frame Rate |
| VPO | Video Policy Orchestrator |
| YAML | YAML Ain't Markup Language |

---

## Related docs

- [Documentation Index](INDEX.md)
- [Data Model](overview/data-model.md)
- [Architecture Overview](overview/architecture.md)
- [Transcode Policy Guide](usage/transcode-policy.md)
