# Feature Specification: Conditional Video Transcoding

**Feature Branch**: `034-conditional-video-transcode`
**Created**: 2025-11-26
**Status**: Draft
**Input**: Sprint 4 - Conditional Video Transcoding with skip conditions and user-configurable quality settings

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Skip Transcoding for Compliant Files (Priority: P1)

As a storage optimizer, I want to skip re-encoding files that are already HEVC at acceptable quality so that I save time and avoid unnecessary quality loss.

**Why this priority**: This is the core value proposition - preventing wasteful re-encoding saves significant time and preserves quality. Without skip logic, users would needlessly re-encode already-optimal files.

**Independent Test**: Can be fully tested by applying a transcode policy to an already-HEVC file and verifying it's skipped, delivering immediate value by avoiding unnecessary work.

**Acceptance Scenarios**:

1. **Given** a video file already encoded in HEVC, **When** I apply a transcode policy targeting HEVC with skip conditions for HEVC codec, **Then** the system reports "Skipping video transcode - already compliant" and no transcoding occurs.

2. **Given** a video file in H.264 at 1080p, **When** I apply a transcode policy targeting HEVC with skip conditions for HEVC codec, **Then** the file is transcoded to HEVC because it doesn't match the skip condition.

3. **Given** a 4K HEVC file, **When** I apply a transcode policy with skip_if requiring resolution_within 1080p, **Then** the file is transcoded because it exceeds the resolution threshold despite matching the codec.

4. **Given** a 1080p HEVC file at 15 Mbps, **When** I apply a transcode policy with skip_if requiring bitrate_under 10M, **Then** the file is transcoded because bitrate exceeds the threshold.

5. **Given** multiple skip conditions (codec, resolution, bitrate), **When** a file matches some but not all conditions, **Then** the file is transcoded (AND logic requires all conditions to be true).

---

### User Story 2 - Configure CRF Quality Settings (Priority: P1)

As a quality-conscious user, I want to set CRF values so that I control the quality/size tradeoff precisely.

**Why this priority**: CRF is the primary quality control mechanism for modern video encoding. Users need fine-grained control over the quality/size tradeoff for their specific needs.

**Independent Test**: Can be fully tested by transcoding a sample file with a specific CRF value and verifying the output quality/size characteristics match expectations.

**Acceptance Scenarios**:

1. **Given** a policy with `quality.mode: crf` and `quality.crf: 20`, **When** I transcode a video file, **Then** the encoder uses CRF 20 for quality targeting.

2. **Given** a policy with CRF value outside valid range (e.g., 52 or -1), **When** I validate the policy, **Then** validation fails with a clear error message about invalid CRF range.

3. **Given** a policy with CRF mode but no explicit CRF value, **When** I apply the policy to an HEVC target, **Then** the system uses codec-appropriate default (28 for x265).

---

### User Story 3 - Select Encoding Preset (Priority: P2)

As a user balancing speed and compression, I want to select encoding presets so that I can choose between fast encoding or better compression.

**Why this priority**: Presets significantly impact encoding time and file size. Users need control over this tradeoff based on their hardware and time constraints.

**Independent Test**: Can be fully tested by transcoding the same source with different presets and measuring encoding time and output size differences.

**Acceptance Scenarios**:

1. **Given** a policy with `quality.preset: slow`, **When** I transcode a video file, **Then** the encoder uses the slow preset for better compression.

2. **Given** a policy with no preset specified, **When** I transcode a video file, **Then** the encoder uses the "medium" preset as default.

3. **Given** a policy with an invalid preset name, **When** I validate the policy, **Then** validation fails with a list of valid presets for the target codec.

---

### User Story 4 - Specify Video Tune Options (Priority: P3)

As a content-aware encoder, I want to specify tune options for different content types so that encoding is optimized for my content (film, animation, grain).

**Why this priority**: Tune options provide content-specific optimization but are optional refinements beyond basic quality settings.

**Independent Test**: Can be fully tested by transcoding animation content with and without the animation tune and comparing visual quality.

**Acceptance Scenarios**:

1. **Given** a policy with `quality.tune: film`, **When** I transcode a movie file, **Then** the encoder applies film-specific optimizations.

