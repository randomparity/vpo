/**
 * Audio Synthesis Section Module for Policy Editor (036-v9-policy-editor)
 *
 * Handles audio synthesis track configuration UI.
 * Features:
 * - Synthesis track list with add/remove controls
 * - Track name, codec, channels configuration
 * - Source preference criteria with add/remove
 * - Optional fields: bitrate, title, language, position
 * - Skip if exists criteria (V8: codec, channels, language, not_commentary)
 */

import { showUndoToast } from './policy-editor.js'
import { createConditionBuilder } from './section-conditional.js'

// Constants for synthesis options
const SYNTHESIS_CODECS = [
    { value: 'eac3', label: 'E-AC3 (Dolby Digital Plus)' },
    { value: 'aac', label: 'AAC' },
    { value: 'ac3', label: 'AC3 (Dolby Digital)' },
    { value: 'opus', label: 'Opus' },
    { value: 'flac', label: 'FLAC (Lossless)' }
]

const CHANNEL_CONFIGS = [
    { value: 2, label: 'Stereo (2.0)' },
    { value: 6, label: '5.1 (6 channels)' },
    { value: 8, label: '7.1 (8 channels)' },
    { value: 'mono', label: 'Mono' },
    { value: 'stereo', label: 'Stereo' },
    { value: 'downmix', label: 'Downmix from source' }
]

const POSITION_OPTIONS = [
    { value: 'end', label: 'End of track list' },
    { value: 'after_source', label: 'After source track' },
    { value: '0', label: 'Position 0' },
    { value: '1', label: 'Position 1' },
    { value: '2', label: 'Position 2' }
]

const COMPARISON_OPERATORS = [
    { value: 'eq', label: '= (equals)' },
    { value: 'lt', label: '< (less than)' },
    { value: 'lte', label: '<= (less or equal)' },
    { value: 'gt', label: '> (greater than)' },
    { value: 'gte', label: '>= (greater or equal)' }
]

const SOURCE_PREFER_FIELDS = [
    { value: 'language', label: 'Language' },
    { value: 'not_commentary', label: 'Not Commentary' },
    { value: 'channels', label: 'Channel Count' },
    { value: 'codec', label: 'Codec' }
]

/**
 * Validate synthesis track name
 * @param {string} name - Track name to validate
 * @returns {boolean} True if valid
 */
function isValidTrackName(name) {
    if (!name || name.trim().length === 0) return false
    // No path separators allowed
    if (name.includes('/') || name.includes('\\')) return false
    return true
}

/**
 * Create a source preference criteria builder
 * @param {Array} sourcePrefer - Current source_prefer array
 * @param {Function} onUpdate - Callback when preferences change
 * @returns {HTMLElement} Source preference container
 */
