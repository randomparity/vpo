/**
 * Policy Editor Main Module (024-policy-editor, 036-v9-policy-editor)
 *
 * Handles policy editing form with track ordering, language preferences,
 * V3-V10 schema features, and save functionality with field preservation.
 */

import { initAccordion } from './accordion.js'
import { initTranscodeSection } from './section-transcode.js'
import { initFiltersSection } from './section-filters.js'
import { initConditionalSection } from './section-conditional.js'
import { initSynthesisSection } from './section-synthesis.js'
import { initContainerSection } from './section-container.js'
import { initWorkflowSection } from './section-workflow.js'
import { initPhasesSection } from './section-phases.js'
import { validatePolicyData } from './validator.js'
import { createLanguageAutocomplete } from './language-autocomplete.js'

// ======================================
// Toast Module (H3: Undo toast for destructive actions)
// ======================================

let toastTimeout = null
let undoCallback = null

/**
 * Show an undo toast notification
 * @param {string} message - Message to display
 * @param {Function} onUndo - Callback when undo is clicked
 */
export function showUndoToast(message, onUndo) {
    const toast = document.getElementById('undo-toast')
    if (!toast) return

    const msgEl = toast.querySelector('.toast-message')
    const undoBtn = toast.querySelector('.toast-undo-btn')
    const closeBtn = toast.querySelector('.toast-close-btn')

    msgEl.textContent = message
    undoCallback = onUndo
    toast.hidden = false

    // Trigger reflow to enable CSS transition
    toast.offsetHeight
    toast.classList.add('visible')

    // Clear any existing timeout
    clearTimeout(toastTimeout)

    // Auto-dismiss after 5 seconds
    toastTimeout = setTimeout(() => {
        hideToast()
        undoCallback = null
    }, 5000)

    // Set up button handlers (use once to avoid duplicate handlers)
    undoBtn.onclick = () => {
        if (undoCallback) {
            undoCallback()
        }
        hideToast()
        undoCallback = null
    }

    closeBtn.onclick = () => {
        hideToast()
        undoCallback = null
    }
}

/**
 * Hide the undo toast
 */
export function hideToast() {
    const toast = document.getElementById('undo-toast')
    if (!toast) return

    clearTimeout(toastTimeout)
    toast.classList.remove('visible')
    setTimeout(() => {
        toast.hidden = true
    }, 300) // Wait for CSS transition
}

/**
 * Escape a string for safe interpolation into HTML attribute values.
 * Uses the DOM textContent approach consistent with window.VPOUtils.escapeHtml.
 * @param {*} str - Value to escape
 * @returns {string} Escaped string safe for HTML attribute use
 */
export function escapeAttr(str) {
    if (!str && str !== 0) return ''
    const div = document.createElement('div')
    div.textContent = str
    return div.innerHTML
}

/**
 * Announce a message to screen readers (H5)
 * @param {string} message - Message to announce
 */
function announceToScreenReader(message) {
    const statusRegion = document.getElementById('sr-save-status')
    if (statusRegion) {
        statusRegion.textContent = message
    }
}

