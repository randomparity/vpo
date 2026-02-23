/**
 * Track Filters Section Module for Policy Editor (036-v9-policy-editor)
 *
 * Handles audio, subtitle, and attachment filter configuration UI.
 * Features:
 * - Audio filter: languages list, fallback mode, minimum tracks
 * - V10 audio filter: music/sfx/non-speech track handling options
 * - Subtitle filter: languages list, preserve_forced, remove_all
 * - Attachment filter: remove_all toggle
 * - Language code validation (ISO 639-2/B: 2-3 lowercase letters)
 */

// ISO 639-2/B language code pattern (2-3 lowercase letters)
const LANGUAGE_PATTERN = /^[a-z]{2,3}$/

// Common audio/subtitle language codes for quick selection
const COMMON_LANGUAGES = [
    { code: 'eng', label: 'English' },
    { code: 'jpn', label: 'Japanese' },
    { code: 'spa', label: 'Spanish' },
    { code: 'fra', label: 'French' },
    { code: 'deu', label: 'German' },
    { code: 'ita', label: 'Italian' },
    { code: 'por', label: 'Portuguese' },
    { code: 'rus', label: 'Russian' },
    { code: 'chi', label: 'Chinese' },
    { code: 'kor', label: 'Korean' },
    { code: 'ara', label: 'Arabic' },
    { code: 'hin', label: 'Hindi' },
    { code: 'und', label: 'Undefined' }
]

// Fallback mode options
const FALLBACK_MODES = [
    { value: '', label: '-- No fallback --' },
    { value: 'content_language', label: 'Content Language' },
    { value: 'keep_all', label: 'Keep All' },
    { value: 'keep_first', label: 'Keep First' },
    { value: 'error', label: 'Error' }
]

/**
 * Validate ISO 639-2/B language code
 * @param {string} code - Language code to validate
 * @returns {boolean} True if valid
 */
function isValidLanguageCode(code) {
    return LANGUAGE_PATTERN.test(code)
}

/**
 * Create a language tag component with add/remove controls
 * @param {string[]} languages - Current list of language codes
 * @param {Function} onUpdate - Callback when languages change
 * @param {string} inputId - ID for the input element
 * @returns {HTMLElement} Container element
 */
function createLanguageTagsComponent(languages, onUpdate, inputId) {
    const container = document.createElement('div')
    container.className = 'language-tags-component'

    // Tags container
    const tagsDiv = document.createElement('div')
    tagsDiv.className = 'codec-tags'  // Reuse codec-tag styling

    // Input row
    const inputRow = document.createElement('div')
    inputRow.className = 'codec-input-row'

    const input = document.createElement('input')
    input.type = 'text'
    input.id = inputId
    input.placeholder = 'Enter language code (e.g., eng)'
    input.className = 'form-input'
    input.maxLength = 3
    input.style.width = '180px'

    const addBtn = document.createElement('button')
    addBtn.type = 'button'
    addBtn.className = 'btn-secondary btn-small'
    addBtn.textContent = 'Add'

    // Quick add dropdown
    const quickSelect = document.createElement('select')
    quickSelect.className = 'form-select'
    quickSelect.style.width = '150px'
    const defaultOpt = document.createElement('option')
    defaultOpt.value = ''
    defaultOpt.textContent = '-- Quick add --'
    quickSelect.appendChild(defaultOpt)
    COMMON_LANGUAGES.forEach(lang => {
        const opt = document.createElement('option')
        opt.value = lang.code
        opt.textContent = `${lang.code} - ${lang.label}`
        quickSelect.appendChild(opt)
    })

    function renderTags() {
        tagsDiv.innerHTML = ''
        if (languages.length === 0) {
            const empty = document.createElement('span')
            empty.className = 'codec-tags-empty'
            empty.textContent = 'No languages configured'
            tagsDiv.appendChild(empty)
        } else {
            languages.forEach((code, idx) => {
                const tag = document.createElement('span')
                tag.className = 'codec-tag'
                tag.textContent = code

                const removeBtn = document.createElement('button')
                removeBtn.type = 'button'
                removeBtn.className = 'codec-tag-remove'
                removeBtn.textContent = '\u00d7'
                removeBtn.title = `Remove ${code}`
                removeBtn.onclick = () => {
                    languages.splice(idx, 1)
                    renderTags()
                    onUpdate([...languages])
                }

                tag.appendChild(removeBtn)
                tagsDiv.appendChild(tag)
            })
        }
    }

    function addLanguage(code) {
        const normalized = code.toLowerCase().trim()
        if (!normalized) return false

        if (!isValidLanguageCode(normalized)) {
            input.setCustomValidity('Invalid language code (use 2-3 lowercase letters)')
            input.reportValidity()
            return false
        }

        if (languages.includes(normalized)) {
            input.setCustomValidity('Language already added')
            input.reportValidity()
            return false
        }

        input.setCustomValidity('')
        languages.push(normalized)
        renderTags()
        onUpdate([...languages])
        return true
    }

    addBtn.onclick = () => {
        if (addLanguage(input.value)) {
            input.value = ''
        }
    }

    input.onkeydown = (e) => {
        if (e.key === 'Enter') {
            e.preventDefault()
            if (addLanguage(input.value)) {
                input.value = ''
            }
        }
    }

    input.oninput = () => {
        input.setCustomValidity('')
    }

    quickSelect.onchange = () => {
        if (quickSelect.value) {
            addLanguage(quickSelect.value)
            quickSelect.value = ''
        }
    }

    inputRow.appendChild(input)
    inputRow.appendChild(addBtn)
    inputRow.appendChild(quickSelect)

    container.appendChild(tagsDiv)
    container.appendChild(inputRow)

    renderTags()
    return container
}