function createSourcePreferBuilder(sourcePrefer, onUpdate) {
    const container = document.createElement('div')
    container.className = 'source-prefer-builder'

    const prefsData = sourcePrefer ? [...sourcePrefer] : []

    function render() {
        container.innerHTML = `
            <div class="source-prefer-header">
                <span class="source-prefer-label">Source Preference Criteria:</span>
                <button type="button" class="btn-secondary btn-small add-pref-btn">Add Criterion</button>
            </div>
            <div class="source-prefer-list"></div>
        `

        const listDiv = container.querySelector('.source-prefer-list')
        const addBtn = container.querySelector('.add-pref-btn')

        if (prefsData.length === 0) {
            const empty = document.createElement('p')
            empty.className = 'source-prefer-empty'
            empty.textContent = 'No source preferences. First matching audio track will be used.'
            listDiv.appendChild(empty)
        } else {
            prefsData.forEach((pref, idx) => {
                const item = document.createElement('div')
                item.className = 'source-prefer-item'

                // Determine the type of preference
                let prefType = 'language'
                if (pref.not_commentary !== undefined) prefType = 'not_commentary'
                else if (pref.channels !== undefined) prefType = 'channels'
                else if (pref.codec !== undefined) prefType = 'codec'
                else if (pref.language !== undefined) prefType = 'language'

                item.innerHTML = `
                    <select class="form-select form-select-small pref-type-select">
                        ${SOURCE_PREFER_FIELDS.map(f => `<option value="${f.value}" ${prefType === f.value ? 'selected' : ''}>${f.label}</option>`).join('')}
                    </select>
                    <div class="pref-value-container"></div>
                    <button type="button" class="btn-icon btn-remove-pref" title="Remove">\u00d7</button>
                `

                const typeSelect = item.querySelector('.pref-type-select')
                const valueContainer = item.querySelector('.pref-value-container')
                const removeBtn = item.querySelector('.btn-remove-pref')

                function renderValue() {
                    const type = typeSelect.value
                    valueContainer.innerHTML = ''

                    if (type === 'language') {
                        const input = document.createElement('input')
                        input.type = 'text'
                        input.className = 'form-input form-input-small'
                        input.placeholder = 'e.g., eng, jpn'
                        input.value = pref.language || ''
                        input.addEventListener('input', () => {
                            pref.language = input.value.trim()
                            delete pref.not_commentary
                            delete pref.channels
                            delete pref.codec
                            onUpdate([...prefsData])
                        })
                        valueContainer.appendChild(input)
                    } else if (type === 'not_commentary') {
                        const checkbox = document.createElement('input')
                        checkbox.type = 'checkbox'
                        checkbox.checked = pref.not_commentary !== false
                        checkbox.addEventListener('change', () => {
                            pref.not_commentary = checkbox.checked
                            delete pref.language
                            delete pref.channels
                            delete pref.codec
                            onUpdate([...prefsData])
                        })
                        const label = document.createElement('label')
                        label.className = 'checkbox-label'
                        label.appendChild(checkbox)
                        label.appendChild(document.createTextNode(' Exclude commentary'))
                        valueContainer.appendChild(label)
                    } else if (type === 'channels') {
                        const opSelect = document.createElement('select')
                        opSelect.className = 'form-select form-select-small'
                        opSelect.innerHTML = COMPARISON_OPERATORS.map(op => `<option value="${op.value}">${op.label}</option>`).join('')
                        if (typeof pref.channels === 'object' && pref.channels.operator) {
                            opSelect.value = pref.channels.operator
                        }

                        const input = document.createElement('input')
                        input.type = 'number'
                        input.className = 'form-input form-input-small'
                        input.placeholder = 'e.g., 6'
                        input.min = 1
                        input.max = 32
                        if (typeof pref.channels === 'object' && pref.channels.value) {
                            input.value = pref.channels.value
                        } else if (typeof pref.channels === 'number') {
                            input.value = pref.channels
                        }

                        const updateChannels = () => {
                            pref.channels = { operator: opSelect.value, value: parseInt(input.value, 10) || 2 }
                            delete pref.language
                            delete pref.not_commentary
                            delete pref.codec
                            onUpdate([...prefsData])
                        }

                        opSelect.addEventListener('change', updateChannels)
                        input.addEventListener('input', updateChannels)

                        valueContainer.appendChild(opSelect)
                        valueContainer.appendChild(input)
                    } else if (type === 'codec') {
                        const input = document.createElement('input')
                        input.type = 'text'
                        input.className = 'form-input form-input-small'
                        input.placeholder = 'e.g., truehd, dts-hd'
                        input.value = pref.codec || ''
                        input.addEventListener('input', () => {
                            pref.codec = input.value.trim()
                            delete pref.language
                            delete pref.not_commentary
                            delete pref.channels
                            onUpdate([...prefsData])
                        })
                        valueContainer.appendChild(input)
                    }
                }

                typeSelect.addEventListener('change', () => {
                    // Clear old values
                    delete pref.language
                    delete pref.not_commentary
                    delete pref.channels
                    delete pref.codec
                    renderValue()
                    onUpdate([...prefsData])
                })

                removeBtn.setAttribute('aria-label', 'Remove this source preference')
                removeBtn.addEventListener('click', () => {
                    // H3: Undo toast for source preference removal
                    const removedPref = prefsData.splice(idx, 1)[0]
                    const removedIdx = idx
                    render()
                    onUpdate([...prefsData])

                    showUndoToast('Source preference removed', () => {
                        prefsData.splice(removedIdx, 0, removedPref)
                        render()
                        onUpdate([...prefsData])
                    })
                })

                renderValue()
                listDiv.appendChild(item)
            })
        }

        addBtn.addEventListener('click', () => {
            prefsData.push({ language: '' })
            render()
            onUpdate([...prefsData])

            // H1: Focus management - focus the new preference's type select
            const typeSelects = listDiv.querySelectorAll('.pref-type-select')
            const lastSelect = typeSelects[typeSelects.length - 1]
            if (lastSelect) {
                lastSelect.focus()
            }
        })
    }

    render()
    return container
}

