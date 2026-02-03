/**
 * V11 Phases Section Module for Policy Editor (037-user-defined-phases)
 *
 * Handles user-defined phases configuration UI for V11 policies.
 * Features:
 * - Add/remove phases with custom names
 * - Configure operations per phase
 * - Drag-and-drop phase reordering
 * - Real-time YAML preview updates
 *
 * Operation types in canonical order:
 * container, audio_filter, subtitle_filter, attachment_filter,
 * track_order, default_flags, conditional, audio_synthesis, transcode,
 * transcription, file_timestamp
 */

// Valid operation types in canonical execution order
const OPERATION_TYPES = [
    { id: 'container', label: 'Container Conversion', description: 'Convert container format' },
    { id: 'audio_filter', label: 'Audio Filter', description: 'Filter audio tracks by language' },
    { id: 'subtitle_filter', label: 'Subtitle Filter', description: 'Filter subtitle tracks by language' },
    { id: 'attachment_filter', label: 'Attachment Filter', description: 'Remove attachments' },
    { id: 'track_order', label: 'Track Ordering', description: 'Reorder tracks by type' },
    { id: 'default_flags', label: 'Default Flags', description: 'Set default track flags' },
    { id: 'conditional', label: 'Conditional Rules', description: 'Apply conditional logic' },
    { id: 'audio_synthesis', label: 'Audio Synthesis', description: 'Create synthesized audio tracks' },
    { id: 'transcode', label: 'Transcode', description: 'Transcode video/audio' },
    { id: 'transcription', label: 'Transcription', description: 'Transcription analysis' },
    { id: 'file_timestamp', label: 'File Timestamp', description: 'Set file modification timestamp' }
]

const RESOLUTION_OPTIONS = [
    { value: '', label: '-- None --' },
    { value: '480p', label: '480p' },
    { value: '720p', label: '720p' },
    { value: '1080p', label: '1080p' },
    { value: '1440p', label: '1440p' },
    { value: '4k', label: '4K' },
    { value: '8k', label: '8K' }
]

const ON_ERROR_OPTIONS = [
    { value: '', label: '(inherit global)' },
    { value: 'skip', label: 'Skip' },
    { value: 'continue', label: 'Continue' },
    { value: 'fail', label: 'Fail' }
]

/**
 * Escape a string for safe interpolation into HTML attribute values.
 */
function escapeAttr(str) {
    if (!str && str !== 0) return ''
    const div = document.createElement('div')
    div.textContent = str
    return div.innerHTML
}

// Phase name validation pattern (same as backend)
const PHASE_NAME_PATTERN = /^[a-zA-Z][a-zA-Z0-9_-]{0,63}$/
const RESERVED_NAMES = ['config', 'schema_version', 'phases']

/**
 * Initialize the V11 phases section
 * @param {Object} policyData - Current policy data
 * @param {Function} onUpdate - Callback when phases config changes
 * @returns {Object|null} Controller with methods to get/set state, or null if not V11
 */