2. **Given** a policy with `quality.tune: animation`, **When** I transcode an animated video, **Then** the encoder applies animation-specific optimizations (flat areas, sharp edges).

3. **Given** a policy with an invalid tune for the target encoder, **When** I validate the policy, **Then** validation fails with valid tune options for that encoder.

---

### User Story 5 - Downscale Resolution (Priority: P2)

As a 4K collector, I want to downscale 4K content to 1080p while preserving audio so that I save significant storage space with acceptable quality.

**Why this priority**: Resolution downscaling provides the largest storage savings for 4K content. Critical for users managing large libraries.

**Independent Test**: Can be fully tested by downscaling a 4K file to 1080p and verifying output resolution and aspect ratio preservation.

**Acceptance Scenarios**:

1. **Given** a 4K video file and policy with `scaling.max_resolution: 1080p`, **When** I transcode the file, **Then** the output is 1920x1080 (or appropriate aspect-ratio-preserved resolution).

2. **Given** a 720p video file and policy with `scaling.max_resolution: 1080p` and `scaling.upscale: false`, **When** I transcode the file, **Then** the resolution remains 720p (no upscaling).

3. **Given** a 2.35:1 aspect ratio 4K file, **When** I downscale to 1080p, **Then** the output maintains 2.35:1 aspect ratio with appropriate dimensions.

4. **Given** a policy with `scaling.algorithm: lanczos`, **When** I downscale a video, **Then** the Lanczos algorithm is used for high-quality scaling.

---

### User Story 6 - Target Specific Bitrate (Priority: P3)

As a streaming content preparer, I want to target specific bitrates rather than CRF so that I have predictable file sizes for bandwidth planning.

**Why this priority**: Bitrate targeting is essential for streaming preparation where bandwidth constraints are known, but less common than CRF for archival use.

**Independent Test**: Can be fully tested by transcoding a file with a target bitrate and verifying the output bitrate is within acceptable tolerance.

**Acceptance Scenarios**:

1. **Given** a policy with `quality.mode: bitrate` and `quality.bitrate: 5M`, **When** I transcode a video file, **Then** the output targets approximately 5 Mbps video bitrate.

2. **Given** a policy with constrained quality mode (CRF with max_bitrate), **When** I transcode a complex scene, **Then** bitrate is capped at max_bitrate even if CRF would require more.

---

### User Story 7 - Use Hardware Acceleration (Priority: P2)

As a user with GPU encoding capability, I want to automatically use hardware encoders when available so that transcoding is faster without manual configuration.

**Why this priority**: Hardware acceleration can reduce encoding time by 10x or more. Auto-detection removes manual configuration burden.

**Independent Test**: Can be fully tested by running transcode on a system with known GPU and verifying the hardware encoder is detected and used.

**Acceptance Scenarios**:

1. **Given** a system with NVIDIA GPU and policy with `hardware_acceleration.enabled: auto`, **When** I run a transcode job, **Then** the system detects and uses NVENC.

2. **Given** a system without GPU capability and policy with `hardware_acceleration.enabled: auto`, **When** I run a transcode job, **Then** the system falls back to CPU encoding.

3. **Given** `hardware_acceleration.enabled: nvenc` on a system without NVIDIA GPU, **When** I run with `fallback_to_cpu: true`, **Then** the system warns about unavailable hardware and falls back to CPU.

4. **Given** dry-run mode, **When** I preview a transcode operation, **Then** the output shows which encoder (hardware or CPU) will be used.

---

### User Story 8 - Preserve Audio During Video Transcode (Priority: P1)

As an audio quality enthusiast, I want to transcode video only while preserving original audio so that I maintain lossless audio with efficient video compression.

**Why this priority**: Lossless audio preservation is critical for quality-focused users. Re-encoding lossless audio to lossy is often unacceptable.

**Independent Test**: Can be fully tested by transcoding a file with TrueHD audio and verifying the audio track is stream-copied unchanged.

**Acceptance Scenarios**:

1. **Given** a file with TrueHD audio and policy preserving TrueHD, **When** I transcode video to HEVC, **Then** the TrueHD audio track is stream-copied (not re-encoded).

2. **Given** a file with AAC audio and policy preserving only lossless codecs, **When** I transcode, **Then** the AAC audio may be transcoded to the specified target codec.