/**
 * Create skip_if_exists criteria builder
 * @param {Object} skipIfExists - Current skip_if_exists criteria
 * @param {Function} onUpdate - Callback when criteria change
 * @returns {HTMLElement} Skip if exists container
 */
function createSkipIfExistsBuilder(skipIfExists, onUpdate) {
    const container = document.createElement('div')
    container.className = 'skip-if-exists-builder'

    const criteria = skipIfExists ? { ...skipIfExists } : null

    function render() {
        container.innerHTML = `
            <div class="skip-if-exists-header">
                <label class="checkbox-label">
                    <input type="checkbox" class="skip-enabled-checkbox" ${criteria ? 'checked' : ''}>
                    Skip if matching track exists (V8)
                </label>
            </div>
            <div class="skip-if-exists-fields${criteria ? '' : ' initially-hidden'}">
                <div class="filter-row">
                    <label class="form-label-inline">Codec:</label>
                    <input type="text" class="form-input form-input-small skip-codec" placeholder="e.g., aac, ac3" value="${criteria?.codec || ''}">
                </div>
                <div class="filter-row">
                    <label class="form-label-inline">Channels:</label>
                    <select class="form-select form-select-small skip-chan-op">
                        <option value="">Any</option>
                        ${COMPARISON_OPERATORS.map(op => `<option value="${op.value}">${op.label}</option>`).join('')}
                    </select>
                    <input type="number" class="form-input form-input-small skip-chan-val" placeholder="e.g., 2" min="1" max="32" value="${criteria?.channels?.value || ''}">
                </div>
                <div class="filter-row">
                    <label class="form-label-inline">Language:</label>
                    <input type="text" class="form-input form-input-small skip-language" placeholder="e.g., eng" value="${criteria?.language || ''}">
                </div>
                <div class="filter-row">
                    <label class="checkbox-label">
                        <input type="checkbox" class="skip-not-commentary" ${criteria?.not_commentary ? 'checked' : ''}>
                        Not Commentary
                    </label>
                </div>
            </div>
        `

        const enabledCheckbox = container.querySelector('.skip-enabled-checkbox')
        const fieldsDiv = container.querySelector('.skip-if-exists-fields')

        enabledCheckbox.addEventListener('change', () => {
            fieldsDiv.style.display = enabledCheckbox.checked ? 'block' : 'none'
            if (!enabledCheckbox.checked) {
                onUpdate(null)
            } else {
                collectCriteria()
            }
        })

        function collectCriteria() {
            if (!enabledCheckbox.checked) {
                onUpdate(null)
                return
            }

            const result = {}
            const codec = container.querySelector('.skip-codec').value.trim()
            if (codec) {
                const codecs = codec.split(',').map(c => c.trim()).filter(Boolean)
                result.codec = codecs.length === 1 ? codecs[0] : codecs
            }

            const chanOp = container.querySelector('.skip-chan-op').value
            const chanVal = container.querySelector('.skip-chan-val').value
            if (chanOp && chanVal) {
                result.channels = { operator: chanOp, value: parseInt(chanVal, 10) }
            }

            const language = container.querySelector('.skip-language').value.trim()
            if (language) {
                const langs = language.split(',').map(l => l.trim()).filter(Boolean)
                result.language = langs.length === 1 ? langs[0] : langs
            }

            if (container.querySelector('.skip-not-commentary').checked) {
                result.not_commentary = true
            }

            onUpdate(Object.keys(result).length > 0 ? result : null)
        }

        // Attach listeners
        container.querySelectorAll('input, select').forEach(el => {
            el.addEventListener('change', collectCriteria)
            el.addEventListener('input', collectCriteria)
        })

        // Set initial operator value
        if (criteria?.channels?.operator) {
            container.querySelector('.skip-chan-op').value = criteria.channels.operator
        }
    }

    render()
    return container
}