(function () {
    'use strict'

    // Validate that POLICY_DATA is available
    if (typeof window.POLICY_DATA === 'undefined') {
        console.error('POLICY_DATA not found')
        return
    }

    // Initialize accordion for advanced settings
    const accordionController = initAccordion('#advanced-settings', {
        allowMultiple: true,
        onToggle: ({ sectionId, isOpen }) => {
            // Store accordion state in localStorage for persistence
            const storedState = JSON.parse(localStorage.getItem('policy-editor-accordion') || '{}')
            storedState[sectionId] = isOpen
            localStorage.setItem('policy-editor-accordion', JSON.stringify(storedState))
        }
    })

    // Restore accordion state from localStorage
    if (accordionController) {
        const storedState = JSON.parse(localStorage.getItem('policy-editor-accordion') || '{}')
        Object.entries(storedState).forEach(([sectionId, isOpen]) => {
            if (isOpen) {
                accordionController.open(sectionId)
            } else {
                accordionController.close(sectionId)
            }
        })
    }

    // State management
    let formState = {
        name: window.POLICY_DATA.name,
        display_name: window.POLICY_DATA.display_name || '',
        last_modified: window.POLICY_DATA.last_modified,
        track_order: [...window.POLICY_DATA.track_order],
        audio_language_preference: [...window.POLICY_DATA.audio_language_preference],
        subtitle_language_preference: [...window.POLICY_DATA.subtitle_language_preference],
        commentary_patterns: [...window.POLICY_DATA.commentary_patterns],
        default_flags: {...window.POLICY_DATA.default_flags},
        transcription: window.POLICY_DATA.transcription ? {...window.POLICY_DATA.transcription} : null,
        // V3-V10 fields (036-v9-policy-editor)
        transcode: window.POLICY_DATA.transcode ? JSON.parse(JSON.stringify(window.POLICY_DATA.transcode)) : null,
        audio_filter: window.POLICY_DATA.audio_filter ? JSON.parse(JSON.stringify(window.POLICY_DATA.audio_filter)) : null,
        subtitle_filter: window.POLICY_DATA.subtitle_filter ? JSON.parse(JSON.stringify(window.POLICY_DATA.subtitle_filter)) : null,
        attachment_filter: window.POLICY_DATA.attachment_filter ? JSON.parse(JSON.stringify(window.POLICY_DATA.attachment_filter)) : null,
        container: window.POLICY_DATA.container ? JSON.parse(JSON.stringify(window.POLICY_DATA.container)) : null,
        conditional: window.POLICY_DATA.conditional ? JSON.parse(JSON.stringify(window.POLICY_DATA.conditional)) : null,
        audio_synthesis: window.POLICY_DATA.audio_synthesis ? JSON.parse(JSON.stringify(window.POLICY_DATA.audio_synthesis)) : null,
        workflow: window.POLICY_DATA.workflow ? JSON.parse(JSON.stringify(window.POLICY_DATA.workflow)) : null,
        // V11 fields (037-user-defined-phases)
        phases: window.POLICY_DATA.phases ? JSON.parse(JSON.stringify(window.POLICY_DATA.phases)) : null,
        config: window.POLICY_DATA.config ? JSON.parse(JSON.stringify(window.POLICY_DATA.config)) : null,
        isDirty: false,
        isSaving: false
    }

    // Section controllers (036-v9-policy-editor)
    let transcodeController = null
    let filtersController = null
    let conditionalController = null
    let synthesisController = null
    let containerController = null
    let workflowController = null
    // V11 section controller (037-user-defined-phases)
    let phasesController = null

    const originalState = JSON.stringify(formState)

    // Track type labels
    const trackTypeLabels = {
        'video': 'Video',
        'audio_main': 'Audio (Main)',
        'audio_alternate': 'Audio (Alternate)',
        'audio_commentary': 'Audio (Commentary)',
        'subtitle_main': 'Subtitles (Main)',
        'subtitle_forced': 'Subtitles (Forced)',
        'subtitle_commentary': 'Subtitles (Commentary)',
        'attachment': 'Attachments'
    }

    // DOM elements
    const trackOrderList = document.getElementById('track-order-list')
    const audioLangInput = document.getElementById('audio-lang-input')
    const audioLangAddBtn = document.getElementById('audio-lang-add-btn')
    const audioLangList = document.getElementById('audio-lang-list')
    const subtitleLangInput = document.getElementById('subtitle-lang-input')
    const subtitleLangAddBtn = document.getElementById('subtitle-lang-add-btn')
    const subtitleLangList = document.getElementById('subtitle-lang-list')
    const commentaryPatternInput = document.getElementById('commentary-pattern-input')
    const commentaryPatternAddBtn = document.getElementById('commentary-pattern-add-btn')
    const commentaryPatternsList = document.getElementById('commentary-patterns-list')
    const detectCommentaryCheckbox = document.getElementById('detect_commentary')
    const reorderCommentaryCheckbox = document.getElementById('reorder_commentary')
    const yamlPreview = document.getElementById('yaml-preview')
    const saveBtn = document.getElementById('save-btn')
    const cancelBtn = document.getElementById('cancel-btn')
    const saveStatus = document.getElementById('save-status')
    const validationErrors = document.getElementById('validation-errors')

    // Display name input
    const displayNameInput = document.getElementById('policy-display-name')
    if (displayNameInput) {
        displayNameInput.addEventListener('input', () => {
            formState.display_name = displayNameInput.value
            markDirty()
        })
    }

    // Default flags checkboxes
    const defaultFlagCheckboxes = {
        set_first_video_default: document.getElementById('set_first_video_default'),
        set_preferred_audio_default: document.getElementById('set_preferred_audio_default'),
        set_preferred_subtitle_default: document.getElementById('set_preferred_subtitle_default'),
        clear_other_defaults: document.getElementById('clear_other_defaults'),
        set_subtitle_default_when_audio_differs: document.getElementById('set_subtitle_default_when_audio_differs'),
        set_subtitle_forced_when_audio_differs: document.getElementById('set_subtitle_forced_when_audio_differs')
    }

    // Preferred audio codec input
    const preferredAudioCodecInput = document.getElementById('preferred_audio_codec')

    // Debounce timer for YAML preview
    let yamlPreviewTimeout

    // Debounce timer for regex validation
    let regexValidationTimeout

    /**
     * Mark form as dirty
     */
    function markDirty() {
        const currentState = JSON.stringify(formState)
        formState.isDirty = (currentState !== originalState)
        updateSaveButtonState()
        updateYAMLPreview()
    }

    /**
     * Update save button state
     */
    function updateSaveButtonState() {
        saveBtn.disabled = !formState.isDirty || formState.isSaving
    }

    /**
     * Render track order list
     */
    function renderTrackOrder() {
        trackOrderList.innerHTML = ''

        formState.track_order.forEach((trackType, index) => {
            const li = document.createElement('li')
            li.className = 'track-order-item'
            li.dataset.trackType = trackType

            const label = document.createElement('span')
            label.className = 'track-order-label'
            label.textContent = trackTypeLabels[trackType] || trackType

            const buttons = document.createElement('div')
            buttons.className = 'track-order-buttons'

            const upBtn = document.createElement('button')
            upBtn.type = 'button'
            upBtn.className = 'btn-icon'
            upBtn.innerHTML = '↑'
            upBtn.title = 'Move up'
            upBtn.setAttribute('aria-label', `Move ${trackTypeLabels[trackType]} up`)
            upBtn.tabIndex = 0
            upBtn.disabled = index === 0
            upBtn.addEventListener('click', () => moveTrackUp(index))
            upBtn.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    moveTrackUp(index)
                }
            })

            const downBtn = document.createElement('button')
            downBtn.type = 'button'
            downBtn.className = 'btn-icon'
            downBtn.innerHTML = '↓'
            downBtn.title = 'Move down'
            downBtn.setAttribute('aria-label', `Move ${trackTypeLabels[trackType]} down`)
            downBtn.tabIndex = 0
            downBtn.disabled = index === formState.track_order.length - 1
            downBtn.addEventListener('click', () => moveTrackDown(index))
            downBtn.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    moveTrackDown(index)
                }
            })

            buttons.appendChild(upBtn)
            buttons.appendChild(downBtn)

            li.appendChild(label)
            li.appendChild(buttons)
            trackOrderList.appendChild(li)
        })
    }

    /**
     * Move track up in order
     */
    function moveTrackUp(index) {
        if (index === 0) return
        const temp = formState.track_order[index]
        formState.track_order[index] = formState.track_order[index - 1]
        formState.track_order[index - 1] = temp
        renderTrackOrder()
        markDirty()
    }

    /**
     * Move track down in order
     */
    function moveTrackDown(index) {
        if (index === formState.track_order.length - 1) return
        const temp = formState.track_order[index]
        formState.track_order[index] = formState.track_order[index + 1]
        formState.track_order[index + 1] = temp
        renderTrackOrder()
        markDirty()
    }

    /**
     * Render language list
     */
    function renderLanguageList(listEl, languages, listType) {
        listEl.innerHTML = ''

        if (languages.length === 0) {
            const emptyMsg = document.createElement('li')
            emptyMsg.className = 'language-list-empty'
            emptyMsg.textContent = 'No languages yet. Click "Add" above to add your first language.'
            listEl.appendChild(emptyMsg)
            return
        }

        languages.forEach((lang, index) => {
            const li = document.createElement('li')
            li.className = 'language-list-item'

            const label = document.createElement('span')
            label.className = 'language-code'
            label.textContent = lang

            const buttons = document.createElement('div')
            buttons.className = 'language-buttons'

            const upBtn = document.createElement('button')
            upBtn.type = 'button'
            upBtn.className = 'btn-icon'
            upBtn.innerHTML = '↑'
            upBtn.title = 'Move up'
            upBtn.setAttribute('aria-label', `Move ${lang} up`)
            upBtn.tabIndex = 0
            upBtn.disabled = index === 0
            upBtn.addEventListener('click', () => moveLanguageUp(listType, index))
            upBtn.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    moveLanguageUp(listType, index)
                }
            })

            const downBtn = document.createElement('button')
            downBtn.type = 'button'
            downBtn.className = 'btn-icon'
            downBtn.innerHTML = '↓'
            downBtn.title = 'Move down'
            downBtn.setAttribute('aria-label', `Move ${lang} down`)
            downBtn.tabIndex = 0
            downBtn.disabled = index === languages.length - 1
            downBtn.addEventListener('click', () => moveLanguageDown(listType, index))
            downBtn.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    moveLanguageDown(listType, index)
                }
            })

            const removeBtn = document.createElement('button')
            removeBtn.type = 'button'
            removeBtn.className = 'btn-icon btn-remove'
            removeBtn.innerHTML = '×'
            removeBtn.title = 'Remove'
            removeBtn.setAttribute('aria-label', `Remove ${lang}`)
            removeBtn.tabIndex = 0
            removeBtn.addEventListener('click', () => removeLanguage(listType, index))
            removeBtn.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    removeLanguage(listType, index)
                }
            })

            buttons.appendChild(upBtn)
            buttons.appendChild(downBtn)
            buttons.appendChild(removeBtn)

            li.appendChild(label)
            li.appendChild(buttons)
            listEl.appendChild(li)
        })
    }

    /**
     * Move language up
     */
    function moveLanguageUp(listType, index) {
        if (index === 0) return
        const list = listType === 'audio' ? formState.audio_language_preference : formState.subtitle_language_preference
        const temp = list[index]
        list[index] = list[index - 1]
        list[index - 1] = temp
        renderLanguageLists()
        markDirty()
    }

    /**
     * Move language down
     */
    function moveLanguageDown(listType, index) {
        const list = listType === 'audio' ? formState.audio_language_preference : formState.subtitle_language_preference
        if (index === list.length - 1) return
        const temp = list[index]
        list[index] = list[index + 1]
        list[index + 1] = temp
        renderLanguageLists()
        markDirty()
    }

    /**
     * Remove language
     */
    function removeLanguage(listType, index) {
        const list = listType === 'audio' ? formState.audio_language_preference : formState.subtitle_language_preference
        list.splice(index, 1)
        renderLanguageLists()
        markDirty()
    }

    /**
     * Add language
     * @param {string} listType - 'audio' or 'subtitle'
     * @param {string} code - Language code to add
     * @returns {boolean} - true if added successfully, false if validation failed
     */
    function addLanguage(listType, code) {
        // Validate ISO 639-2 code (2-3 lowercase letters)
        const trimmed = code.trim().toLowerCase()
        if (!/^[a-z]{2,3}$/.test(trimmed)) {
            showError(`Invalid language code: "${code}". Use 2-3 letter codes (e.g., eng, jpn, fra).`)
            return false
        }

        const list = listType === 'audio' ? formState.audio_language_preference : formState.subtitle_language_preference

        // Check for duplicates
        if (list.includes(trimmed)) {
            showError(`Language "${trimmed}" is already in the list.`)
            return false
        }

        list.push(trimmed)
        renderLanguageLists()
        markDirty()

        // Clear input (for the original input fields, not autocomplete)
        if (listType === 'audio') {
            audioLangInput.value = ''
            audioLangInput.focus()
        } else {
            subtitleLangInput.value = ''
            subtitleLangInput.focus()
        }

        return true
    }

    /**
     * Render all language lists
     */
    function renderLanguageLists() {
        renderLanguageList(audioLangList, formState.audio_language_preference, 'audio')
        renderLanguageList(subtitleLangList, formState.subtitle_language_preference, 'subtitle')
    }

    /**
     * Render commentary patterns list
     */
    function renderCommentaryPatterns() {
        commentaryPatternsList.innerHTML = ''

        if (formState.commentary_patterns.length === 0) {
            const emptyMsg = document.createElement('li')
            emptyMsg.className = 'patterns-list-empty'
            emptyMsg.textContent = 'No patterns yet. Click "Add Pattern" above to add your first pattern.'
            commentaryPatternsList.appendChild(emptyMsg)
            return
        }

        formState.commentary_patterns.forEach((pattern, index) => {
            const li = document.createElement('li')
            li.className = 'pattern-list-item'

            const label = document.createElement('span')
            label.className = 'pattern-text'
            label.textContent = pattern

            const buttons = document.createElement('div')
            buttons.className = 'pattern-buttons'

            const removeBtn = document.createElement('button')
            removeBtn.type = 'button'
            removeBtn.className = 'btn-icon btn-remove'
            removeBtn.innerHTML = '×'
            removeBtn.title = 'Remove pattern'
            removeBtn.setAttribute('aria-label', `Remove pattern ${pattern}`)
            removeBtn.tabIndex = 0
            removeBtn.addEventListener('click', () => removeCommentaryPattern(index))
            removeBtn.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    removeCommentaryPattern(index)
                }
            })

            buttons.appendChild(removeBtn)

            li.appendChild(label)
            li.appendChild(buttons)
            commentaryPatternsList.appendChild(li)
        })
    }

    /**
     * Validate regex pattern
     */
    function isValidRegex(pattern) {
        try {
            new RegExp(pattern)
            return true
        } catch {
            return false
        }
    }

    /**
     * Add commentary pattern
     */
    function addCommentaryPattern(pattern) {
        const trimmed = pattern.trim()

        if (trimmed === '') {
            showError('Pattern cannot be empty')
            return
        }

        // Validate regex
        if (!isValidRegex(trimmed)) {
            showError(`Invalid regex pattern: "${trimmed}". Check syntax and try again.`)
            return
        }

        // Check for duplicates
        if (formState.commentary_patterns.includes(trimmed)) {
            showError(`Pattern "${trimmed}" is already in the list.`)
            return
        }

        formState.commentary_patterns.push(trimmed)
        renderCommentaryPatterns()
        markDirty()

        // Clear input
        commentaryPatternInput.value = ''
        commentaryPatternInput.focus()
    }

    /**
     * Remove commentary pattern
     */
    function removeCommentaryPattern(index) {
        formState.commentary_patterns.splice(index, 1)
        renderCommentaryPatterns()
        markDirty()
    }

    // Transcription controls
    const updateLangCheckbox = document.getElementById('update_language_from_transcription')
    const confidenceThresholdInput = document.getElementById('confidence_threshold')

    /**
     * Update transcription checkboxes state
     */
    function updateTranscriptionCheckboxes() {
        if (formState.transcription) {
            if (detectCommentaryCheckbox) {
                detectCommentaryCheckbox.checked = formState.transcription.detect_commentary || false
            }
            if (reorderCommentaryCheckbox) {
                reorderCommentaryCheckbox.checked = formState.transcription.reorder_commentary || false
                // Disable reorder if detect is not enabled
                reorderCommentaryCheckbox.disabled = !formState.transcription.detect_commentary
            }
            if (updateLangCheckbox) {
                updateLangCheckbox.checked = formState.transcription.update_language_from_transcription || false
            }
            if (confidenceThresholdInput) {
                const threshold = formState.transcription.confidence_threshold
                confidenceThresholdInput.value = threshold !== undefined ? Math.round(threshold * 100) : 80
            }
        }
    }

    /**
     * Generate YAML from form state
     */
    function generateYAML() {
        let yaml = `schema_version: ${window.POLICY_DATA.schema_version}\n`

        // Display name
        const trimmedName = (formState.display_name || '').trim()
        if (trimmedName) {
            yaml += `name: ${trimmedName}\n`
        }
        yaml += '\n'

        // Track order
        yaml += 'track_order:\n'
        formState.track_order.forEach(track => {
            yaml += `  - ${track}\n`
        })
        yaml += '\n'

        // Audio language preference
        yaml += 'audio_language_preference:\n'
        formState.audio_language_preference.forEach(lang => {
            yaml += `  - ${lang}\n`
        })
        yaml += '\n'

        // Subtitle language preference
        yaml += 'subtitle_language_preference:\n'
        formState.subtitle_language_preference.forEach(lang => {
            yaml += `  - ${lang}\n`
        })
        yaml += '\n'

        // Commentary patterns
        yaml += 'commentary_patterns:\n'
        if (formState.commentary_patterns.length === 0) {
            yaml += '  []\n'
        } else {
            formState.commentary_patterns.forEach(pattern => {
                yaml += `  - ${pattern}\n`
            })
        }
        yaml += '\n'

        // Default flags
        yaml += 'default_flags:\n'
        Object.keys(formState.default_flags).forEach(key => {
            const value = formState.default_flags[key]
            if (key === 'preferred_audio_codec') {
                if (Array.isArray(value) && value.length > 0) {
                    yaml += `  ${key}: [${value.join(', ')}]\n`
                }
                // Omit if null/empty
            } else {
                yaml += `  ${key}: ${value}\n`
            }
        })
        yaml += '\n'

        // Transcode (if exists)
        if (window.POLICY_DATA.transcode) {
            yaml += '# Transcode settings preserved (not editable in UI)\n'
            yaml += 'transcode:\n'
            yaml += '  # ... (original settings preserved)\n\n'
        }

        // Transcription (if exists)
        if (formState.transcription) {
            yaml += 'transcription:\n'
            yaml += `  enabled: ${formState.transcription.enabled}\n`
            if (formState.transcription.update_language_from_transcription !== undefined) {
                yaml += `  update_language_from_transcription: ${formState.transcription.update_language_from_transcription}\n`
            }
            if (formState.transcription.confidence_threshold !== undefined) {
                yaml += `  confidence_threshold: ${formState.transcription.confidence_threshold}\n`
            }
            yaml += `  detect_commentary: ${formState.transcription.detect_commentary}\n`
            yaml += `  reorder_commentary: ${formState.transcription.reorder_commentary}\n`
        }

        return yaml
    }

    /**
     * Update YAML preview with debouncing and syntax highlighting (T051)
     */
    function updateYAMLPreview() {
        if (!yamlPreview) return

        clearTimeout(yamlPreviewTimeout)
        yamlPreviewTimeout = setTimeout(() => {
            const yaml = generateYAML()
            yamlPreview.textContent = yaml

            // Apply syntax highlighting if highlight.js is available
            if (typeof hljs !== 'undefined') {
                // Remove previous highlighting classes
                yamlPreview.classList.remove('hljs')
                yamlPreview.removeAttribute('data-highlighted')
                // Apply fresh highlighting
                hljs.highlightElement(yamlPreview)
            }
        }, 300) // 300ms debounce as per spec
    }

    /**
     * Validate form data
     */
    function validateForm() {
        const errors = []

        if (formState.track_order.length === 0) {
            errors.push('Track order cannot be empty')
        }

        if (formState.audio_language_preference.length === 0) {
            errors.push('Audio language preferences cannot be empty')
        }

        if (formState.subtitle_language_preference.length === 0) {
            errors.push('Subtitle language preferences cannot be empty')
        }

        // Validate commentary patterns (all must be valid regex)
        formState.commentary_patterns.forEach((pattern, index) => {
            if (!isValidRegex(pattern)) {
                errors.push(`Invalid regex pattern at position ${index + 1}: "${pattern}"`)
            }
        })

        // Cross-field validation: reorder_commentary requires detect_commentary
        if (formState.transcription && formState.transcription.reorder_commentary && !formState.transcription.detect_commentary) {
            errors.push('Reorder commentary requires detect commentary to be enabled')
        }

        return errors
    }

    /**
     * Show error message (single string)
     */
    function showError(message) {
        showErrors([{ message }])
    }

    /**
     * Show multiple field-level errors (T020)
     * @param {Array<{field?: string, message: string, code?: string}>} errors - Array of error objects
     */
    function showErrors(errors) {
        // Clear previous content and field highlighting
        validationErrors.innerHTML = ''
        clearFieldHighlighting()

        if (!errors || errors.length === 0) {
            validationErrors.style.display = 'none'
            return
        }

        // Create error list container
        const errorList = document.createElement('div')
        errorList.className = 'validation-error-list'

        // Create header if multiple errors
        if (errors.length > 1) {
            const header = document.createElement('div')
            header.className = 'validation-error-header'
            header.textContent = `${errors.length} validation error${errors.length > 1 ? 's' : ''} found:`
            errorList.appendChild(header)
        }

        // Create error items
        const errorItems = document.createElement('ul')
        errorItems.className = 'validation-error-items'

        errors.forEach(error => {
            const li = document.createElement('li')
            li.className = 'validation-error-item'

            // Format error message with field name
            if (error.field && error.field !== 'root') {
                const fieldSpan = document.createElement('span')
                fieldSpan.className = 'validation-error-field'
                fieldSpan.textContent = error.field
                li.appendChild(fieldSpan)
                li.appendChild(document.createTextNode(': '))

                // Highlight the field in the form (T022)
                highlightErrorField(error.field)
            }

            const messageSpan = document.createElement('span')
            messageSpan.className = 'validation-error-message'
            messageSpan.textContent = error.message
            li.appendChild(messageSpan)

            errorItems.appendChild(li)
        })

        errorList.appendChild(errorItems)
        validationErrors.appendChild(errorList)

        // Create close button
        const closeBtn = document.createElement('button')
        closeBtn.className = 'error-close'
        closeBtn.innerHTML = '×'
        closeBtn.setAttribute('aria-label', 'Dismiss errors')
        closeBtn.tabIndex = 0
        closeBtn.onclick = () => {
            validationErrors.style.display = 'none'
            clearFieldHighlighting()
            saveBtn.focus() // Restore focus for accessibility
        }
        closeBtn.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                validationErrors.style.display = 'none'
                clearFieldHighlighting()
                saveBtn.focus() // Restore focus for accessibility
            }
        })
        validationErrors.appendChild(closeBtn)

        validationErrors.style.display = 'block'
        validationErrors.setAttribute('role', 'alert')

        // Focus the error for screen readers
        validationErrors.tabIndex = -1
        validationErrors.focus()

        // Scroll to first error field or top of page (T022a)
        scrollToFirstError(errors)
    }

    /**
     * Map field name to DOM element ID or class for highlighting (T022)
     */
    const fieldToElementMap = {
        'track_order': 'track-order-list',
        'audio_language_preference': 'audio-lang-list',
        'subtitle_language_preference': 'subtitle-lang-list',
        'commentary_patterns': 'commentary-patterns-list',
        'default_flags': 'default-flags-section',
        'preferred_audio_codec': 'preferred_audio_codec'
    }

    /**
     * Highlight a field section that has an error (T022)
     */
    function highlightErrorField(field) {
        // Extract base field name (remove array index notation)
        const baseField = field.split('[')[0].split('.')[0]
        const elementId = fieldToElementMap[baseField]

        if (elementId) {
            const element = document.getElementById(elementId)
            if (element) {
                element.classList.add('field-error')
                // Find the parent section and highlight it too
                const section = element.closest('.editor-section')
                if (section) {
                    section.classList.add('section-has-error')
                }
            }
        }
    }

    /**
     * Clear all field error highlighting
     */
    function clearFieldHighlighting() {
        document.querySelectorAll('.field-error').forEach(el => {
            el.classList.remove('field-error')
        })
        document.querySelectorAll('.section-has-error').forEach(el => {
            el.classList.remove('section-has-error')
        })
    }

    /**
     * Scroll to the first error field (T022a)
     */
    function scrollToFirstError(errors) {
        if (!errors || errors.length === 0) {
            window.scrollTo({ top: 0, behavior: 'smooth' })
            return
        }

        // Find the first field with an error
        const firstError = errors.find(e => e.field && e.field !== 'root')
        if (firstError) {
            const baseField = firstError.field.split('[')[0].split('.')[0]
            const elementId = fieldToElementMap[baseField]

            if (elementId) {
                const element = document.getElementById(elementId)
                if (element) {
                    // Scroll to element with offset for header
                    const rect = element.getBoundingClientRect()
                    const scrollTop = window.pageYOffset + rect.top - 100
                    window.scrollTo({ top: Math.max(0, scrollTop), behavior: 'smooth' })

                    // Try to focus an input in the error section
                    setTimeout(() => {
                        const focusable = element.querySelector('input, button, select, textarea')
                        if (focusable) {
                            focusable.focus()
                        }
                    }, 300)
                    return
                }
            }
        }

        // Fallback: scroll to top
        window.scrollTo({ top: 0, behavior: 'smooth' })
    }

    /**
     * Show save status
     */
    function showSaveStatus(message, isError = false) {
        saveStatus.textContent = message
        saveStatus.className = 'save-status ' + (isError ? 'save-status--error' : 'save-status--success')
        setTimeout(() => {
            saveStatus.textContent = ''
            saveStatus.className = 'save-status'
        }, 8000) // 8 seconds for screen reader accessibility
    }

    /**
     * Save policy
     */
    async function savePolicy() {
        // Validate
        const errors = validateForm()
        if (errors.length > 0) {
            showError(errors.join('; '))
            return
        }

        formState.isSaving = true
        updateSaveButtonState()
        saveBtn.innerHTML = '<span class="spinner"></span> Saving...'
        saveBtn.setAttribute('aria-busy', 'true')
        saveStatus.textContent = ''
        announceToScreenReader('Saving policy...')

        // Get filter configs from controller if available
        const filtersConfig = filtersController ? filtersController.getConfig() : {
            audio_filter: formState.audio_filter,
            subtitle_filter: formState.subtitle_filter,
            attachment_filter: formState.attachment_filter
        }

        const requestData = {
            track_order: formState.track_order,
            audio_language_preference: formState.audio_language_preference,
            subtitle_language_preference: formState.subtitle_language_preference,
            commentary_patterns: formState.commentary_patterns,
            default_flags: formState.default_flags,
            transcode: transcodeController ? transcodeController.getConfig() : formState.transcode,
            transcription: formState.transcription,
            // V3-V10 fields (036-v9-policy-editor)
            audio_filter: filtersConfig.audio_filter,
            subtitle_filter: filtersConfig.subtitle_filter,
            attachment_filter: filtersConfig.attachment_filter,
            container: containerController ? containerController.getConfig() : formState.container,
            conditional: conditionalController ? conditionalController.getConfig() : formState.conditional,
            audio_synthesis: synthesisController ? synthesisController.getConfig() : formState.audio_synthesis,
            workflow: workflowController ? workflowController.getConfig() : formState.workflow,
            // V11 fields (037-user-defined-phases)
            phases: phasesController ? phasesController.getConfig().phases : formState.phases,
            config: phasesController ? phasesController.getConfig().config : formState.config,
            // Policy metadata
            display_name: (formState.display_name || '').trim() || null,
            description: formState.description || null,
            category: formState.category || null,
            last_modified_timestamp: formState.last_modified
        }

        try {
            const response = await fetch(`/api/policies/${formState.name}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': window.CSRF_TOKEN
                },
                body: JSON.stringify(requestData)
            })

            if (!response.ok) {
                // Handle non-OK responses (T047 edge case handling)
                let errorData
                try {
                    errorData = await response.json()
                } catch {
                    // Response is not valid JSON
                    showError(`Server error (${response.status}): Unable to parse response`)
                    formState.isSaving = false
                    saveBtn.innerHTML = 'Save Changes'
                    saveBtn.setAttribute('aria-busy', 'false')
                    updateSaveButtonState()
                    return
                }

                if (response.status === 409) {
                    showError('Concurrent modification detected. Please reload and try again.')
                } else if (response.status === 400 && errorData.errors && Array.isArray(errorData.errors)) {
                    // Handle structured validation errors (T021)
                    showErrors(errorData.errors)
                } else if (response.status === 503) {
                    showError('Service unavailable. Please try again later.')
                } else {
                    // Fallback for unexpected error formats (T047)
                    const errorMsg = errorData.error || errorData.message || errorData.details || 'Failed to save policy'
                    showError(typeof errorMsg === 'string' ? errorMsg : 'Failed to save policy')
                }
                formState.isSaving = false
                saveBtn.innerHTML = 'Save Changes'
                saveBtn.setAttribute('aria-busy', 'false')
                updateSaveButtonState()
                return
            }

            // Handle successful response (T047 edge case handling)
            let updatedPolicy
            try {
                updatedPolicy = await response.json()
            } catch {
                // Success but invalid JSON response
                showSaveStatus('Policy saved successfully')
                formState.isDirty = false
                formState.isSaving = false
                saveBtn.innerHTML = 'Save Changes'
                saveBtn.setAttribute('aria-busy', 'false')
                updateSaveButtonState()
                clearFieldHighlighting()
                return
            }

            // Update state from response
            if (updatedPolicy.last_modified) {
                formState.last_modified = updatedPolicy.last_modified
            } else if (updatedPolicy.policy && updatedPolicy.policy.last_modified) {
                formState.last_modified = updatedPolicy.policy.last_modified
            }
            formState.isDirty = false
            formState.isSaving = false
            saveBtn.innerHTML = 'Save Changes'
            saveBtn.setAttribute('aria-busy', 'false')
            updateSaveButtonState()

            // Display success message with changed fields summary (T023)
            let successMsg = 'Policy saved successfully'
            if (updatedPolicy.changed_fields_summary && updatedPolicy.changed_fields_summary !== 'No changes') {
                successMsg = `Saved: ${updatedPolicy.changed_fields_summary}`
            }
            showSaveStatus(successMsg)
            announceToScreenReader(successMsg)

            // Clear any existing error highlighting
            clearFieldHighlighting()

        } catch (error) {
            // Network errors and other exceptions (T048)
            console.error('Save error:', error)
            let errorMsg = 'Network error'
            if (error.name === 'TypeError' && error.message.includes('fetch')) {
                errorMsg = 'Unable to connect to server. Check your network connection.'
            } else if (error.name === 'AbortError') {
                errorMsg = 'Request was cancelled. Please try again.'
            } else if (error.message) {
                errorMsg = `Connection error: ${error.message}`
            }
            showError(errorMsg)
            announceToScreenReader(`Save failed: ${errorMsg}`)
            formState.isSaving = false
            saveBtn.innerHTML = 'Save Changes'
            saveBtn.setAttribute('aria-busy', 'false')
            updateSaveButtonState()
        }
    }

    /**
     * Test policy without saving (T032)
     * Uses client-side JSON Schema validation first (T033), then server validation
     */
    async function testPolicy() {
        // Don't test during save operation
        if (formState.isSaving) return

        // Clear previous errors
        clearFieldHighlighting()
        validationErrors.style.display = 'none'

        const testBtn = document.getElementById('test-policy-btn')
        const originalText = testBtn.textContent
        testBtn.innerHTML = '<span class="spinner"></span> Testing...'
        testBtn.setAttribute('aria-busy', 'true')
        testBtn.disabled = true

        // Get filter configs from controller if available
        const filtersConfigForTest = filtersController ? filtersController.getConfig() : {
            audio_filter: formState.audio_filter,
            subtitle_filter: formState.subtitle_filter,
            attachment_filter: formState.attachment_filter
        }

        const requestData = {
            track_order: formState.track_order,
            audio_language_preference: formState.audio_language_preference,
            subtitle_language_preference: formState.subtitle_language_preference,
            commentary_patterns: formState.commentary_patterns,
            default_flags: formState.default_flags,
            transcode: transcodeController ? transcodeController.getConfig() : formState.transcode,
            transcription: formState.transcription,
            // V3-V10 fields (036-v9-policy-editor)
            audio_filter: filtersConfigForTest.audio_filter,
            subtitle_filter: filtersConfigForTest.subtitle_filter,
            attachment_filter: filtersConfigForTest.attachment_filter,
            container: containerController ? containerController.getConfig() : formState.container,
            conditional: conditionalController ? conditionalController.getConfig() : formState.conditional,
            audio_synthesis: synthesisController ? synthesisController.getConfig() : formState.audio_synthesis,
            workflow: workflowController ? workflowController.getConfig() : formState.workflow,
            // V11 fields (037-user-defined-phases)
            phases: phasesController ? phasesController.getConfig().phases : formState.phases,
            config: phasesController ? phasesController.getConfig().config : formState.config,
            last_modified_timestamp: formState.last_modified
        }

        // Build policy data for schema validation (includes schema_version)
        const policyForValidation = {
            schema_version: window.POLICY_DATA.schema_version,
            ...requestData,
        }
        // Remove editor-specific fields not in schema
        delete policyForValidation.last_modified_timestamp

        // Client-side JSON Schema validation (T033)
        try {
            const clientResult = await validatePolicyData(policyForValidation)
            if (!clientResult.valid && clientResult.errors.length > 0) {
                // Show client-side validation errors immediately
                showErrors(clientResult.errors)
                testBtn.innerHTML = originalText
                testBtn.setAttribute('aria-busy', 'false')
                testBtn.disabled = false
                return
            }
        } catch (clientError) {
            // Client validation failed, fall through to server validation
            console.warn('Client-side validation unavailable:', clientError)
        }

        // Server-side validation (fallback and authoritative check)
        try {
            const response = await fetch(`/api/policies/${formState.name}/validate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': window.CSRF_TOKEN
                },
                body: JSON.stringify(requestData)
            })

            // Parse response with edge case handling (T047)
            let result
            try {
                result = await response.json()
            } catch {
                if (response.ok) {
                    // HTTP 200 but invalid JSON - assume success
                    showSaveStatus('Policy configuration is valid', false)
                } else {
                    showError(`Server error (${response.status}): Unable to parse response`)
                }
                return
            }

            // Handle non-OK status codes (T047)
            if (!response.ok) {
                if (response.status === 503) {
                    showError('Service unavailable. Please try again later.')
                } else if (result.errors && Array.isArray(result.errors)) {
                    showErrors(result.errors)
                } else {
                    const errorMsg = result.error || result.message || result.details || 'Validation request failed'
                    showError(typeof errorMsg === 'string' ? errorMsg : 'Validation request failed')
                }
                return
            }

            // Handle response (T034)
            if (result.valid === true) {
                showSaveStatus('Policy configuration is valid', false)
            } else if (result.valid === false && result.errors && Array.isArray(result.errors)) {
                showErrors(result.errors)
            } else if (result.errors && Array.isArray(result.errors)) {
                // Errors present without valid field (T047 edge case)
                showErrors(result.errors)
            } else if (result.valid === false) {
                // Invalid but no errors array
                showError(result.message || 'Validation failed')
            } else {
                // Unexpected response format (T047)
                showError(result.message || 'Unexpected response from server')
            }

        } catch (error) {
            // Network errors and other exceptions (T048)
            console.error('Test policy error:', error)
            let errorMsg = 'Network error'
            if (error.name === 'TypeError' && error.message.includes('fetch')) {
                errorMsg = 'Unable to connect to server. Check your network connection.'
            } else if (error.name === 'AbortError') {
                errorMsg = 'Request was cancelled. Please try again.'
            } else if (error.message) {
                errorMsg = `Connection error: ${error.message}`
            }
            showError(errorMsg)
        } finally {
            testBtn.innerHTML = originalText
            testBtn.setAttribute('aria-busy', 'false')
            testBtn.disabled = false
        }
    }

    /**
     * Validate language code format in real-time
     */
    function validateLanguageInput(input) {
        const value = input.value.trim().toLowerCase()
        const errorHint = document.getElementById(input.id + '-error')

        if (value.length === 0) {
            input.classList.remove('invalid', 'valid')
            input.removeAttribute('aria-invalid')
            if (errorHint) errorHint.textContent = ''
            return
        }

        const ISO_639_PATTERN = /^[a-z]{2,3}$/
        if (!ISO_639_PATTERN.test(value)) {
            input.classList.add('invalid')
            input.classList.remove('valid')
            input.setAttribute('aria-invalid', 'true')
            if (errorHint) errorHint.textContent = 'Use 2-3 letter codes (e.g., eng, jpn)'
        } else {
            input.classList.add('valid')
            input.classList.remove('invalid')
            input.setAttribute('aria-invalid', 'false')
            if (errorHint) errorHint.textContent = ''
        }
    }

    /**
     * Validate regex pattern format in real-time (T035)
     * Checks if the input is a valid JavaScript regular expression
     */
    function validateRegexInput(input) {
        const value = input.value.trim()
        const errorHint = document.getElementById(input.id + '-error')

        if (value.length === 0) {
            input.classList.remove('invalid', 'valid')
            input.removeAttribute('aria-invalid')
            if (errorHint) errorHint.textContent = ''
            return
        }

        try {
            // Attempt to create a RegExp - will throw if invalid
            new RegExp(value)
            input.classList.add('valid')
            input.classList.remove('invalid')
            input.setAttribute('aria-invalid', 'false')
            if (errorHint) errorHint.textContent = ''
        } catch {
            // Invalid regex syntax
            input.classList.add('invalid')
            input.classList.remove('valid')
            input.setAttribute('aria-invalid', 'true')
            if (errorHint) errorHint.textContent = 'Invalid regex pattern'
        }
    }

    /**
     * Initialize event listeners
     */
    function initEventListeners() {
        // Audio language real-time validation
        audioLangInput.addEventListener('input', () => {
            validateLanguageInput(audioLangInput)
        })

        // Subtitle language real-time validation
        subtitleLangInput.addEventListener('input', () => {
            validateLanguageInput(subtitleLangInput)
        })

        // Audio language add
        audioLangAddBtn.addEventListener('click', () => {
            addLanguage('audio', audioLangInput.value)
        })

        audioLangInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault()
                addLanguage('audio', audioLangInput.value)
            }
        })

        // Subtitle language add
        subtitleLangAddBtn.addEventListener('click', () => {
            addLanguage('subtitle', subtitleLangInput.value)
        })

        subtitleLangInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault()
                addLanguage('subtitle', subtitleLangInput.value)
            }
        })

        // Commentary pattern add
        if (commentaryPatternAddBtn && commentaryPatternInput) {
            commentaryPatternAddBtn.addEventListener('click', () => {
                addCommentaryPattern(commentaryPatternInput.value)
            })

            commentaryPatternInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault()
                    addCommentaryPattern(commentaryPatternInput.value)
                }
            })

            // Commentary pattern real-time regex validation (T036) - debounced
            commentaryPatternInput.addEventListener('input', () => {
                clearTimeout(regexValidationTimeout)
                regexValidationTimeout = setTimeout(() => {
                    validateRegexInput(commentaryPatternInput)
                }, 300)
            })
        }

        // Transcription checkboxes
        if (detectCommentaryCheckbox && formState.transcription) {
            detectCommentaryCheckbox.addEventListener('change', () => {
                formState.transcription.detect_commentary = detectCommentaryCheckbox.checked
                // Update reorder checkbox state (disable if detect is off)
                if (reorderCommentaryCheckbox) {
                    reorderCommentaryCheckbox.disabled = !detectCommentaryCheckbox.checked
                    if (!detectCommentaryCheckbox.checked) {
                        reorderCommentaryCheckbox.checked = false
                        formState.transcription.reorder_commentary = false
                    }
                }
                markDirty()
            })
        }

        if (reorderCommentaryCheckbox && formState.transcription) {
            reorderCommentaryCheckbox.addEventListener('change', () => {
                formState.transcription.reorder_commentary = reorderCommentaryCheckbox.checked
                markDirty()
            })
        }

        if (updateLangCheckbox && formState.transcription) {
            updateLangCheckbox.addEventListener('change', () => {
                formState.transcription.update_language_from_transcription = updateLangCheckbox.checked
                markDirty()
            })
        }

        if (confidenceThresholdInput && formState.transcription) {
            confidenceThresholdInput.addEventListener('input', () => {
                const pct = parseFloat(confidenceThresholdInput.value)
                if (!isNaN(pct) && pct >= 0 && pct <= 100) {
                    formState.transcription.confidence_threshold = pct / 100
                    markDirty()
                }
            })
        }

        // Default flags checkboxes
        Object.keys(defaultFlagCheckboxes).forEach(key => {
            const checkbox = defaultFlagCheckboxes[key]
            if (checkbox) {
                checkbox.checked = formState.default_flags[key] || false
                checkbox.addEventListener('change', () => {
                    formState.default_flags[key] = checkbox.checked
                    markDirty()
                })
            }
        })

        // Preferred audio codec input
        if (preferredAudioCodecInput) {
            // Initialize from state
            const codecs = formState.default_flags.preferred_audio_codec
            if (Array.isArray(codecs) && codecs.length > 0) {
                preferredAudioCodecInput.value = codecs.join(', ')
            }
            preferredAudioCodecInput.addEventListener('input', () => {
                const value = preferredAudioCodecInput.value.trim()
                if (value === '') {
                    formState.default_flags.preferred_audio_codec = null
                } else {
                    formState.default_flags.preferred_audio_codec = value
                        .split(',')
                        .map(s => s.trim().toLowerCase())
                        .filter(s => s.length > 0)
                }
                markDirty()
            })
        }

        // Save button
        saveBtn.addEventListener('click', () => {
            savePolicy()
        })

        // Test Policy button (T033)
        const testPolicyBtn = document.getElementById('test-policy-btn')
        if (testPolicyBtn) {
            testPolicyBtn.addEventListener('click', () => {
                testPolicy()
            })
        }

        // Cancel button
        cancelBtn.addEventListener('click', async () => {
            if (formState.isDirty) {
                let confirmed = false
                if (typeof window.ConfirmationModal !== 'undefined') {
                    confirmed = await window.ConfirmationModal.show(
                        'You have unsaved changes. Are you sure you want to discard them?',
                        {
                            title: 'Unsaved Changes',
                            confirmText: 'Discard',
                            cancelText: 'Keep Editing',
                            focusCancel: true
                        }
                    )
                } else {
                    confirmed = confirm('You have unsaved changes. Are you sure you want to discard them?')
                }
                if (confirmed) {
                    window.location.href = '/policies'
                }
            } else {
                window.location.href = '/policies'
            }
        })

        // Warn on navigation if dirty
        window.addEventListener('beforeunload', (e) => {
            if (formState.isDirty) {
                e.preventDefault()
                e.returnValue = 'You have unsaved changes. Are you sure you want to leave?'
            }
        })
    }

    /**
     * Initialize V3-V10 section controllers (036-v9-policy-editor)
     */
    function initSectionControllers() {
        // Initialize transcode section (US1, US2)
        transcodeController = initTranscodeSection(window.POLICY_DATA, (transcodeConfig) => {
            formState.transcode = transcodeConfig
            markDirty()
        })

        // Initialize filters section (US5)
        filtersController = initFiltersSection(window.POLICY_DATA, (filtersConfig) => {
            formState.audio_filter = filtersConfig.audio_filter
            formState.subtitle_filter = filtersConfig.subtitle_filter
            formState.attachment_filter = filtersConfig.attachment_filter
            markDirty()
        })

        // Initialize conditional section (US4)
        conditionalController = initConditionalSection(window.POLICY_DATA, (conditionalConfig) => {
            formState.conditional = conditionalConfig
            markDirty()
        })

        // Initialize synthesis section (US3)
        synthesisController = initSynthesisSection(window.POLICY_DATA, (synthesisConfig) => {
            formState.audio_synthesis = synthesisConfig
            markDirty()
        })

        // Initialize container section (US6)
        containerController = initContainerSection(window.POLICY_DATA, (containerConfig) => {
            formState.container = containerConfig
            markDirty()
        })

        // Initialize workflow section (US7)
        workflowController = initWorkflowSection(window.POLICY_DATA, (workflowConfig) => {
            formState.workflow = workflowConfig
            markDirty()
        })

        // Initialize V11 phases section (037-user-defined-phases)
        phasesController = initPhasesSection(window.POLICY_DATA, (phasesConfig) => {
            formState.phases = phasesConfig.phases
            formState.config = phasesConfig.config
            markDirty()
        })

        // Show unknown fields warning if present
        if (window.POLICY_DATA.unknown_fields && window.POLICY_DATA.unknown_fields.length > 0) {
            const warningEl = document.getElementById('unknown-fields-warning')
            if (warningEl) {
                warningEl.style.display = 'block'
            }
        }
    }

    /**
     * Initialize accessible language autocomplete components (T023)
     */
    function initLanguageAutocomplete() {
        // Audio language autocomplete
        const audioInputGroup = document.querySelector('#audio-lang-input')?.parentElement
        if (audioInputGroup) {
            const existingInput = document.getElementById('audio-lang-input')
            const existingBtn = document.getElementById('audio-lang-add-btn')

            // Create wrapper for autocomplete
            const wrapper = document.createElement('div')
            wrapper.style.flex = '1'

            // Insert wrapper before button
            audioInputGroup.insertBefore(wrapper, existingBtn)

            // Create autocomplete
            const _audioAutocomplete = createLanguageAutocomplete(wrapper, {
                inputId: 'audio-lang-autocomplete',
                listboxId: 'audio-lang-listbox',
                label: 'Add audio language',
                placeholder: 'Type language code or name...',
                onSelect: (code) => {
                    addLanguage('audio', code)
                },
            })

            // Remove original input (keep label)
            if (existingInput) {
                existingInput.style.display = 'none'
            }
            if (existingBtn) {
                existingBtn.style.display = 'none'
            }
        }

        // Subtitle language autocomplete
        const subtitleInputGroup = document.querySelector('#subtitle-lang-input')?.parentElement
        if (subtitleInputGroup) {
            const existingInput = document.getElementById('subtitle-lang-input')
            const existingBtn = document.getElementById('subtitle-lang-add-btn')

            // Create wrapper for autocomplete
            const wrapper = document.createElement('div')
            wrapper.style.flex = '1'

            // Insert wrapper before button
            subtitleInputGroup.insertBefore(wrapper, existingBtn)

            // Create autocomplete
            const _subtitleAutocomplete = createLanguageAutocomplete(wrapper, {
                inputId: 'subtitle-lang-autocomplete',
                listboxId: 'subtitle-lang-listbox',
                label: 'Add subtitle language',
                placeholder: 'Type language code or name...',
                onSelect: (code) => {
                    addLanguage('subtitle', code)
                },
            })

            // Remove original input
            if (existingInput) {
                existingInput.style.display = 'none'
            }
            if (existingBtn) {
                existingBtn.style.display = 'none'
            }
        }
    }

    /**
     * Initialize editor
     */
    function init() {
        renderTrackOrder()
        renderLanguageLists()
        renderCommentaryPatterns()
        updateTranscriptionCheckboxes()
        updateYAMLPreview()
        initEventListeners()
        updateSaveButtonState()

        // Initialize V3-V10 section controllers
        initSectionControllers()

        // Initialize accessible language autocomplete (T023)
        initLanguageAutocomplete()
    }

    // Start the editor
    init()

})()
