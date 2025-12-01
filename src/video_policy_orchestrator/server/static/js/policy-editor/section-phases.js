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
 * track_order, default_flags, conditional, audio_synthesis, transcode, transcription
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
    { id: 'transcription', label: 'Transcription', description: 'Transcription analysis' }
]

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