/**
 * Create a synthesis track builder component
 * @param {Object} track - Track definition
 * @param {Function} onUpdate - Callback when track changes
 * @param {Function} onRemove - Callback to remove track
 * @param {number} trackIndex - Index of this track for generating unique IDs (B2)
 * @returns {HTMLElement} Track builder container
 */
function createSynthesisTrackBuilder(track, onUpdate, onRemove, trackIndex = 0) {
    const container = document.createElement('div')
    container.className = 'synthesis-track-builder'

    // Generate unique IDs for this track instance (B2: label associations)
    const idPrefix = `synth-track-${trackIndex}`

    const trackData = track ? { ...track } : {
        name: 'New Synthesis Track',
        codec: 'aac',
        channels: 2,
        source_prefer: [],
        title: 'inherit',
        language: 'inherit',
        position: 'end'
    }

    function render() {
        container.innerHTML = `
            <div class="track-header">
                <label for="${idPrefix}-name" class="sr-only">Track name</label>
                <input type="text" id="${idPrefix}-name" class="form-input track-name-input" placeholder="Track name" value="${trackData.name || ''}"
                       aria-label="Synthesis track name">
                <button type="button" class="btn-icon btn-remove-track" title="Remove track" aria-label="Remove this synthesis track">\u00d7</button>
            </div>
            <div class="track-main-fields">
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label" for="${idPrefix}-codec">Codec</label>
                        <select id="${idPrefix}-codec" class="form-select track-codec-select">
                            ${SYNTHESIS_CODECS.map(c => `<option value="${c.value}" ${trackData.codec === c.value ? 'selected' : ''}>${c.label}</option>`).join('')}
                        </select>
                    </div>
                    <div class="form-group">
                        <label class="form-label" for="${idPrefix}-channels">Channels</label>
                        <select id="${idPrefix}-channels" class="form-select track-channels-select">
                            ${CHANNEL_CONFIGS.map(c => `<option value="${c.value}" ${String(trackData.channels) === String(c.value) ? 'selected' : ''}>${c.label}</option>`).join('')}
                        </select>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label" for="${idPrefix}-bitrate">Bitrate (optional)</label>
                        <input type="text" id="${idPrefix}-bitrate" class="form-input track-bitrate" placeholder="e.g., 640k, 192k" value="${trackData.bitrate || ''}">
                    </div>
                    <div class="form-group">
                        <label class="form-label" for="${idPrefix}-position">Position</label>
                        <select id="${idPrefix}-position" class="form-select track-position-select">
                            ${POSITION_OPTIONS.map(p => `<option value="${p.value}" ${String(trackData.position) === String(p.value) ? 'selected' : ''}>${p.label}</option>`).join('')}
                        </select>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label" for="${idPrefix}-title">Title</label>
                        <input type="text" id="${idPrefix}-title" class="form-input track-title" placeholder="inherit" value="${trackData.title === 'inherit' ? '' : trackData.title || ''}">
                        <span class="form-hint">Leave empty for 'inherit'</span>
                    </div>
                    <div class="form-group">
                        <label class="form-label" for="${idPrefix}-language">Language</label>
                        <input type="text" id="${idPrefix}-language" class="form-input track-language" placeholder="inherit" value="${trackData.language === 'inherit' ? '' : trackData.language || ''}">
                        <span class="form-hint">Leave empty for 'inherit'</span>
                    </div>
                </div>
            </div>
            <div class="source-prefer-container"></div>
            <div class="skip-if-exists-container"></div>
            <div class="create-if-container"></div>
        `

        // Attach main field listeners
        const nameInput = container.querySelector('.track-name-input')
        const codecSelect = container.querySelector('.track-codec-select')
        const channelsSelect = container.querySelector('.track-channels-select')
        const bitrateInput = container.querySelector('.track-bitrate')
        const positionSelect = container.querySelector('.track-position-select')
        const titleInput = container.querySelector('.track-title')
        const languageInput = container.querySelector('.track-language')
        const removeBtn = container.querySelector('.btn-remove-track')

        nameInput.addEventListener('input', () => {
            if (!isValidTrackName(nameInput.value)) {
                nameInput.setCustomValidity('Invalid track name')
            } else {
                nameInput.setCustomValidity('')
            }
            trackData.name = nameInput.value.trim()
            onUpdate(buildTrack())
        })

        codecSelect.addEventListener('change', () => {
            trackData.codec = codecSelect.value
            onUpdate(buildTrack())
        })

        channelsSelect.addEventListener('change', () => {
            const val = channelsSelect.value
            trackData.channels = isNaN(parseInt(val, 10)) ? val : parseInt(val, 10)
            onUpdate(buildTrack())
        })

        bitrateInput.addEventListener('input', () => {
            trackData.bitrate = bitrateInput.value.trim() || null
            onUpdate(buildTrack())
        })

        positionSelect.addEventListener('change', () => {
            const val = positionSelect.value
            trackData.position = isNaN(parseInt(val, 10)) ? val : parseInt(val, 10)
            onUpdate(buildTrack())
        })

        titleInput.addEventListener('input', () => {
            trackData.title = titleInput.value.trim() || 'inherit'
            onUpdate(buildTrack())
        })

        languageInput.addEventListener('input', () => {
            trackData.language = languageInput.value.trim() || 'inherit'
            onUpdate(buildTrack())
        })

        removeBtn.addEventListener('click', onRemove)

        // Source prefer builder
        const sourcePreferContainer = container.querySelector('.source-prefer-container')
        const sourcePreferBuilder = createSourcePreferBuilder(trackData.source_prefer || [], (updated) => {
            trackData.source_prefer = updated
            onUpdate(buildTrack())
        })
        sourcePreferContainer.appendChild(sourcePreferBuilder)

        // Skip if exists builder
        const skipContainer = container.querySelector('.skip-if-exists-container')
        const skipBuilder = createSkipIfExistsBuilder(trackData.skip_if_exists, (updated) => {
            trackData.skip_if_exists = updated
            onUpdate(buildTrack())
        })
        skipContainer.appendChild(skipBuilder)

        // Create-if condition builder
        const createIfContainer = container.querySelector('.create-if-container')
        const createIfWrapper = document.createElement('div')
        createIfWrapper.className = 'create-if-builder'

        const createIfHeader = document.createElement('div')
        createIfHeader.className = 'create-if-header'

        const createIfCheckbox = document.createElement('input')
        createIfCheckbox.type = 'checkbox'
        createIfCheckbox.checked = !!trackData.create_if
        createIfCheckbox.id = `${idPrefix}-create-if-enabled`

        const createIfLabel = document.createElement('label')
        createIfLabel.className = 'checkbox-label'
        createIfLabel.appendChild(createIfCheckbox)
        createIfLabel.appendChild(document.createTextNode(' Only create if condition is met'))

        createIfHeader.appendChild(createIfLabel)
        createIfWrapper.appendChild(createIfHeader)

        const createIfBody = document.createElement('div')
        createIfBody.className = 'create-if-body'
        createIfBody.style.display = trackData.create_if ? 'block' : 'none'
        createIfWrapper.appendChild(createIfBody)

        if (trackData.create_if) {
            const condBuilder = createConditionBuilder(
                trackData.create_if,
                (updated) => {
                    trackData.create_if = updated
                    onUpdate(buildTrack())
                },
                0
            )
            createIfBody.appendChild(condBuilder)
        }

        createIfCheckbox.addEventListener('change', () => {
            if (createIfCheckbox.checked) {
                trackData.create_if = { track_type: 'audio' }
                createIfBody.style.display = 'block'
                createIfBody.innerHTML = ''
                const condBuilder = createConditionBuilder(
                    trackData.create_if,
                    (updated) => {
                        trackData.create_if = updated
                        onUpdate(buildTrack())
                    },
                    0
                )
                createIfBody.appendChild(condBuilder)
            } else {
                trackData.create_if = null
                createIfBody.style.display = 'none'
                createIfBody.innerHTML = ''
            }
            onUpdate(buildTrack())
        })

        createIfContainer.appendChild(createIfWrapper)
    }

    function buildTrack() {
        const result = {
            name: trackData.name || 'Unnamed Track',
            codec: trackData.codec || 'aac',
            channels: trackData.channels || 2,
            source_prefer: trackData.source_prefer || []
        }

        if (trackData.bitrate) {
            result.bitrate = trackData.bitrate
        }

        if (trackData.title && trackData.title !== 'inherit') {
            result.title = trackData.title
        }

        if (trackData.language && trackData.language !== 'inherit') {
            result.language = trackData.language
        }

        if (trackData.position && trackData.position !== 'end') {
            result.position = trackData.position
        }

        if (trackData.skip_if_exists) {
            result.skip_if_exists = trackData.skip_if_exists
        }

        if (trackData.create_if) {
            result.create_if = trackData.create_if
        }

        return result
    }

    render()
    return container
}

