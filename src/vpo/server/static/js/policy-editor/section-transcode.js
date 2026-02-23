/**
 * Transcode Section Module for Policy Editor (V13 flat structure)
 *
 * Handles video and audio transcode configuration UI.
 * V13 uses a flat video config (no nested quality/scaling/hardware_acceleration).
 * Features:
 * - Video target codec (`to`) dropdown with codec-specific options
 * - Skip conditions (codec_matches, resolution_within, bitrate_under)
 * - Quality fields flat on video: crf, preset, tune, target_bitrate,
 *   min_bitrate, max_bitrate, two_pass (mode inferred server-side)
 * - Scaling fields flat on video: max_resolution, scale_algorithm, upscale
 * - Hardware acceleration flat on video: hw, hw_fallback
 * - Audio: preserve list, to codec, and bitrate
 */

// Constants for video transcode options
const _VIDEO_CODECS = [
    { value: '', label: '-- Not configured --' },
    { value: 'hevc', label: 'HEVC (H.265)' },
    { value: 'h264', label: 'H.264 (AVC)' },
    { value: 'vp9', label: 'VP9' },
    { value: 'av1', label: 'AV1' }
]

const SKIP_CODECS = [
    'hevc', 'h265', 'h264', 'avc', 'vp9', 'av1',
    'mpeg2video', 'mpeg4', 'vc1', 'wmv3'
]

const RESOLUTIONS = [
    { value: '', label: '-- No limit --' },
    { value: '8k', label: '8K (7680x4320)' },
    { value: '4k', label: '4K (3840x2160)' },
    { value: '1440p', label: '1440p (2560x1440)' },
    { value: '1080p', label: '1080p (1920x1080)' },
    { value: '720p', label: '720p (1280x720)' },
    { value: '480p', label: '480p (720x480)' }
]

const QUALITY_MODES = [
    { value: 'crf', label: 'CRF (Constant Rate Factor)' },
    { value: 'bitrate', label: 'Target Bitrate' },
    { value: 'constrained_quality', label: 'Constrained Quality' }
]

const PRESETS = [
    'ultrafast', 'superfast', 'veryfast', 'faster', 'fast',
    'medium', 'slow', 'slower', 'veryslow'
]

const TUNES = [
    { value: '', label: '-- None --' },
    { value: 'film', label: 'Film' },
    { value: 'animation', label: 'Animation' },
    { value: 'grain', label: 'Grain' },
    { value: 'stillimage', label: 'Still Image' },
    { value: 'fastdecode', label: 'Fast Decode' },
    { value: 'zerolatency', label: 'Zero Latency' }
]

const SCALE_ALGORITHMS = [
    { value: 'lanczos', label: 'Lanczos (Best Quality)' },
    { value: 'bilinear', label: 'Bilinear (Fast)' },
    { value: 'bicubic', label: 'Bicubic (Balanced)' }
]

const HW_ACCEL_MODES = [
    { value: 'auto', label: 'Auto (Detect and Use)' },
    { value: 'nvenc', label: 'NVIDIA NVENC' },
    { value: 'qsv', label: 'Intel Quick Sync' },
    { value: 'vaapi', label: 'VA-API (Linux)' },
    { value: 'none', label: 'Disabled (CPU Only)' }
]

// Audio codec options for preserve and to
const AUDIO_CODECS = [
    'truehd', 'dts-hd', 'flac', 'pcm_s24le', 'pcm_s16le',
    'aac', 'ac3', 'eac3', 'dts', 'opus', 'vorbis', 'mp3'
]

const _AUDIO_TRANSCODE_CODECS = [
    { value: '', label: '-- Not configured --' },
    { value: 'aac', label: 'AAC' },
    { value: 'ac3', label: 'AC3 (Dolby Digital)' },
    { value: 'eac3', label: 'E-AC3 (Dolby Digital Plus)' },
    { value: 'opus', label: 'Opus' },
    { value: 'flac', label: 'FLAC (Lossless)' }
]

/**
 * Initialize the transcode section
 * @param {Object} policyData - Current policy data
 * @param {Function} onUpdate - Callback when transcode data changes
 * @returns {Object} Controller with methods to get/set state
 */