3. **Given** multiple audio tracks (TrueHD + AAC), **When** I transcode with lossless preservation, **Then** track order is maintained and TrueHD is preserved while AAC may be transcoded.

4. **Given** subtitle tracks in the source file, **When** I transcode video, **Then** all subtitle tracks are stream-copied unchanged.

---

### User Story 9 - View Transcoding Progress (Priority: P3)

As a user running long transcode jobs, I want to see progress and estimated time remaining so that I can plan around the encoding time.

**Why this priority**: Progress visibility is important for user experience but doesn't affect the core transcoding functionality.

**Independent Test**: Can be fully tested by starting a transcode job and verifying progress updates appear with frame count and time estimates.

**Acceptance Scenarios**:

1. **Given** an active transcode job, **When** I view job status, **Then** I see progress percentage and current/total frame count.

2. **Given** an active transcode job that has processed at least 10% of frames, **When** I view job status, **Then** I see estimated time remaining based on current speed.

3. **Given** an active transcode job, **When** I view job status, **Then** I see encoding speed (e.g., "2.5x realtime").

---

### Edge Cases

- What happens when source file has variable frame rate? (System should handle VFR input gracefully)
- How does system handle corrupted source files? (Fail gracefully with clear error message)
- What happens when disk space runs out during transcode? (Detect and report error, clean up partial output)
- How does system handle source files with multiple video streams? (Process primary video stream by default)
- What happens when hardware encoder runs out of memory? (Fall back to CPU if configured, otherwise fail with clear error)
- How does system handle HDR content during downscaling? (Preserve HDR metadata, warn about potential compatibility issues)
- What happens when source bitrate cannot be determined? (Skip bitrate-based conditions with warning)

## Requirements *(mandatory)*

### Functional Requirements

**Skip Conditions**

- **FR-001**: System MUST support `skip_if` conditions in transcode policy for video streams
- **FR-002**: System MUST support skip condition `codec_matches` accepting a list of codec names (e.g., hevc, h265, x265)
- **FR-003**: System MUST support skip condition `resolution_within` accepting resolution presets (480p, 720p, 1080p, 1440p, 4k, 8k)
- **FR-004**: System MUST support skip condition `bitrate_under` accepting bitrate values (e.g., "10M", "5000k")
- **FR-005**: System MUST evaluate all skip conditions with AND logic (all must be true to skip)
- **FR-006**: System MUST display "Skipping video transcode - already compliant" in dry-run when skip conditions are met

**Quality Settings**

- **FR-007**: System MUST support `quality.mode` with values: crf, bitrate, constrained_quality
- **FR-008**: System MUST support `quality.crf` accepting integer values 0-51
- **FR-009**: System MUST apply codec-appropriate CRF defaults when not specified (x264: 23, x265: 28, VP9: 31, AV1: 30)
- **FR-010**: System MUST support `quality.preset` with values: ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow
- **FR-011**: System MUST default to "medium" preset when not specified
- **FR-012**: System MUST support `quality.tune` with codec-appropriate values (film, animation, grain, stillimage, fastdecode, zerolatency)
- **FR-013**: System MUST validate tune options against target encoder capabilities

**Bitrate Targeting**

- **FR-014**: System MUST support `quality.bitrate` accepting values like "5M", "2500k"
- **FR-015**: System MUST support `quality.min_bitrate` and `quality.max_bitrate` for constrained quality mode
- **FR-016**: System SHOULD support two-pass encoding for accurate bitrate targeting when configured

**Resolution Scaling**

- **FR-017**: System MUST support `scaling.max_resolution` with presets: 480p, 720p, 1080p, 1440p, 4k, 8k
- **FR-018**: System MUST support explicit `scaling.max_width` and `scaling.max_height` for custom limits
- **FR-019**: System MUST preserve aspect ratio during all scaling operations
- **FR-020**: System MUST support `scaling.algorithm` with values: lanczos, bicubic, bilinear
- **FR-021**: System MUST support `scaling.upscale: false` to prevent upscaling smaller content
- **FR-022**: System MUST default to no upscaling (upscale: false)

**Hardware Acceleration**

