/**
 * Policy Editor Main Module (024-policy-editor)
 *
 * Handles policy editing form with track ordering, language preferences,
 * and save functionality with field preservation.
 */

(function() {
    'use strict';

    // Validate that POLICY_DATA is available
    if (typeof window.POLICY_DATA === 'undefined') {
        console.error('POLICY_DATA not found');
        return;
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
    };

    const originalState = JSON.stringify(formState);

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
    };

    // DOM elements
    const trackOrderList = document.getElementById('track-order-list');
    const audioLangInput = document.getElementById('audio-lang-input');
    const audioLangAddBtn = document.getElementById('audio-lang-add-btn');
    const audioLangList = document.getElementById('audio-lang-list');
    const subtitleLangInput = document.getElementById('subtitle-lang-input');
    const subtitleLangAddBtn = document.getElementById('subtitle-lang-add-btn');
    const subtitleLangList = document.getElementById('subtitle-lang-list');
    const commentaryPatternInput = document.getElementById('commentary-pattern-input');
    const commentaryPatternAddBtn = document.getElementById('commentary-pattern-add-btn');
    const commentaryPatternsList = document.getElementById('commentary-patterns-list');
    const detectCommentaryCheckbox = document.getElementById('detect_commentary');
    const reorderCommentaryCheckbox = document.getElementById('reorder_commentary');
    const yamlPreview = document.getElementById('yaml-preview');
    const saveBtn = document.getElementById('save-btn');
    const cancelBtn = document.getElementById('cancel-btn');
    const saveStatus = document.getElementById('save-status');
    const validationErrors = document.getElementById('validation-errors');

    // Default flags checkboxes
    const defaultFlagCheckboxes = {
        set_first_video_default: document.getElementById('set_first_video_default'),
        set_preferred_audio_default: document.getElementById('set_preferred_audio_default'),
        set_preferred_subtitle_default: document.getElementById('set_preferred_subtitle_default'),
        clear_other_defaults: document.getElementById('clear_other_defaults')
    };

    // Debounce timer for YAML preview
    let yamlPreviewTimeout;

    /**
     * Mark form as dirty
     */
    function markDirty() {
        const currentState = JSON.stringify(formState);
        formState.isDirty = (currentState !== originalState);
        updateSaveButtonState();
        updateYAMLPreview();
    }

    /**
     * Update save button state
     */
    function updateSaveButtonState() {
        saveBtn.disabled = !formState.isDirty || formState.isSaving;
    }

    /**
     * Render track order list
     */
    function renderTrackOrder() {
        trackOrderList.innerHTML = '';

        formState.track_order.forEach((trackType, index) => {
            const li = document.createElement('li');
            li.className = 'track-order-item';
            li.dataset.trackType = trackType;

            const label = document.createElement('span');
            label.className = 'track-order-label';
            label.textContent = trackTypeLabels[trackType] || trackType;

            const buttons = document.createElement('div');
            buttons.className = 'track-order-buttons';

            const upBtn = document.createElement('button');
            upBtn.type = 'button';
            upBtn.className = 'btn-icon';
            upBtn.innerHTML = '↑';
            upBtn.title = 'Move up';
            upBtn.disabled = index === 0;
            upBtn.addEventListener('click', () => moveTrackUp(index));

            const downBtn = document.createElement('button');
            downBtn.type = 'button';
            downBtn.className = 'btn-icon';
            downBtn.innerHTML = '↓';
            downBtn.title = 'Move down';
            downBtn.disabled = index === formState.track_order.length - 1;
            downBtn.addEventListener('click', () => moveTrackDown(index));

            buttons.appendChild(upBtn);
            buttons.appendChild(downBtn);

            li.appendChild(label);
            li.appendChild(buttons);
            trackOrderList.appendChild(li);
        });
    }

    /**
     * Move track up in order
     */
    function moveTrackUp(index) {
        if (index === 0) return;
        const temp = formState.track_order[index];
        formState.track_order[index] = formState.track_order[index - 1];
        formState.track_order[index - 1] = temp;
        renderTrackOrder();
        markDirty();
    }

    /**
     * Move track down in order
     */
    function moveTrackDown(index) {
        if (index === formState.track_order.length - 1) return;
        const temp = formState.track_order[index];
        formState.track_order[index] = formState.track_order[index + 1];
        formState.track_order[index + 1] = temp;
        renderTrackOrder();
        markDirty();
    }

    /**
     * Render language list
     */
    function renderLanguageList(listEl, languages, listType) {
        listEl.innerHTML = '';

        if (languages.length === 0) {
            const emptyMsg = document.createElement('li');
            emptyMsg.className = 'language-list-empty';
            emptyMsg.textContent = 'No languages configured';
            listEl.appendChild(emptyMsg);
            return;
        }

        languages.forEach((lang, index) => {
            const li = document.createElement('li');
            li.className = 'language-list-item';

            const label = document.createElement('span');
            label.className = 'language-code';
            label.textContent = lang;

            const buttons = document.createElement('div');
            buttons.className = 'language-buttons';

            const upBtn = document.createElement('button');
            upBtn.type = 'button';
            upBtn.className = 'btn-icon';
            upBtn.innerHTML = '↑';
            upBtn.title = 'Move up';
            upBtn.disabled = index === 0;
            upBtn.addEventListener('click', () => moveLanguageUp(listType, index));

            const downBtn = document.createElement('button');
            downBtn.type = 'button';
            downBtn.className = 'btn-icon';
            downBtn.innerHTML = '↓';
            downBtn.title = 'Move down';
            downBtn.disabled = index === languages.length - 1;
            downBtn.addEventListener('click', () => moveLanguageDown(listType, index));

            const removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.className = 'btn-icon btn-remove';
            removeBtn.innerHTML = '×';
            removeBtn.title = 'Remove';
            removeBtn.addEventListener('click', () => removeLanguage(listType, index));

            buttons.appendChild(upBtn);
            buttons.appendChild(downBtn);
            buttons.appendChild(removeBtn);

            li.appendChild(label);
            li.appendChild(buttons);
            listEl.appendChild(li);
        });
    }

    /**
     * Move language up
     */
    function moveLanguageUp(listType, index) {
        if (index === 0) return;
        const list = listType === 'audio' ? formState.audio_language_preference : formState.subtitle_language_preference;
        const temp = list[index];
        list[index] = list[index - 1];
        list[index - 1] = temp;
        renderLanguageLists();
        markDirty();
    }

    /**
     * Move language down
     */
    function moveLanguageDown(listType, index) {
        const list = listType === 'audio' ? formState.audio_language_preference : formState.subtitle_language_preference;
        if (index === list.length - 1) return;
        const temp = list[index];
        list[index] = list[index + 1];
        list[index + 1] = temp;
        renderLanguageLists();
        markDirty();
    }

    /**
     * Remove language
     */
    function removeLanguage(listType, index) {
        const list = listType === 'audio' ? formState.audio_language_preference : formState.subtitle_language_preference;
        list.splice(index, 1);
        renderLanguageLists();
        markDirty();
    }

    /**
     * Add language
     */
    function addLanguage(listType, code) {
        // Validate ISO 639-2 code (2-3 lowercase letters)
        const trimmed = code.trim().toLowerCase();
        if (!/^[a-z]{2,3}$/.test(trimmed)) {
            showError(`Invalid language code: "${code}". Use 2-3 letter codes (e.g., eng, jpn, fra).`);
            return;
        }

        const list = listType === 'audio' ? formState.audio_language_preference : formState.subtitle_language_preference;

        // Check for duplicates
        if (list.includes(trimmed)) {
            showError(`Language "${trimmed}" is already in the list.`);
            return;
        }

        list.push(trimmed);
        renderLanguageLists();
        markDirty();

        // Clear input
        if (listType === 'audio') {
            audioLangInput.value = '';
            audioLangInput.focus();
        } else {
            subtitleLangInput.value = '';
            subtitleLangInput.focus();
        }
    }

    /**
     * Render all language lists
     */
    function renderLanguageLists() {
        renderLanguageList(audioLangList, formState.audio_language_preference, 'audio');
        renderLanguageList(subtitleLangList, formState.subtitle_language_preference, 'subtitle');
    }

    /**
     * Render commentary patterns list
     */
    function renderCommentaryPatterns() {
        commentaryPatternsList.innerHTML = '';

        if (formState.commentary_patterns.length === 0) {
            const emptyMsg = document.createElement('li');
            emptyMsg.className = 'patterns-list-empty';
            emptyMsg.textContent = 'No patterns configured';
            commentaryPatternsList.appendChild(emptyMsg);
            return;
        }

        formState.commentary_patterns.forEach((pattern, index) => {
            const li = document.createElement('li');
            li.className = 'pattern-list-item';

            const label = document.createElement('span');
            label.className = 'pattern-text';
            label.textContent = pattern;

            const buttons = document.createElement('div');
            buttons.className = 'pattern-buttons';

            const removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.className = 'btn-icon btn-remove';
            removeBtn.innerHTML = '×';
            removeBtn.title = 'Remove pattern';
            removeBtn.addEventListener('click', () => removeCommentaryPattern(index));

            buttons.appendChild(removeBtn);

            li.appendChild(label);
            li.appendChild(buttons);
            commentaryPatternsList.appendChild(li);
        });
    }

    /**
     * Validate regex pattern
     */
    function isValidRegex(pattern) {
        try {
            new RegExp(pattern);
            return true;
        } catch (e) {
            return false;
        }
    }

    /**
     * Add commentary pattern
     */
    function addCommentaryPattern(pattern) {
        const trimmed = pattern.trim();

        if (trimmed === '') {
            showError('Pattern cannot be empty');
            return;
        }

        // Validate regex
        if (!isValidRegex(trimmed)) {
            showError(`Invalid regex pattern: "${trimmed}". Check syntax and try again.`);
            return;
        }

        // Check for duplicates
        if (formState.commentary_patterns.includes(trimmed)) {
            showError(`Pattern "${trimmed}" is already in the list.`);
            return;
        }

        formState.commentary_patterns.push(trimmed);
        renderCommentaryPatterns();
        markDirty();

        // Clear input
        commentaryPatternInput.value = '';
        commentaryPatternInput.focus();
    }

    /**
     * Remove commentary pattern
     */
    function removeCommentaryPattern(index) {
        formState.commentary_patterns.splice(index, 1);
        renderCommentaryPatterns();
        markDirty();
    }

    /**
     * Update transcription checkboxes state
     */
    function updateTranscriptionCheckboxes() {
        if (formState.transcription) {
            if (detectCommentaryCheckbox) {
                detectCommentaryCheckbox.checked = formState.transcription.detect_commentary || false;
            }
            if (reorderCommentaryCheckbox) {
                reorderCommentaryCheckbox.checked = formState.transcription.reorder_commentary || false;
                // Disable reorder if detect is not enabled
                reorderCommentaryCheckbox.disabled = !formState.transcription.detect_commentary;
            }
        }
    }

    /**
     * Generate YAML from form state
     */
    function generateYAML() {
        let yaml = `schema_version: ${window.POLICY_DATA.schema_version}\n\n`;

        // Track order
        yaml += 'track_order:\n';
        formState.track_order.forEach(track => {
            yaml += `  - ${track}\n`;
        });
        yaml += '\n';

        // Audio language preference
        yaml += 'audio_language_preference:\n';
        formState.audio_language_preference.forEach(lang => {
            yaml += `  - ${lang}\n`;
        });
        yaml += '\n';

        // Subtitle language preference
        yaml += 'subtitle_language_preference:\n';
        formState.subtitle_language_preference.forEach(lang => {
            yaml += `  - ${lang}\n`;
        });
        yaml += '\n';

        // Commentary patterns
        yaml += 'commentary_patterns:\n';
        if (formState.commentary_patterns.length === 0) {
            yaml += '  []\n';
        } else {
            formState.commentary_patterns.forEach(pattern => {
                yaml += `  - ${pattern}\n`;
            });
        }
        yaml += '\n';

        // Default flags
        yaml += 'default_flags:\n';
        Object.keys(formState.default_flags).forEach(key => {
            yaml += `  ${key}: ${formState.default_flags[key]}\n`;
        });
        yaml += '\n';

        // Transcode (if exists)
        if (window.POLICY_DATA.transcode) {
            yaml += '# Transcode settings preserved (not editable in UI)\n';
            yaml += 'transcode:\n';
            yaml += '  # ... (original settings preserved)\n\n';
        }

        // Transcription (if exists)
        if (formState.transcription) {
            yaml += 'transcription:\n';
            yaml += `  enabled: ${formState.transcription.enabled}\n`;
            if (formState.transcription.update_language_from_transcription !== undefined) {
                yaml += `  update_language_from_transcription: ${formState.transcription.update_language_from_transcription}\n`;
            }
            if (formState.transcription.confidence_threshold !== undefined) {
                yaml += `  confidence_threshold: ${formState.transcription.confidence_threshold}\n`;
            }
            yaml += `  detect_commentary: ${formState.transcription.detect_commentary}\n`;
            yaml += `  reorder_commentary: ${formState.transcription.reorder_commentary}\n`;
        }

        return yaml;
    }

    /**
     * Update YAML preview with debouncing
     */
    function updateYAMLPreview() {
        if (!yamlPreview) return;

        clearTimeout(yamlPreviewTimeout);
        yamlPreviewTimeout = setTimeout(() => {
            yamlPreview.value = generateYAML();
        }, 300); // 300ms debounce as per spec
    }

    /**
     * Validate form data
     */
    function validateForm() {
        const errors = [];

        if (formState.track_order.length === 0) {
            errors.push('Track order cannot be empty');
        }

        if (formState.audio_language_preference.length === 0) {
            errors.push('Audio language preferences cannot be empty');
        }

        if (formState.subtitle_language_preference.length === 0) {
            errors.push('Subtitle language preferences cannot be empty');
        }

        // Validate commentary patterns (all must be valid regex)
        formState.commentary_patterns.forEach((pattern, index) => {
            if (!isValidRegex(pattern)) {
                errors.push(`Invalid regex pattern at position ${index + 1}: "${pattern}"`);
            }
        });

        // Cross-field validation: reorder_commentary requires detect_commentary
        if (formState.transcription && formState.transcription.reorder_commentary && !formState.transcription.detect_commentary) {
            errors.push('Reorder commentary requires detect commentary to be enabled');
        }

        return errors;
    }

    /**
     * Show error message
     */
    function showError(message) {
        validationErrors.textContent = message;
        validationErrors.style.display = 'block';
        setTimeout(() => {
            validationErrors.style.display = 'none';
        }, 5000);
    }

    /**
     * Show save status
     */
    function showSaveStatus(message, isError = false) {
        saveStatus.textContent = message;
        saveStatus.className = 'save-status ' + (isError ? 'save-status--error' : 'save-status--success');
        setTimeout(() => {
            saveStatus.textContent = '';
            saveStatus.className = 'save-status';
        }, 5000);
    }

    /**
     * Save policy
     */
    async function savePolicy() {
        // Validate
        const errors = validateForm();
        if (errors.length > 0) {
            showError(errors.join('; '));
            return;
        }

        formState.isSaving = true;
        updateSaveButtonState();
        saveStatus.textContent = 'Saving...';

        const requestData = {
            track_order: formState.track_order,
            audio_language_preference: formState.audio_language_preference,
            subtitle_language_preference: formState.subtitle_language_preference,
            commentary_patterns: formState.commentary_patterns,
            default_flags: formState.default_flags,
            transcode: window.POLICY_DATA.transcode,
            transcription: formState.transcription,
            last_modified_timestamp: formState.last_modified
        };

        try {
            const response = await fetch(`/api/policies/${formState.name}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData)
            });

            if (!response.ok) {
                const errorData = await response.json();
                if (response.status === 409) {
                    showError('Concurrent modification detected. Please reload and try again.');
                } else {
                    showError(errorData.error || 'Failed to save policy');
                }
                formState.isSaving = false;
                updateSaveButtonState();
                return;
            }

            const updatedPolicy = await response.json();
            formState.last_modified = updatedPolicy.last_modified;
            formState.isDirty = false;
            formState.isSaving = false;
            updateSaveButtonState();
            showSaveStatus('Policy saved successfully');

        } catch (error) {
            console.error('Save error:', error);
            showError('Network error: ' + error.message);
            formState.isSaving = false;
            updateSaveButtonState();
        }
    }

    /**
     * Initialize event listeners
     */
    function initEventListeners() {
        // Audio language add
        audioLangAddBtn.addEventListener('click', () => {
            addLanguage('audio', audioLangInput.value);
        });

        audioLangInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                addLanguage('audio', audioLangInput.value);
            }
        });

        // Subtitle language add
        subtitleLangAddBtn.addEventListener('click', () => {
            addLanguage('subtitle', subtitleLangInput.value);
        });

        subtitleLangInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                addLanguage('subtitle', subtitleLangInput.value);
            }
        });

        // Commentary pattern add
        if (commentaryPatternAddBtn && commentaryPatternInput) {
            commentaryPatternAddBtn.addEventListener('click', () => {
                addCommentaryPattern(commentaryPatternInput.value);
            });

            commentaryPatternInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    addCommentaryPattern(commentaryPatternInput.value);
                }
            });
        }

        // Transcription checkboxes
        if (detectCommentaryCheckbox && formState.transcription) {
            detectCommentaryCheckbox.addEventListener('change', () => {
                formState.transcription.detect_commentary = detectCommentaryCheckbox.checked;
                // Update reorder checkbox state (disable if detect is off)
                if (reorderCommentaryCheckbox) {
                    reorderCommentaryCheckbox.disabled = !detectCommentaryCheckbox.checked;
                    if (!detectCommentaryCheckbox.checked) {
                        reorderCommentaryCheckbox.checked = false;
                        formState.transcription.reorder_commentary = false;
                    }
                }
                markDirty();
            });
        }

        if (reorderCommentaryCheckbox && formState.transcription) {
            reorderCommentaryCheckbox.addEventListener('change', () => {
                formState.transcription.reorder_commentary = reorderCommentaryCheckbox.checked;
                markDirty();
            });
        }

        // Default flags checkboxes
        Object.keys(defaultFlagCheckboxes).forEach(key => {
            const checkbox = defaultFlagCheckboxes[key];
            if (checkbox) {
                checkbox.checked = formState.default_flags[key] || false;
                checkbox.addEventListener('change', () => {
                    formState.default_flags[key] = checkbox.checked;
                    markDirty();
                });
            }
        });

        // Save button
        saveBtn.addEventListener('click', () => {
            savePolicy();
        });

        // Cancel button
        cancelBtn.addEventListener('click', () => {
            if (formState.isDirty) {
                if (confirm('You have unsaved changes. Are you sure you want to discard them?')) {
                    window.location.href = '/policies';
                }
            } else {
                window.location.href = '/policies';
            }
        });

        // Warn on navigation if dirty
        window.addEventListener('beforeunload', (e) => {
            if (formState.isDirty) {
                e.preventDefault();
                e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
            }
        });
    }

    /**
     * Initialize editor
     */
    function init() {
        renderTrackOrder();
        renderLanguageLists();
        renderCommentaryPatterns();
        updateTranscriptionCheckboxes();
        updateYAMLPreview();
        initEventListeners();
        updateSaveButtonState();
    }

    // Start the editor
    init();

})();