export function initTranscodeSection(policyData, onUpdate) {
    // Get DOM elements
    const videoCodecSelect = document.getElementById('video-target-codec')
    const videoOptionsDiv = document.getElementById('video-transcode-options')
    const audioTranscodeSelect = document.getElementById('audio-transcode-to')
    const audioOptionsDiv = document.getElementById('audio-transcode-options')

    if (!videoCodecSelect) {
        console.warn('Video transcode section not found')
        return null
    }

    // Current state
    let state = {
        video: extractVideoConfig(policyData),
        audio: extractAudioConfig(policyData)
    }

    /**
     * Extract video transcode config from policy data (V13 flat structure)
     */
    function extractVideoConfig(data) {
        const transcode = data?.transcode?.video
        if (!transcode) return null

        return {
            to: transcode.to || '',
            skip_if: transcode.skip_if || null,
            crf: transcode.crf ?? null,
            preset: transcode.preset || null,
            tune: transcode.tune || null,
            target_bitrate: transcode.target_bitrate || null,
            min_bitrate: transcode.min_bitrate || null,
            max_bitrate: transcode.max_bitrate || null,
            two_pass: transcode.two_pass || false,
            max_resolution: transcode.max_resolution || null,
            scale_algorithm: transcode.scale_algorithm || null,
            upscale: transcode.upscale || false,
            hw: transcode.hw || null,
            hw_fallback: transcode.hw_fallback ?? null
        }
    }

    /**
     * Extract audio transcode config from policy data (V13 field names)
     */
    function extractAudioConfig(data) {
        const transcode = data?.transcode?.audio
        if (!transcode) return null

        return {
            preserve: transcode.preserve || [],
            to: transcode.to || 'aac',
            bitrate: transcode.bitrate || '192k'
        }
    }

    /**
     * Build the video options form HTML
     */
    function buildVideoOptionsHTML() {
        return `
            <!-- Skip Conditions -->
            <div class="accordion-subsection" id="video-skip-section">
                <h4 class="accordion-subsection-title">Skip Conditions</h4>
                <p class="form-hint">Skip transcoding when all specified conditions are met.</p>

                <div class="form-group">
                    <label for="video-skip-codecs">Skip if codec matches</label>
                    <div class="codec-tags" id="video-skip-codec-tags"></div>
                    <div class="accordion-list-add">
                        <select id="video-skip-codec-select">
                            <option value="">Select codec...</option>
                            ${SKIP_CODECS.map(c => `<option value="${c}">${c.toUpperCase()}</option>`).join('')}
                        </select>
                        <button type="button" id="video-skip-codec-add" class="btn-secondary">Add</button>
                    </div>
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label for="video-skip-resolution">Skip if resolution within</label>
                        <select id="video-skip-resolution">
                            ${RESOLUTIONS.map(r => `<option value="${r.value}">${r.label}</option>`).join('')}
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="video-skip-bitrate">Skip if bitrate under</label>
                        <input type="text" id="video-skip-bitrate" placeholder="e.g., 15M or 8000k">
                        <p class="form-hint">Format: number + M or k (e.g., 10M, 5000k)</p>
                    </div>
                </div>
            </div>

            <!-- Quality Settings -->
            <div class="accordion-subsection" id="video-quality-section">
                <h4 class="accordion-subsection-title">Quality Settings</h4>

                <div class="form-group">
                    <label for="video-quality-mode">Quality Mode</label>
                    <select id="video-quality-mode">
                        ${QUALITY_MODES.map(m => `<option value="${m.value}">${m.label}</option>`).join('')}
                    </select>
                </div>

                <div class="form-row">
                    <div class="form-group" id="video-crf-group">
                        <label for="video-quality-crf">CRF Value (0-51)</label>
                        <input type="number" id="video-quality-crf" min="0" max="51" placeholder="18-28 typical">
                        <p class="form-hint">Lower = better quality. HEVC: 20-28, H.264: 18-23</p>
                    </div>
                    <div class="form-group initially-hidden" id="video-bitrate-group">
                        <label for="video-quality-bitrate">Target Bitrate</label>
                        <input type="text" id="video-quality-bitrate" placeholder="e.g., 5M or 2500k">
                    </div>
                </div>

                <div class="form-row initially-hidden" id="video-constrained-group">
                    <div class="form-group">
                        <label for="video-quality-min-bitrate">Min Bitrate</label>
                        <input type="text" id="video-quality-min-bitrate" placeholder="e.g., 2M">
                    </div>
                    <div class="form-group">
                        <label for="video-quality-max-bitrate">Max Bitrate</label>
                        <input type="text" id="video-quality-max-bitrate" placeholder="e.g., 10M">
                    </div>
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label for="video-quality-preset">Encoding Preset</label>
                        <select id="video-quality-preset">
                            ${PRESETS.map(p => `<option value="${p}" ${p === 'medium' ? 'selected' : ''}>${p.charAt(0).toUpperCase() + p.slice(1)}</option>`).join('')}
                        </select>
                        <p class="form-hint">Slower = smaller file size</p>
                    </div>
                    <div class="form-group">
                        <label for="video-quality-tune">Content Tune</label>
                        <select id="video-quality-tune">
                            ${TUNES.map(t => `<option value="${t.value}">${t.label}</option>`).join('')}
                        </select>
                    </div>
                </div>

                <div class="checkbox-group">
                    <label class="checkbox-label">
                        <input type="checkbox" id="video-quality-twopass">
                        <span>Enable two-pass encoding (slower, more accurate bitrate)</span>
                    </label>
                </div>
            </div>

            <!-- Scaling Settings -->
            <div class="accordion-subsection" id="video-scaling-section">
                <h4 class="accordion-subsection-title">Resolution Scaling</h4>

                <div class="form-row">
                    <div class="form-group">
                        <label for="video-scaling-resolution">Max Resolution</label>
                        <select id="video-scaling-resolution">
                            ${RESOLUTIONS.map(r => `<option value="${r.value}">${r.label}</option>`).join('')}
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="video-scaling-algorithm">Scaling Algorithm</label>
                        <select id="video-scaling-algorithm">
                            ${SCALE_ALGORITHMS.map(a => `<option value="${a.value}">${a.label}</option>`).join('')}
                        </select>
                    </div>
                </div>

                <div class="checkbox-group">
                    <label class="checkbox-label">
                        <input type="checkbox" id="video-scaling-upscale">
                        <span>Allow upscaling (scale up smaller content to max resolution)</span>
                    </label>
                </div>
            </div>

            <!-- Hardware Acceleration -->
            <div class="accordion-subsection" id="video-hwaccel-section">
                <h4 class="accordion-subsection-title">Hardware Acceleration</h4>

                <div class="form-row">
                    <div class="form-group">
                        <label for="video-hwaccel-mode">Hardware Encoder</label>
                        <select id="video-hwaccel-mode">
                            ${HW_ACCEL_MODES.map(m => `<option value="${m.value}">${m.label}</option>`).join('')}
                        </select>
                    </div>
                </div>

                <div class="checkbox-group">
                    <label class="checkbox-label">
                        <input type="checkbox" id="video-hwaccel-fallback" checked>
                        <span>Fallback to CPU if hardware unavailable</span>
                    </label>
                </div>
            </div>
        `
    }

    /**
     * Build the audio options form HTML
     */
    function buildAudioOptionsHTML() {
        return `
            <div class="form-group">
                <label>Preserve Codecs (stream-copy without re-encoding)</label>
                <div class="codec-tags" id="audio-preserve-codec-tags"></div>
                <div class="accordion-list-add">
                    <select id="audio-preserve-codec-select">
                        <option value="">Select codec...</option>
                        ${AUDIO_CODECS.map(c => `<option value="${c}">${c.toUpperCase()}</option>`).join('')}
                    </select>
                    <button type="button" id="audio-preserve-codec-add" class="btn-secondary">Add</button>
                </div>
                <p class="form-hint">High-quality codecs like TrueHD, DTS-HD, FLAC are typically preserved.</p>
            </div>

            <div class="form-row">
                <div class="form-group">
                    <label for="audio-transcode-bitrate">Transcode Bitrate</label>
                    <input type="text" id="audio-transcode-bitrate" placeholder="e.g., 192k or 256k">
                    <p class="form-hint">Bitrate for non-preserved audio tracks</p>
                </div>
            </div>
        `
    }

    /**
     * Render codec tags for skip/preserve lists
     */
    function renderCodecTags(containerId, codecs, onRemove) {
        const container = document.getElementById(containerId)
        if (!container) return

        if (!codecs || codecs.length === 0) {
            container.innerHTML = '<span class="accordion-list-empty">No codecs selected</span>'
            return
        }

        container.innerHTML = codecs.map(codec => `
            <span class="codec-tag">
                ${codec.toUpperCase()}
                <button type="button" class="codec-tag-remove" data-codec="${codec}" aria-label="Remove ${codec}">&times;</button>
            </span>
        `).join('')

        // Add remove handlers
        container.querySelectorAll('.codec-tag-remove').forEach(btn => {
            btn.addEventListener('click', () => {
                const codecToRemove = btn.dataset.codec
                onRemove(codecToRemove)
            })
        })
    }

    /**
     * Update state and notify parent
     */
    function updateState() {
        if (onUpdate) {
            onUpdate(getTranscodeConfig())
        }
    }

    /**
     * Get current transcode configuration (V13 flat video structure)
     */
    function getTranscodeConfig() {
        const config = {}

        // Video config (flat - no nested quality/scaling/hardware_acceleration)
        const videoCodec = videoCodecSelect?.value
        if (videoCodec) {
            config.video = { to: videoCodec }

            // Skip conditions (field names unchanged)
            const skipConfig = getSkipConfig()
            if (skipConfig && Object.keys(skipConfig).length > 0) {
                config.video.skip_if = skipConfig
            }

            // Quality fields (flat, no mode field - mode inferred server-side)
            const mode = document.getElementById('video-quality-mode')?.value

            const crf = document.getElementById('video-quality-crf')?.value
            if (crf && (mode === 'crf' || mode === 'constrained_quality')) {
                config.video.crf = parseInt(crf, 10)
            }

            const targetBitrate = document.getElementById('video-quality-bitrate')?.value?.trim()
            if (targetBitrate && (mode === 'bitrate' || mode === 'constrained_quality')) {
                config.video.target_bitrate = targetBitrate
            }

            const minBitrate = document.getElementById('video-quality-min-bitrate')?.value?.trim()
            if (minBitrate && mode === 'constrained_quality') {
                config.video.min_bitrate = minBitrate
            }

            const maxBitrate = document.getElementById('video-quality-max-bitrate')?.value?.trim()
            if (maxBitrate && mode === 'constrained_quality') {
                config.video.max_bitrate = maxBitrate
            }

            const preset = document.getElementById('video-quality-preset')?.value
            if (preset && preset !== 'medium') {
                config.video.preset = preset
            }

            const tune = document.getElementById('video-quality-tune')?.value
            if (tune) {
                config.video.tune = tune
            }

            const twoPass = document.getElementById('video-quality-twopass')?.checked
            if (twoPass) {
                config.video.two_pass = true
            }

            // Scaling fields (flat)
            const resolution = document.getElementById('video-scaling-resolution')?.value
            if (resolution) {
                config.video.max_resolution = resolution
            }

            const algorithm = document.getElementById('video-scaling-algorithm')?.value
            if (algorithm && algorithm !== 'lanczos') {
                config.video.scale_algorithm = algorithm
            }

            const upscale = document.getElementById('video-scaling-upscale')?.checked
            if (upscale) {
                config.video.upscale = true
            }

            // Hardware acceleration fields (flat)
            const hwMode = document.getElementById('video-hwaccel-mode')?.value
            if (hwMode && hwMode !== 'auto') {
                config.video.hw = hwMode
            }

            const hwFallback = document.getElementById('video-hwaccel-fallback')?.checked
            if (hwFallback === false) {
                config.video.hw_fallback = false
            }
        }

        // Audio config
        const audioConfig = getAudioTranscodeConfig()
        if (audioConfig) {
            config.audio = audioConfig
        }

        return Object.keys(config).length > 0 ? config : null
    }

    /**
     * Get skip conditions config
     */
    function getSkipConfig() {
        const config = {}

        // Codec matches
        if (state.video?.skip_if?.codec_matches?.length > 0) {
            config.codec_matches = state.video.skip_if.codec_matches
        }

        // Resolution
        const resolution = document.getElementById('video-skip-resolution')?.value
        if (resolution) {
            config.resolution_within = resolution
        }

        // Bitrate
        const bitrate = document.getElementById('video-skip-bitrate')?.value?.trim()
        if (bitrate) {
            config.bitrate_under = bitrate
        }

        return config
    }

    /**
     * Get audio transcode config (V13 field names)
     */
    function getAudioTranscodeConfig() {
        const transcodeTo = audioTranscodeSelect?.value
        if (!transcodeTo) return null

        const config = {
            to: transcodeTo
        }

        // Preserve codecs
        if (state.audio?.preserve?.length > 0) {
            config.preserve = state.audio.preserve
        }

        // Bitrate
        const bitrate = document.getElementById('audio-transcode-bitrate')?.value?.trim()
        if (bitrate) {
            config.bitrate = bitrate
        }

        return config
    }

    /**
     * Populate form from state (V13 flat structure)
     */
    function populateForm() {
        // Video codec
        if (state.video?.to && videoCodecSelect) {
            videoCodecSelect.value = state.video.to
            showVideoOptions()
        }

        // Skip conditions (field names unchanged)
        if (state.video?.skip_if) {
            const skipRes = document.getElementById('video-skip-resolution')
            if (skipRes && state.video.skip_if.resolution_within) {
                skipRes.value = state.video.skip_if.resolution_within
            }

            const skipBitrate = document.getElementById('video-skip-bitrate')
            if (skipBitrate && state.video.skip_if.bitrate_under) {
                skipBitrate.value = state.video.skip_if.bitrate_under
            }

            renderCodecTags('video-skip-codec-tags',
                state.video.skip_if.codec_matches,
                (codec) => {
                    state.video.skip_if.codec_matches = state.video.skip_if.codec_matches.filter(c => c !== codec)
                    renderCodecTags('video-skip-codec-tags', state.video.skip_if.codec_matches, arguments.callee)
                    updateState()
                }
            )
        }

        // Quality settings (flat on state.video, infer mode from fields)
        if (state.video) {
            // Infer quality mode from which fields are set
            let inferredMode = 'crf' // default
            if (state.video.crf != null && state.video.max_bitrate) {
                inferredMode = 'constrained_quality'
            } else if (state.video.target_bitrate) {
                inferredMode = 'bitrate'
            } else if (state.video.crf != null) {
                inferredMode = 'crf'
            }

            const modeSelect = document.getElementById('video-quality-mode')
            if (modeSelect) {
                modeSelect.value = inferredMode
                handleQualityModeChange(inferredMode)
            }

            const crfInput = document.getElementById('video-quality-crf')
            if (crfInput && state.video.crf != null) {
                crfInput.value = state.video.crf
            }

            const bitrateInput = document.getElementById('video-quality-bitrate')
            if (bitrateInput && state.video.target_bitrate) {
                bitrateInput.value = state.video.target_bitrate
            }

            const minBitrateInput = document.getElementById('video-quality-min-bitrate')
            if (minBitrateInput && state.video.min_bitrate) {
                minBitrateInput.value = state.video.min_bitrate
            }

            const maxBitrateInput = document.getElementById('video-quality-max-bitrate')
            if (maxBitrateInput && state.video.max_bitrate) {
                maxBitrateInput.value = state.video.max_bitrate
            }

            const presetSelect = document.getElementById('video-quality-preset')
            if (presetSelect && state.video.preset) {
                presetSelect.value = state.video.preset
            }

            const tuneSelect = document.getElementById('video-quality-tune')
            if (tuneSelect && state.video.tune) {
                tuneSelect.value = state.video.tune
            }

            const twoPassCheck = document.getElementById('video-quality-twopass')
            if (twoPassCheck) {
                twoPassCheck.checked = state.video.two_pass || false
            }

            // Scaling settings (flat on state.video)
            const resSelect = document.getElementById('video-scaling-resolution')
            if (resSelect && state.video.max_resolution) {
                resSelect.value = state.video.max_resolution
            }

            const algoSelect = document.getElementById('video-scaling-algorithm')
            if (algoSelect && state.video.scale_algorithm) {
                algoSelect.value = state.video.scale_algorithm
            }

            const upscaleCheck = document.getElementById('video-scaling-upscale')
            if (upscaleCheck) {
                upscaleCheck.checked = state.video.upscale || false
            }

            // Hardware acceleration (flat on state.video)
            const hwModeSelect = document.getElementById('video-hwaccel-mode')
            if (hwModeSelect && state.video.hw) {
                hwModeSelect.value = state.video.hw
            }

            const fallbackCheck = document.getElementById('video-hwaccel-fallback')
            if (fallbackCheck) {
                fallbackCheck.checked = state.video.hw_fallback !== false
            }
        }

        // Audio config
        if (state.audio) {
            if (audioTranscodeSelect && state.audio.to) {
                audioTranscodeSelect.value = state.audio.to
                showAudioOptions()
            }

            const bitrateInput = document.getElementById('audio-transcode-bitrate')
            if (bitrateInput && state.audio.bitrate) {
                bitrateInput.value = state.audio.bitrate
            }

            renderCodecTags('audio-preserve-codec-tags',
                state.audio.preserve,
                (codec) => {
                    state.audio.preserve = state.audio.preserve.filter(c => c !== codec)
                    renderCodecTags('audio-preserve-codec-tags', state.audio.preserve, arguments.callee)
                    updateState()
                }
            )
        }
    }

    /**
     * Show/hide video options based on codec selection
     */
    function showVideoOptions() {
        if (videoOptionsDiv) {
            videoOptionsDiv.style.display = videoCodecSelect?.value ? 'block' : 'none'
        }
    }

    /**
     * Show/hide audio options based on audio codec selection
     */
    function showAudioOptions() {
        if (audioOptionsDiv) {
            audioOptionsDiv.style.display = audioTranscodeSelect?.value ? 'block' : 'none'
        }
    }

    /**
     * Handle quality mode change
     */
    function handleQualityModeChange(mode) {
        const crfGroup = document.getElementById('video-crf-group')
        const bitrateGroup = document.getElementById('video-bitrate-group')
        const constrainedGroup = document.getElementById('video-constrained-group')

        if (crfGroup) crfGroup.style.display = mode === 'crf' ? 'block' : 'none'
        if (bitrateGroup) bitrateGroup.style.display = (mode === 'bitrate' || mode === 'constrained_quality') ? 'block' : 'none'
        if (constrainedGroup) constrainedGroup.style.display = mode === 'constrained_quality' ? 'flex' : 'none'
    }

    /**
     * Set up event listeners
     */
    function setupEventListeners() {
        // Video codec change
        videoCodecSelect?.addEventListener('change', () => {
            showVideoOptions()
            updateState()
        })

        // Audio codec change
        audioTranscodeSelect?.addEventListener('change', () => {
            showAudioOptions()
            updateState()
        })

        // Quality mode change
        document.getElementById('video-quality-mode')?.addEventListener('change', (e) => {
            handleQualityModeChange(e.target.value)
            updateState()
        })

        // Skip codec add
        const videoSkipCodecSelect = document.getElementById('video-skip-codec-select')
        const videoSkipCodecAddBtn = document.getElementById('video-skip-codec-add')

        videoSkipCodecAddBtn?.addEventListener('click', () => {
            const codec = videoSkipCodecSelect?.value
            if (!codec) return

            if (!state.video) state.video = { to: videoCodecSelect?.value || '' }
            if (!state.video.skip_if) state.video.skip_if = {}
            if (!state.video.skip_if.codec_matches) state.video.skip_if.codec_matches = []

            if (!state.video.skip_if.codec_matches.includes(codec)) {
                state.video.skip_if.codec_matches.push(codec)
                renderCodecTags('video-skip-codec-tags',
                    state.video.skip_if.codec_matches,
                    (c) => {
                        state.video.skip_if.codec_matches = state.video.skip_if.codec_matches.filter(x => x !== c)
                        renderCodecTags('video-skip-codec-tags', state.video.skip_if.codec_matches, arguments.callee)
                        updateState()
                    }
                )
                updateState()
            }
            videoSkipCodecSelect.value = ''
            // H2: Update button state after clearing select
            if (videoSkipCodecAddBtn) videoSkipCodecAddBtn.disabled = true
        })

        // H2: Disable Add button when no codec selected
        if (videoSkipCodecSelect && videoSkipCodecAddBtn) {
            const updateVideoSkipAddBtnState = () => {
                videoSkipCodecAddBtn.disabled = !videoSkipCodecSelect.value
            }
            videoSkipCodecSelect.addEventListener('change', updateVideoSkipAddBtnState)
            updateVideoSkipAddBtnState() // Initial state
        }

        // Audio preserve codec add
        const audioPreserveCodecSelect = document.getElementById('audio-preserve-codec-select')
        const audioPreserveCodecAddBtn = document.getElementById('audio-preserve-codec-add')

        audioPreserveCodecAddBtn?.addEventListener('click', () => {
            const codec = audioPreserveCodecSelect?.value
            if (!codec) return

            if (!state.audio) state.audio = { to: audioTranscodeSelect?.value || 'aac' }
            if (!state.audio.preserve) state.audio.preserve = []

            if (!state.audio.preserve.includes(codec)) {
                state.audio.preserve.push(codec)
                renderCodecTags('audio-preserve-codec-tags',
                    state.audio.preserve,
                    (c) => {
                        state.audio.preserve = state.audio.preserve.filter(x => x !== c)
                        renderCodecTags('audio-preserve-codec-tags', state.audio.preserve, arguments.callee)
                        updateState()
                    }
                )
                updateState()
            }
            audioPreserveCodecSelect.value = ''
            // H2: Update button state after clearing select
            if (audioPreserveCodecAddBtn) audioPreserveCodecAddBtn.disabled = true
        })

        // H2: Disable Add button when no codec selected
        if (audioPreserveCodecSelect && audioPreserveCodecAddBtn) {
            const updateAudioPreserveAddBtnState = () => {
                audioPreserveCodecAddBtn.disabled = !audioPreserveCodecSelect.value
            }
            audioPreserveCodecSelect.addEventListener('change', updateAudioPreserveAddBtnState)
            updateAudioPreserveAddBtnState() // Initial state
        }

        // All input changes trigger update
        const inputs = [
            'video-skip-resolution', 'video-skip-bitrate',
            'video-quality-crf', 'video-quality-bitrate',
            'video-quality-min-bitrate', 'video-quality-max-bitrate',
            'video-quality-preset', 'video-quality-tune', 'video-quality-twopass',
            'video-scaling-resolution', 'video-scaling-algorithm', 'video-scaling-upscale',
            'video-hwaccel-mode', 'video-hwaccel-fallback',
            'audio-transcode-bitrate'
        ]

        inputs.forEach(id => {
            const el = document.getElementById(id)
            if (el) {
                el.addEventListener('change', updateState)
                el.addEventListener('input', updateState)
            }
        })
    }

    // Initialize
    function init() {
        // Build options HTML
        if (videoOptionsDiv) {
            videoOptionsDiv.innerHTML = buildVideoOptionsHTML()
        }

        if (audioOptionsDiv) {
            audioOptionsDiv.innerHTML = buildAudioOptionsHTML()
        }

        // Populate form
        populateForm()

        // Setup listeners
        setupEventListeners()

        // Show/hide based on initial state
        showVideoOptions()
        showAudioOptions()
    }

    // Run initialization
    init()

    // Return controller
    return {
        getConfig: getTranscodeConfig,
        setConfig: (config) => {
            state = {
                video: config?.video || null,
                audio: config?.audio || null
            }
            populateForm()
        },
        refresh: () => {
            populateForm()
        }
    }
}

export default { initTranscodeSection }