/**
 * Initialize the filters section
 * @param {Object} policyData - Current policy data
 * @param {Function} onUpdate - Callback when filter data changes
 * @returns {Object} Controller with methods to get/set state
 */
export function initFiltersSection(policyData, onUpdate) {
    // Get DOM elements
    const audioFilterSection = document.getElementById('audio-filter-section')
    const subtitleFilterSection = document.getElementById('subtitle-filter-section')
    const attachmentFilterSection = document.getElementById('attachment-filter-section')

    if (!audioFilterSection || !subtitleFilterSection || !attachmentFilterSection) {
        console.warn('Filter section elements not found')
        return null
    }

    // Internal state
    let audioFilter = policyData.keep_audio ? { ...policyData.keep_audio } : null
    let subtitleFilter = policyData.keep_subtitles ? { ...policyData.keep_subtitles } : null
    let attachmentFilter = policyData.filter_attachments ? { ...policyData.filter_attachments } : null

    // Track language arrays separately for mutation
    let audioLanguages = audioFilter?.languages ? [...audioFilter.languages] : []
    let subtitleLanguages = subtitleFilter?.languages ? [...subtitleFilter.languages] : []

    function notifyUpdate() {
        onUpdate({
            keep_audio: getAudioFilterConfig(),
            keep_subtitles: getSubtitleFilterConfig(),
            filter_attachments: getAttachmentFilterConfig()
        })
    }

    function getAudioFilterConfig() {
        if (audioLanguages.length === 0) {
            return null
        }

        const config = {
            languages: audioLanguages
        }

        // Add fallback if configured
        const fallbackMode = document.getElementById('audio-fallback-mode')?.value
        if (fallbackMode) {
            config.fallback = { mode: fallbackMode }
        }

        // Add minimum if not default
        const minimum = parseInt(document.getElementById('audio-minimum')?.value || '1', 10)
        if (minimum > 1) {
            config.minimum = minimum
        }

        // V10: Music track options
        const keepMusic = document.getElementById('audio-keep-music')?.checked
        const excludeMusic = document.getElementById('audio-exclude-music')?.checked
        if (keepMusic === false) config.keep_music_tracks = false
        if (excludeMusic === false) config.exclude_music_from_language_filter = false

        // V10: SFX track options
        const keepSfx = document.getElementById('audio-keep-sfx')?.checked
        const excludeSfx = document.getElementById('audio-exclude-sfx')?.checked
        if (keepSfx === false) config.keep_sfx_tracks = false
        if (excludeSfx === false) config.exclude_sfx_from_language_filter = false

        // V10: Non-speech track options
        const keepNonSpeech = document.getElementById('audio-keep-non-speech')?.checked
        const excludeNonSpeech = document.getElementById('audio-exclude-non-speech')?.checked
        if (keepNonSpeech === false) config.keep_non_speech_tracks = false
        if (excludeNonSpeech === false) config.exclude_non_speech_from_language_filter = false

        return config
    }

    function getSubtitleFilterConfig() {
        const removeAll = document.getElementById('subtitle-remove-all')?.checked
        if (removeAll) {
            return { remove_all: true }
        }

        if (subtitleLanguages.length === 0) {
            const preserveForced = document.getElementById('subtitle-preserve-forced')?.checked
            if (preserveForced) {
                return { preserve_forced: true }
            }
            return null
        }

        const config = {
            languages: subtitleLanguages
        }

        const preserveForced = document.getElementById('subtitle-preserve-forced')?.checked
        if (preserveForced) {
            config.preserve_forced = true
        }

        return config
    }

    function getAttachmentFilterConfig() {
        const removeAll = document.getElementById('attachment-remove-all')?.checked
        if (removeAll) {
            return { remove_all: true }
        }
        return null
    }

    function renderAudioFilter() {
        audioFilterSection.innerHTML = `
            <h4 class="accordion-subsection-title">Audio Filter</h4>
            <p class="form-hint">Filter audio tracks by language. At least one track will always be kept.</p>

            <div class="form-group">
                <label class="form-label">Languages to Keep</label>
                <div id="audio-languages-container"></div>
            </div>

            <div class="form-row">
                <div class="form-group">
                    <label for="audio-fallback-mode" class="form-label">Fallback Mode</label>
                    <select id="audio-fallback-mode" class="form-select">
                        ${FALLBACK_MODES.map(mode =>
        `<option value="${mode.value}">${mode.label}</option>`
    ).join('')}
                    </select>
                    <span class="form-hint">Behavior when no tracks match preferred languages</span>
                </div>
                <div class="form-group">
                    <label for="audio-minimum" class="form-label">Minimum Tracks</label>
                    <input type="number" id="audio-minimum" class="form-input form-input-narrow" value="1" min="1" max="99">
                    <span class="form-hint">Minimum audio tracks to keep (default: 1)</span>
                </div>
            </div>

            <div class="accordion-subsection accordion-subsection--spaced">
                <h5 class="accordion-subsection-title accordion-subsection-title--small">V10: Special Track Handling</h5>

                <div class="form-row">
                    <div class="form-group">
                        <label class="checkbox-label">
                            <input type="checkbox" id="audio-keep-music" checked>
                            Keep music tracks
                        </label>
                        <label class="checkbox-label checkbox-label--indented">
                            <input type="checkbox" id="audio-exclude-music" checked>
                            Exclude from language filter
                        </label>
                    </div>
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label class="checkbox-label">
                            <input type="checkbox" id="audio-keep-sfx" checked>
                            Keep SFX tracks
                        </label>
                        <label class="checkbox-label checkbox-label--indented">
                            <input type="checkbox" id="audio-exclude-sfx" checked>
                            Exclude from language filter
                        </label>
                    </div>
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label class="checkbox-label">
                            <input type="checkbox" id="audio-keep-non-speech" checked>
                            Keep non-speech tracks
                        </label>
                        <label class="checkbox-label checkbox-label--indented">
                            <input type="checkbox" id="audio-exclude-non-speech" checked>
                            Exclude from language filter
                        </label>
                    </div>
                </div>
            </div>
        `

        // Add language tags component
        const languagesContainer = document.getElementById('audio-languages-container')
        const tagsComponent = createLanguageTagsComponent(
            audioLanguages,
            (updated) => {
                audioLanguages = updated
                notifyUpdate()
            },
            'audio-language-input'
        )
        languagesContainer.appendChild(tagsComponent)

        // Set initial values
        const fallbackSelect = document.getElementById('audio-fallback-mode')
        if (audioFilter?.fallback?.mode) {
            fallbackSelect.value = audioFilter.fallback.mode
        }

        const minimumInput = document.getElementById('audio-minimum')
        if (audioFilter?.minimum) {
            minimumInput.value = audioFilter.minimum
        }

        // V10 options
        document.getElementById('audio-keep-music').checked =
            audioFilter?.keep_music_tracks !== false
        document.getElementById('audio-exclude-music').checked =
            audioFilter?.exclude_music_from_language_filter !== false
        document.getElementById('audio-keep-sfx').checked =
            audioFilter?.keep_sfx_tracks !== false
        document.getElementById('audio-exclude-sfx').checked =
            audioFilter?.exclude_sfx_from_language_filter !== false
        document.getElementById('audio-keep-non-speech').checked =
            audioFilter?.keep_non_speech_tracks !== false
        document.getElementById('audio-exclude-non-speech').checked =
            audioFilter?.exclude_non_speech_from_language_filter !== false

        // Event listeners
        fallbackSelect.onchange = notifyUpdate
        minimumInput.onchange = notifyUpdate

        // V10 checkboxes
        document.getElementById('audio-keep-music').onchange = notifyUpdate
        document.getElementById('audio-exclude-music').onchange = notifyUpdate
        document.getElementById('audio-keep-sfx').onchange = notifyUpdate
        document.getElementById('audio-exclude-sfx').onchange = notifyUpdate
        document.getElementById('audio-keep-non-speech').onchange = notifyUpdate
        document.getElementById('audio-exclude-non-speech').onchange = notifyUpdate
    }

    function renderSubtitleFilter() {
        subtitleFilterSection.innerHTML = `
            <h4 class="accordion-subsection-title">Subtitle Filter</h4>
            <p class="form-hint">Filter subtitle tracks by language or remove all.</p>

            <div class="form-group">
                <label class="checkbox-label">
                    <input type="checkbox" id="subtitle-remove-all">
                    Remove all subtitle tracks
                </label>
                <span class="form-hint">Overrides other subtitle settings</span>
            </div>

            <div id="subtitle-language-options">
                <div class="form-group">
                    <label class="form-label">Languages to Keep</label>
                    <div id="subtitle-languages-container"></div>
                </div>

                <div class="form-group">
                    <label class="checkbox-label">
                        <input type="checkbox" id="subtitle-preserve-forced">
                        Preserve forced subtitles
                    </label>
                    <span class="form-hint">Keep forced subtitles regardless of language</span>
                </div>
            </div>
        `

        // Add language tags component
        const languagesContainer = document.getElementById('subtitle-languages-container')
        const tagsComponent = createLanguageTagsComponent(
            subtitleLanguages,
            (updated) => {
                subtitleLanguages = updated
                notifyUpdate()
            },
            'subtitle-language-input'
        )
        languagesContainer.appendChild(tagsComponent)

        // Set initial values
        const removeAllCheckbox = document.getElementById('subtitle-remove-all')
        const languageOptions = document.getElementById('subtitle-language-options')
        const preserveForcedCheckbox = document.getElementById('subtitle-preserve-forced')

        removeAllCheckbox.checked = subtitleFilter?.remove_all === true
        preserveForcedCheckbox.checked = subtitleFilter?.preserve_forced === true

        // Toggle language options visibility based on remove_all
        function updateVisibility() {
            languageOptions.style.display = removeAllCheckbox.checked ? 'none' : 'block'
        }
        updateVisibility()

        removeAllCheckbox.onchange = () => {
            updateVisibility()
            notifyUpdate()
        }

        preserveForcedCheckbox.onchange = notifyUpdate
    }

    function renderAttachmentFilter() {
        attachmentFilterSection.innerHTML = `
            <h4 class="accordion-subsection-title">Attachment Filter</h4>
            <p class="form-hint">Configure attachment handling (fonts, cover art, etc.).</p>

            <div class="form-group">
                <label class="checkbox-label">
                    <input type="checkbox" id="attachment-remove-all">
                    Remove all attachments
                </label>
                <span class="form-hint warning-text">Warning: Removing fonts may affect subtitle rendering</span>
            </div>
        `

        const removeAllCheckbox = document.getElementById('attachment-remove-all')
        removeAllCheckbox.checked = attachmentFilter?.remove_all === true

        removeAllCheckbox.onchange = notifyUpdate
    }

    // Initial render
    renderAudioFilter()
    renderSubtitleFilter()
    renderAttachmentFilter()

    // Return controller
    return {
        /**
         * Get current filter configuration
         * @returns {Object} Filter configs (keep_audio, keep_subtitles, filter_attachments)
         */
        getConfig() {
            return {
                keep_audio: getAudioFilterConfig(),
                keep_subtitles: getSubtitleFilterConfig(),
                filter_attachments: getAttachmentFilterConfig()
            }
        },

        /**
         * Set filter configuration
         * @param {Object} config - Filter configs
         */
        setConfig(config) {
            audioFilter = config.keep_audio || null
            subtitleFilter = config.keep_subtitles || null
            attachmentFilter = config.filter_attachments || null

            audioLanguages = audioFilter?.languages ? [...audioFilter.languages] : []
            subtitleLanguages = subtitleFilter?.languages ? [...subtitleFilter.languages] : []

            renderAudioFilter()
            renderSubtitleFilter()
            renderAttachmentFilter()
        },

        /**
         * Refresh the UI with current policy data
         * @param {Object} policyData - Policy data
         */
        refresh(policyData) {
            this.setConfig({
                keep_audio: policyData.keep_audio,
                keep_subtitles: policyData.keep_subtitles,
                filter_attachments: policyData.filter_attachments
            })
        }
    }
}
