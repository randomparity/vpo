/**
 * Policy Editor Main Module (024-policy-editor)
 *
 * Handles policy editing form with track ordering, language preferences,
 * and save functionality with field preservation.
 */

(function () {
    'use strict'

    // Validate that POLICY_DATA is available
    if (typeof window.POLICY_DATA === 'undefined') {
        console.error('POLICY_DATA not found')
        return
    }

    // State management
    let formState = {
        name: window.POLICY_DATA.name,
        last_modified: window.POLICY_DATA.last_modified,
        track_order: [...window.POLICY_DATA.track_order],
        audio_language_preference: [...window.POLICY_DATA.audio_language_preference],
        subtitle_language_preference: [...window.POLICY_DATA.subtitle_language_preference],
        commentary_patterns: [...window.POLICY_DATA.commentary_patterns],
        default_flags: {...window.POLICY_DATA.default_flags},
        transcription: window.POLICY_DATA.transcription ? {...window.POLICY_DATA.transcription} : null,
        isDirty: false,
        isSaving: false
    }

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

    // Default flags checkboxes
    const defaultFlagCheckboxes = {
        set_first_video_default: document.getElementById('set_first_video_default'),
        set_preferred_audio_default: document.getElementById('set_preferred_audio_default'),
        set_preferred_subtitle_default: document.getElementById('set_preferred_subtitle_default'),
        clear_other_defaults: document.getElementById('clear_other_defaults')
    }

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
     */
    function addLanguage(listType, code) {
        // Validate ISO 639-2 code (2-3 lowercase letters)
        const trimmed = code.trim().toLowerCase()
        if (!/^[a-z]{2,3}$/.test(trimmed)) {
            showError(`Invalid language code: "${code}". Use 2-3 letter codes (e.g., eng, jpn, fra).`)
            return
        }

        const list = listType === 'audio' ? formState.audio_language_preference : formState.subtitle_language_preference

        // Check for duplicates
        if (list.includes(trimmed)) {
            showError(`Language "${trimmed}" is already in the list.`)
            return
        }

        list.push(trimmed)
        renderLanguageLists()
        markDirty()

        // Clear input
        if (listType === 'audio') {
            audioLangInput.value = ''
            audioLangInput.focus()
        } else {
            subtitleLangInput.value = ''
            subtitleLangInput.focus()
        }
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
        }
    }

    /**
     * Generate YAML from form state
     */
    function generateYAML() {
        let yaml = `schema_version: ${window.POLICY_DATA.schema_version}\n\n`

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
            yaml += `  ${key}: ${formState.default_flags[key]}\n`
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
     * Update YAML preview with debouncing
     */
    function updateYAMLPreview() {
        if (!yamlPreview) return

        clearTimeout(yamlPreviewTimeout)
        yamlPreviewTimeout = setTimeout(() => {
            yamlPreview.value = generateYAML()
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
        'default_flags': 'default-flags-section'
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

        const requestData = {
            track_order: formState.track_order,
            audio_language_preference: formState.audio_language_preference,
            subtitle_language_preference: formState.subtitle_language_preference,
            commentary_patterns: formState.commentary_patterns,
            default_flags: formState.default_flags,
            transcode: window.POLICY_DATA.transcode,
            transcription: formState.transcription,
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
            formState.isSaving = false
            saveBtn.innerHTML = 'Save Changes'
            saveBtn.setAttribute('aria-busy', 'false')
            updateSaveButtonState()
        }
    }

    /**
     * Test policy without saving (T032)
     * Calls POST /api/policies/{name}/validate
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

        const requestData = {
            track_order: formState.track_order,
            audio_language_preference: formState.audio_language_preference,
            subtitle_language_preference: formState.subtitle_language_preference,
            commentary_patterns: formState.commentary_patterns,
            default_flags: formState.default_flags,
            transcode: window.POLICY_DATA.transcode,
            transcription: formState.transcription,
            last_modified_timestamp: formState.last_modified
        }

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
                const confirmed = await window.ConfirmationModal.show(
                    'You have unsaved changes. Are you sure you want to discard them?',
                    {
                        title: 'Unsaved Changes',
                        confirmText: 'Discard',
                        cancelText: 'Keep Editing',
                        focusCancel: true
                    }
                )
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

        // Make YAML preview read-only (prevent editing while maintaining keyboard access)
        if (yamlPreview) {
            yamlPreview.addEventListener('keydown', (e) => {
                // Allow navigation keys but prevent typing/editing
                const allowedKeys = ['Tab', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Home', 'End', 'PageUp', 'PageDown']
                if (!allowedKeys.includes(e.key) && !e.ctrlKey && !e.metaKey) {
                    e.preventDefault()
                }
            })
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
    }

    // Start the editor
    init()

})()