/**
 * Initialize the audio synthesis section
 * @param {Object} policyData - Current policy data
 * @param {Function} onUpdate - Callback when synthesis config changes
 * @returns {Object} Controller with methods to get/set state
 */
export function initSynthesisSection(policyData, onUpdate) {
    const tracksListEl = document.getElementById('synthesis-tracks-list')
    const addTrackBtn = document.getElementById('add-synthesis-track-btn')

    if (!tracksListEl || !addTrackBtn) {
        console.warn('Synthesis section elements not found')
        return null
    }

    // Internal state - transform from API format
    let tracks = []
    if (policyData.audio_synthesis) {
        if (Array.isArray(policyData.audio_synthesis)) {
            tracks = [...policyData.audio_synthesis]
        } else if (policyData.audio_synthesis.tracks) {
            tracks = [...policyData.audio_synthesis.tracks]
        }
    }

    function notifyUpdate() {
        // Return as array format (the API expects audio_synthesis as array of tracks)
        onUpdate(tracks.length > 0 ? [...tracks] : null)
    }

    function renderTracks() {
        tracksListEl.innerHTML = ''

        if (tracks.length === 0) {
            const empty = document.createElement('p')
            empty.className = 'accordion-list-empty'
            empty.textContent = 'No audio synthesis tracks configured.'
            tracksListEl.appendChild(empty)
            return
        }

        tracks.forEach((track, idx) => {
            const trackBuilder = createSynthesisTrackBuilder(
                track,
                (updated) => {
                    tracks[idx] = updated
                    notifyUpdate()
                },
                () => {
                    // H3: Undo toast for track removal
                    const removedTrack = tracks.splice(idx, 1)[0]
                    const removedIdx = idx
                    renderTracks()
                    notifyUpdate()

                    showUndoToast('Synthesis track removed', () => {
                        tracks.splice(removedIdx, 0, removedTrack)
                        renderTracks()
                        notifyUpdate()
                    })
                },
                idx // B2: Pass track index for unique IDs
            )
            tracksListEl.appendChild(trackBuilder)
        })
    }

    // Add track button handler
    addTrackBtn.addEventListener('click', () => {
        tracks.push({
            name: `Synthesis Track ${tracks.length + 1}`,
            codec: 'aac',
            channels: 2,
            source_prefer: []
        })
        renderTracks()
        notifyUpdate()

        // H1: Focus management - focus the newly added track's name input
        const inputs = tracksListEl.querySelectorAll('.track-name-input')
        const lastInput = inputs[inputs.length - 1]
        if (lastInput) {
            lastInput.focus()
            lastInput.select()
        }
    })

    // Initial render
    renderTracks()

    // Return controller
    return {
        /**
         * Get current audio synthesis configuration
         * @returns {Array|null} Audio synthesis tracks array or null if empty
         */
        getConfig() {
            return tracks.length > 0 ? [...tracks] : null
        },

        /**
         * Set audio synthesis configuration
         * @param {Array|Object|null} config - Audio synthesis config
         */
        setConfig(config) {
            if (Array.isArray(config)) {
                tracks = [...config]
            } else if (config?.tracks) {
                tracks = [...config.tracks]
            } else {
                tracks = []
            }
            renderTracks()
        },

        /**
         * Refresh the UI with current policy data
         * @param {Object} policyData - Policy data
         */
        refresh(policyData) {
            if (policyData.audio_synthesis) {
                if (Array.isArray(policyData.audio_synthesis)) {
                    tracks = [...policyData.audio_synthesis]
                } else if (policyData.audio_synthesis.tracks) {
                    tracks = [...policyData.audio_synthesis.tracks]
                } else {
                    tracks = []
                }
            } else {
                tracks = []
            }
            renderTracks()
        }
    }
}