export function initPhasesSection(policyData, onUpdate) {
    const container = document.getElementById('phases-section-container')
    const phasesList = document.getElementById('phases-list')
    const addPhaseBtn = document.getElementById('add-phase-btn')
    const configOnError = document.getElementById('config-on-error')

    // Only activate for V11 policies
    if (!container || policyData.schema_version !== 11) {
        return null
    }

    // Internal state
    let phases = policyData.phases ? JSON.parse(JSON.stringify(policyData.phases)) : []
    let config = policyData.config ? { ...policyData.config } : {}

    // Track drag state
    let draggedItem = null

    function notifyUpdate() {
        onUpdate(getConfig())
    }

    function getConfig() {
        return {
            phases: phases.length > 0 ? phases : null,
            config: Object.keys(config).length > 0 ? config : null
        }
    }

    function validatePhaseName(name, excludeIndex = -1) {
        if (!name || !name.trim()) {
            return 'Phase name is required'
        }
        if (!PHASE_NAME_PATTERN.test(name)) {
            return 'Phase name must start with a letter and contain only letters, numbers, hyphens, or underscores (max 64 chars)'
        }
        if (RESERVED_NAMES.includes(name.toLowerCase())) {
            return `'${name}' is a reserved name`
        }
        // Check for duplicates
        const duplicate = phases.find((p, i) => i !== excludeIndex && p.name === name)
        if (duplicate) {
            return `Phase '${name}' already exists`
        }
        return null
    }

    function createPhaseElement(phase, index) {
        const div = document.createElement('div')
        div.className = 'phase-item'
        div.dataset.index = index
        div.draggable = true

        // Phase header with name and controls
        const header = document.createElement('div')
        header.className = 'phase-item-header'

        const dragHandle = document.createElement('span')
        dragHandle.className = 'phase-drag-handle'
        dragHandle.innerHTML = '⋮⋮'
        dragHandle.title = 'Drag to reorder'
        dragHandle.setAttribute('aria-label', 'Drag handle')

        const nameInput = document.createElement('input')
        nameInput.type = 'text'
        nameInput.className = 'phase-name-input'
        nameInput.value = phase.name || ''
        nameInput.placeholder = 'Phase name'
        nameInput.setAttribute('aria-label', 'Phase name')

        const deleteBtn = document.createElement('button')
        deleteBtn.type = 'button'
        deleteBtn.className = 'phase-delete-btn'
        deleteBtn.innerHTML = '&times;'
        deleteBtn.title = 'Delete phase'
        deleteBtn.setAttribute('aria-label', 'Delete phase')

        header.appendChild(dragHandle)
        header.appendChild(nameInput)
        header.appendChild(deleteBtn)

        // Operations section
        const opsSection = document.createElement('div')
        opsSection.className = 'phase-operations'

        const opsLabel = document.createElement('span')
        opsLabel.className = 'phase-operations-label'
        opsLabel.textContent = 'Operations:'

        const opsGrid = document.createElement('div')
        opsGrid.className = 'phase-operations-grid'

        OPERATION_TYPES.forEach(op => {
            const label = document.createElement('label')
            label.className = 'phase-operation-checkbox'
            label.title = op.description

            const checkbox = document.createElement('input')
            checkbox.type = 'checkbox'
            checkbox.name = `phase-${index}-op-${op.id}`
            checkbox.value = op.id
            checkbox.checked = hasOperation(phase, op.id)

            const span = document.createElement('span')
            span.textContent = op.label

            label.appendChild(checkbox)
            label.appendChild(span)
            opsGrid.appendChild(label)

            // Operation checkbox change
            checkbox.addEventListener('change', () => {
                updatePhaseOperation(index, op.id, checkbox.checked)
                notifyUpdate()
            })
        })

        opsSection.appendChild(opsLabel)
        opsSection.appendChild(opsGrid)

        div.appendChild(header)
        div.appendChild(opsSection)

        // Audio/Subtitle pre-processing actions section
        const actionsSection = document.createElement('div')
        actionsSection.className = 'phase-track-actions'

        const actionsToggle = document.createElement('details')
        actionsToggle.className = 'phase-cond-details'
        if (phase.audio_actions || phase.subtitle_actions) {
            actionsToggle.open = true
        }

        const actionsSummary = document.createElement('summary')
        actionsSummary.className = 'phase-cond-summary'
        actionsSummary.textContent = 'Track Pre-Processing Actions'

        const actionsContent = document.createElement('div')
        actionsContent.className = 'phase-cond-content'
        actionsContent.innerHTML = `
            <div class="phase-cond-group">
                <label class="form-label">Audio Actions:</label>
                <div class="checkbox-group">
                    <label class="checkbox-label">
                        <input type="checkbox" class="audio-clear-forced" ${phase.audio_actions?.clear_all_forced ? 'checked' : ''}>
                        <span>Clear all forced flags</span>
                    </label>
                    <label class="checkbox-label">
                        <input type="checkbox" class="audio-clear-default" ${phase.audio_actions?.clear_all_default ? 'checked' : ''}>
                        <span>Clear all default flags</span>
                    </label>
                    <label class="checkbox-label">
                        <input type="checkbox" class="audio-clear-titles" ${phase.audio_actions?.clear_all_titles ? 'checked' : ''}>
                        <span>Clear all titles</span>
                    </label>
                </div>
            </div>
            <div class="phase-cond-group">
                <label class="form-label">Subtitle Actions:</label>
                <div class="checkbox-group">
                    <label class="checkbox-label">
                        <input type="checkbox" class="sub-clear-forced" ${phase.subtitle_actions?.clear_all_forced ? 'checked' : ''}>
                        <span>Clear all forced flags</span>
                    </label>
                    <label class="checkbox-label">
                        <input type="checkbox" class="sub-clear-default" ${phase.subtitle_actions?.clear_all_default ? 'checked' : ''}>
                        <span>Clear all default flags</span>
                    </label>
                    <label class="checkbox-label">
                        <input type="checkbox" class="sub-clear-titles" ${phase.subtitle_actions?.clear_all_titles ? 'checked' : ''}>
                        <span>Clear all titles</span>
                    </label>
                </div>
            </div>
        `

        function collectAudioActions() {
            const actions = {}
            if (actionsContent.querySelector('.audio-clear-forced').checked) actions.clear_all_forced = true
            if (actionsContent.querySelector('.audio-clear-default').checked) actions.clear_all_default = true
            if (actionsContent.querySelector('.audio-clear-titles').checked) actions.clear_all_titles = true
            phases[index].audio_actions = Object.keys(actions).length > 0 ? actions : null
            notifyUpdate()
        }

        function collectSubtitleActions() {
            const actions = {}
            if (actionsContent.querySelector('.sub-clear-forced').checked) actions.clear_all_forced = true
            if (actionsContent.querySelector('.sub-clear-default').checked) actions.clear_all_default = true
            if (actionsContent.querySelector('.sub-clear-titles').checked) actions.clear_all_titles = true
            phases[index].subtitle_actions = Object.keys(actions).length > 0 ? actions : null
            notifyUpdate()
        }

        actionsContent.querySelectorAll('[class^="audio-clear"]').forEach(el => {
            el.addEventListener('change', collectAudioActions)
        })
        actionsContent.querySelectorAll('[class^="sub-clear"]').forEach(el => {
            el.addEventListener('change', collectSubtitleActions)
        })

        actionsToggle.appendChild(actionsSummary)
        actionsToggle.appendChild(actionsContent)
        actionsSection.appendChild(actionsToggle)
        div.appendChild(actionsSection)

        // Conditional execution section
        const condExecSection = document.createElement('div')
        condExecSection.className = 'phase-conditional-execution'

        const condExecToggle = document.createElement('details')
        condExecToggle.className = 'phase-cond-details'

        const condExecSummary = document.createElement('summary')
        condExecSummary.className = 'phase-cond-summary'
        condExecSummary.textContent = 'Conditional Execution'
        // Auto-open if phase has any conditional fields
        if (phase.skip_when || phase.depends_on || phase.run_if || phase.on_error) {
            condExecToggle.open = true
        }

        const condExecContent = document.createElement('div')
        condExecContent.className = 'phase-cond-content'

        // Other phase names available for reference (reserved for future dropdown enhancement)
        const _otherPhaseNames = phases
            .filter((_, i) => i !== index)
            .map(p => p.name)
            .filter(Boolean)

        condExecContent.innerHTML = `
            <div class="phase-cond-group">
                <label class="form-label">Per-Phase On Error:</label>
                <select class="form-select form-select-small phase-on-error-select">
                    ${ON_ERROR_OPTIONS.map(o => `<option value="${o.value}" ${(phase.on_error || '') === o.value ? 'selected' : ''}>${o.label}</option>`).join('')}
                </select>
            </div>
            <div class="phase-cond-group">
                <label class="form-label">Depends On:</label>
                <input type="text" class="form-input form-input-small phase-depends-on"
                       placeholder="Comma-separated phase names"
                       value="${escapeAttr((phase.depends_on || []).join(', '))}">
                <span class="form-hint">Phase names that must complete before this runs</span>
            </div>
            <div class="phase-cond-group">
                <label class="form-label">Run If:</label>
                <select class="form-select form-select-small phase-run-if-type">
                    <option value="">Always run</option>
                    <option value="phase_modified" ${phase.run_if?.phase_modified ? 'selected' : ''}>Phase modified file</option>
                    <option value="phase_completed" ${phase.run_if?.phase_completed ? 'selected' : ''}>Phase completed</option>
                </select>
                <input type="text" class="form-input form-input-small phase-run-if-value"
                       placeholder="Phase name"
                       value="${escapeAttr(phase.run_if?.phase_modified || phase.run_if?.phase_completed || '')}"
                       style="display: ${phase.run_if ? 'inline-block' : 'none'}">
            </div>
            <div class="phase-cond-group">
                <label class="form-label">Skip When:</label>
                <div class="skip-when-fields">
                    <div class="filter-row">
                        <label class="form-label-inline">Video Codec:</label>
                        <input type="text" class="form-input form-input-small skip-when-video-codec"
                               placeholder="e.g., hevc, h265"
                               value="${escapeAttr((phase.skip_when?.video_codec || []).join(', '))}">
                    </div>
                    <div class="filter-row">
                        <label class="form-label-inline">Audio Codec Exists:</label>
                        <input type="text" class="form-input form-input-small skip-when-audio-codec"
                               placeholder="e.g., truehd"
                               value="${escapeAttr(phase.skip_when?.audio_codec_exists || '')}">
                    </div>
                    <div class="filter-row">
                        <label class="form-label-inline">Container:</label>
                        <input type="text" class="form-input form-input-small skip-when-container"
                               placeholder="e.g., mkv, mp4"
                               value="${escapeAttr((phase.skip_when?.container || []).join(', '))}">
                    </div>
                    <div class="filter-row">
                        <label class="form-label-inline">Resolution Under:</label>
                        <select class="form-select form-select-small skip-when-resolution">
                            ${RESOLUTION_OPTIONS.map(r => `<option value="${r.value}" ${phase.skip_when?.resolution_under === r.value ? 'selected' : ''}>${r.label}</option>`).join('')}
                        </select>
                    </div>
                    <div class="filter-row">
                        <label class="form-label-inline">File Size Under:</label>
                        <input type="text" class="form-input form-input-small skip-when-file-size"
                               placeholder="e.g., 1GB, 500MB"
                               value="${escapeAttr(phase.skip_when?.file_size_under || '')}">
                    </div>
                    <div class="filter-row">
                        <label class="form-label-inline">Duration Under:</label>
                        <input type="text" class="form-input form-input-small skip-when-duration"
                               placeholder="e.g., 30m, 1h"
                               value="${escapeAttr(phase.skip_when?.duration_under || '')}">
                    </div>
                </div>
            </div>
        `

        condExecToggle.appendChild(condExecSummary)
        condExecToggle.appendChild(condExecContent)
        condExecSection.appendChild(condExecToggle)
        div.appendChild(condExecSection)

        // Conditional execution event listeners
        const onErrorSelect = condExecContent.querySelector('.phase-on-error-select')
        const dependsOnInput = condExecContent.querySelector('.phase-depends-on')
        const runIfTypeSelect = condExecContent.querySelector('.phase-run-if-type')
        const runIfValueInput = condExecContent.querySelector('.phase-run-if-value')
        const skipVideoCodec = condExecContent.querySelector('.skip-when-video-codec')
        const skipAudioCodec = condExecContent.querySelector('.skip-when-audio-codec')
        const skipContainer = condExecContent.querySelector('.skip-when-container')
        const skipResolution = condExecContent.querySelector('.skip-when-resolution')
        const skipFileSize = condExecContent.querySelector('.skip-when-file-size')
        const skipDuration = condExecContent.querySelector('.skip-when-duration')

        onErrorSelect.addEventListener('change', () => {
            phases[index].on_error = onErrorSelect.value || null
            notifyUpdate()
        })

        dependsOnInput.addEventListener('input', () => {
            const names = dependsOnInput.value.split(',').map(s => s.trim()).filter(Boolean)
            phases[index].depends_on = names.length > 0 ? names : null
            notifyUpdate()
        })

        runIfTypeSelect.addEventListener('change', () => {
            const type = runIfTypeSelect.value
            runIfValueInput.style.display = type ? 'inline-block' : 'none'
            if (!type) {
                phases[index].run_if = null
            } else {
                phases[index].run_if = { [type]: runIfValueInput.value.trim() || '' }
            }
            notifyUpdate()
        })

        runIfValueInput.addEventListener('input', () => {
            const type = runIfTypeSelect.value
            if (type) {
                phases[index].run_if = { [type]: runIfValueInput.value.trim() || '' }
                notifyUpdate()
            }
        })

        function collectSkipWhen() {
            const skipWhen = {}
            const vCodecs = skipVideoCodec.value.split(',').map(s => s.trim()).filter(Boolean)
            if (vCodecs.length > 0) skipWhen.video_codec = vCodecs
            const aCodec = skipAudioCodec.value.trim()
            if (aCodec) skipWhen.audio_codec_exists = aCodec
            const containers = skipContainer.value.split(',').map(s => s.trim()).filter(Boolean)
            if (containers.length > 0) skipWhen.container = containers
            if (skipResolution.value) skipWhen.resolution_under = skipResolution.value
            const fSize = skipFileSize.value.trim()
            if (fSize) skipWhen.file_size_under = fSize
            const dur = skipDuration.value.trim()
            if (dur) skipWhen.duration_under = dur

            phases[index].skip_when = Object.keys(skipWhen).length > 0 ? skipWhen : null
            notifyUpdate()
        }

        ;[skipVideoCodec, skipAudioCodec, skipContainer, skipFileSize, skipDuration].forEach(el => {
            el.addEventListener('input', collectSkipWhen)
        })
        skipResolution.addEventListener('change', collectSkipWhen)

        // Name input change
        nameInput.addEventListener('blur', () => {
            const error = validatePhaseName(nameInput.value, index)
            if (error) {
                nameInput.classList.add('input-error')
                nameInput.title = error
            } else {
                nameInput.classList.remove('input-error')
                nameInput.title = ''
                phases[index].name = nameInput.value.trim()
                notifyUpdate()
            }
        })

        nameInput.addEventListener('input', () => {
            nameInput.classList.remove('input-error')
            nameInput.title = ''
        })

        // Delete button
        deleteBtn.addEventListener('click', () => {
            phases.splice(index, 1)
            renderPhases()
            notifyUpdate()
        })

        // Drag events
        div.addEventListener('dragstart', (e) => {
            draggedItem = div
            div.classList.add('dragging')
            e.dataTransfer.effectAllowed = 'move'
        })

        div.addEventListener('dragend', () => {
            div.classList.remove('dragging')
            draggedItem = null
        })

        div.addEventListener('dragover', (e) => {
            e.preventDefault()
            if (!draggedItem || draggedItem === div) return

            const rect = div.getBoundingClientRect()
            const midY = rect.top + rect.height / 2

            if (e.clientY < midY) {
                div.classList.add('drag-over-top')
                div.classList.remove('drag-over-bottom')
            } else {
                div.classList.add('drag-over-bottom')
                div.classList.remove('drag-over-top')
            }
        })

        div.addEventListener('dragleave', () => {
            div.classList.remove('drag-over-top', 'drag-over-bottom')
        })

        div.addEventListener('drop', (e) => {
            e.preventDefault()
            div.classList.remove('drag-over-top', 'drag-over-bottom')

            if (!draggedItem || draggedItem === div) return

            const fromIndex = parseInt(draggedItem.dataset.index)
            const toIndex = parseInt(div.dataset.index)

            // Move phase in array
            const [removed] = phases.splice(fromIndex, 1)
            const insertAt = e.clientY < div.getBoundingClientRect().top + div.getBoundingClientRect().height / 2
                ? toIndex
                : toIndex + 1
            phases.splice(insertAt > fromIndex ? insertAt - 1 : insertAt, 0, removed)

            renderPhases()
            notifyUpdate()
        })

        return div
    }

    function hasOperation(phase, opId) {
        // Check if phase has this operation configured
        switch (opId) {
        case 'container': return !!phase.container
        case 'audio_filter': return !!phase.audio_filter
        case 'subtitle_filter': return !!phase.subtitle_filter
        case 'attachment_filter': return !!phase.attachment_filter
        case 'track_order': return Array.isArray(phase.track_order) && phase.track_order.length > 0
        case 'default_flags': return !!phase.default_flags
        case 'conditional': return Array.isArray(phase.conditional) && phase.conditional.length > 0
        case 'audio_synthesis': return !!phase.audio_synthesis
        case 'transcode': return !!phase.transcode || !!phase.audio_transcode
        case 'transcription': return !!phase.transcription
        case 'file_timestamp': return !!phase.file_timestamp
        default: return false
        }
    }

    function updatePhaseOperation(phaseIndex, opId, enabled) {
        const phase = phases[phaseIndex]
        if (!phase) return

        if (enabled) {
            // Add default config for the operation
            switch (opId) {
            case 'container':
                phase.container = { target: 'mkv' }
                break
            case 'audio_filter':
                phase.audio_filter = { languages: ['eng'] }
                break
            case 'subtitle_filter':
                phase.subtitle_filter = { languages: ['eng'] }
                break
            case 'attachment_filter':
                phase.attachment_filter = { remove_all: false }
                break
            case 'track_order':
                phase.track_order = ['video', 'audio', 'subtitle', 'attachment']
                break
            case 'default_flags':
                phase.default_flags = { set_first_video_default: true }
                break
            case 'conditional':
                phase.conditional = []
                break
            case 'audio_synthesis':
                phase.audio_synthesis = { tracks: [] }
                break
            case 'transcode':
                phase.transcode = { target_codec: 'hevc' }
                break
            case 'transcription':
                phase.transcription = { enabled: true }
                break
            case 'file_timestamp':
                phase.file_timestamp = { mode: 'preserve' }
                break
            }
        } else {
            // Remove the operation
            delete phase[opId]
            // Special case for transcode which has audio_transcode too
            if (opId === 'transcode') {
                delete phase.audio_transcode
            }
        }
    }

    function renderPhases() {
        phasesList.innerHTML = ''

        if (phases.length === 0) {
            const empty = document.createElement('p')
            empty.className = 'accordion-list-empty'
            empty.textContent = 'No phases configured. Click "Add Phase" to create one.'
            phasesList.appendChild(empty)
            return
        }

        phases.forEach((phase, index) => {
            const element = createPhaseElement(phase, index)
            phasesList.appendChild(element)
        })
    }

    function setInitialValues() {
        // Set on_error select
        if (configOnError) {
            configOnError.value = config.on_error || 'skip'
        }

        renderPhases()
    }

    // Event listeners
    if (addPhaseBtn) {
        addPhaseBtn.addEventListener('click', () => {
            // Generate unique name
            let baseName = 'phase'
            let counter = phases.length + 1
            let name = `${baseName}_${counter}`
            while (phases.find(p => p.name === name)) {
                counter++
                name = `${baseName}_${counter}`
            }

            phases.push({ name })
            renderPhases()
            notifyUpdate()

            // Focus the new name input
            const inputs = phasesList.querySelectorAll('.phase-name-input')
            if (inputs.length > 0) {
                inputs[inputs.length - 1].focus()
                inputs[inputs.length - 1].select()
            }
        })
    }

    if (configOnError) {
        configOnError.addEventListener('change', () => {
            config.on_error = configOnError.value
            notifyUpdate()
        })
    }

    // Initialize
    setInitialValues()

    // Return controller
    return {
        /**
         * Get current phases configuration
         * @returns {Object} Object with phases and config
         */
        getConfig() {
            return getConfig()
        },

        /**
         * Set phases configuration
         * @param {Object} newConfig - Object with phases and config
         */
        setConfig(newConfig) {
            phases = newConfig.phases ? JSON.parse(JSON.stringify(newConfig.phases)) : []
            config = newConfig.config ? { ...newConfig.config } : {}
            setInitialValues()
        },

        /**
         * Refresh the UI with current policy data
         * @param {Object} policyData - Policy data
         */
        refresh(policyData) {
            phases = policyData.phases ? JSON.parse(JSON.stringify(policyData.phases)) : []
            config = policyData.config ? { ...policyData.config } : {}
            setInitialValues()
        },

        /**
         * Check if this is a V11 policy
         * @returns {boolean}
         */
        isV11() {
            return true
        }
    }
}