- **FR-023**: System MUST support `hardware_acceleration.enabled` with values: auto, nvenc, qsv, vaapi, none
- **FR-024**: System MUST auto-detect available hardware encoders when set to "auto"
- **FR-025**: System MUST support `hardware_acceleration.fallback_to_cpu` boolean option
- **FR-026**: System MUST display selected encoder in dry-run output
- **FR-027**: System MUST detect NVENC (NVIDIA), QSV (Intel), and VAAPI (Linux) when available

**Audio Handling**

- **FR-028**: System MUST support `audio.preserve_codecs` list specifying codecs to stream-copy
- **FR-029**: System MUST support `audio.transcode_to` specifying target codec for non-preserved audio
- **FR-030**: System MUST support `audio.transcode_bitrate` for audio transcoding
- **FR-031**: System MUST stream-copy all subtitle tracks during video transcode
- **FR-032**: System MUST preserve track order through transcoding operations

**Progress Reporting**

- **FR-033**: System MUST report transcoding progress as percentage complete
- **FR-034**: System MUST report current frame and total frame count during transcode
- **FR-035**: System MUST calculate and display estimated time remaining
- **FR-036**: System MUST display encoding speed relative to realtime (e.g., "2.5x")
- **FR-037**: System MUST make progress available in both CLI and web UI

**Output Handling**

- **FR-042**: System MUST write transcoded output to a temporary location during encoding
- **FR-043**: System MUST replace original file with transcoded output only after successful completion
- **FR-044**: System MUST clean up temporary files on transcode failure
- **FR-045**: System MUST verify transcoded file integrity before replacing original:
  - Output file exists and size > 0 bytes
  - ffprobe successfully reads container metadata
  - Video stream count matches expected (at least 1)
  - Duration within 1% of source duration (detect truncation)

**Validation**

- **FR-038**: System MUST validate CRF values are within 0-51 range
- **FR-039**: System MUST validate preset values against supported list per encoder
- **FR-040**: System MUST validate tune values against supported list per encoder
- **FR-041**: System MUST validate bitrate format (numeric with M/k suffix)

### Key Entities

- **TranscodePolicy**: Configuration specifying video transcoding behavior including target codec, quality settings, skip conditions, scaling options, and audio handling
- **SkipCondition**: Set of conditions (codec, resolution, bitrate) that when all true, skip transcoding
- **QualitySettings**: Configuration for CRF/bitrate mode, preset, tune options
- **ScalingSettings**: Configuration for resolution limits, algorithm, and upscale prevention
- **HardwareAcceleration**: Configuration for encoder selection and fallback behavior
- **AudioSettings**: Configuration for codec preservation and transcoding rules
- **TranscodeProgress**: Runtime state tracking frame count, percentage, speed, and time estimates

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can skip transcoding for compliant files, avoiding unnecessary re-encoding in 100% of matching cases
- **SC-002**: Users can achieve target quality levels within 5% variance of expected CRF-based output size
- **SC-003**: Users can complete transcoding configuration in under 5 minutes using documented presets
- **SC-004**: Hardware-accelerated encoding achieves at least 3x speed improvement over CPU encoding when available
- **SC-005**: Audio preservation maintains bit-perfect copies of specified lossless codecs in 100% of cases
- **SC-006**: Progress estimates are accurate within 20% of actual completion time after 10% progress
- **SC-007**: All policy validation errors provide actionable feedback identifying the specific issue and valid alternatives
- **SC-008**: Track order and subtitle streams are preserved identically through transcoding in 100% of cases

## Clarifications

### Session 2025-11-26

- Q: Where should transcoded output files be written? → A: Write to temp location, replace original only on success

## Assumptions

- Users have ffmpeg installed with appropriate encoder support (libx264, libx265, libvpx-vp9, etc.)
- Hardware acceleration requires appropriate drivers and ffmpeg builds with hardware support
- Source media files are accessible and readable
- Sufficient disk space exists for temporary transcoding output
- Two-pass encoding doubles processing time but provides more accurate bitrate targeting
- Default scaling algorithm is lanczos for best quality unless specified otherwise
- VP9 presets map to numeric CPU-used values (0-8) internally while presenting standard preset names to users

## Dependencies

- Sprint 2 (Conditional Logic) - skip condition evaluation framework
- ffprobe for source file analysis (codec, resolution, bitrate detection)
- ffmpeg for transcoding operations
- Existing TranscodeExecutor infrastructure for job execution
