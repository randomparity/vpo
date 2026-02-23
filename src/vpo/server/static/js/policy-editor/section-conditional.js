/**
 * Conditional Rules Section Module for Policy Editor (036-v9-policy-editor)
 *
 * Handles conditional rules configuration UI with condition builder
 * and action selectors.
 *
 * Features:
 * - Rule list with add/remove controls
 * - Condition types: exists, count, and, or, not, audio_is_multi_language
 * - Track filters: language, codec, is_default, is_forced, channels, width, height, title, not_commentary
 * - Actions: skip_video_transcode, skip_audio_transcode, skip_track_filter, warn, fail
 * - V7 actions: set_forced, set_default
 * - V12 actions: set_container_metadata
 * - V12 conditions: plugin_metadata, container_metadata
 * - 2-level nesting enforcement for boolean conditions
 */

import { showUndoToast, escapeAttr } from './policy-editor.js'

// Constants for condition building
const TRACK_TYPES = [
    { value: 'video', label: 'Video' },
    { value: 'audio', label: 'Audio' },
    { value: 'subtitle', label: 'Subtitle' },
    { value: 'attachment', label: 'Attachment' }
]

const CONDITION_TYPES = [
    { value: 'exists', label: 'Exists (track matches)' },
    { value: 'count', label: 'Count (track count)' },
    { value: 'and', label: 'AND (all must match)' },
    { value: 'or', label: 'OR (any must match)' },
    { value: 'not', label: 'NOT (negate)' },
    { value: 'audio_is_multi_language', label: 'Audio is Multi-Language' },
    { value: 'is_original', label: 'Is Original Audio (V12)' },
    { value: 'is_dubbed', label: 'Is Dubbed Audio (V12)' },
    { value: 'plugin_metadata', label: 'Plugin Metadata (V12)' },
    { value: 'container_metadata', label: 'Container Metadata (V12)' }
]

const METADATA_OPERATORS = [
    { value: 'eq', label: '= (equals)' },
    { value: 'neq', label: '!= (not equals)' },
    { value: 'contains', label: 'Contains (substring)' },
    { value: 'exists', label: 'Exists (field present)' },
    { value: 'lt', label: '< (less than)' },
    { value: 'lte', label: '<= (less or equal)' },
    { value: 'gt', label: '> (greater than)' },
    { value: 'gte', label: '>= (greater or equal)' }
]

const COMPARISON_OPERATORS = [
    { value: 'eq', label: '= (equals)' },
    { value: 'lt', label: '< (less than)' },
    { value: 'lte', label: '<= (less or equal)' },
    { value: 'gt', label: '> (greater than)' },
    { value: 'gte', label: '>= (greater or equal)' }
]

const SKIP_TYPES = [
    { value: 'skip_video_transcode', label: 'Skip Video Transcode' },
    { value: 'skip_audio_transcode', label: 'Skip Audio Transcode' },
    { value: 'skip_track_filter', label: 'Skip Track Filter' }
]

const ACTION_TYPES = [
    { value: 'skip', label: 'Skip Processing' },
    { value: 'warn', label: 'Warn (log message)' },
    { value: 'fail', label: 'Fail (stop with error)' },
    { value: 'set_forced', label: 'Set Forced Flag (V7)' },
    { value: 'set_default', label: 'Set Default Flag (V7)' },
    { value: 'set_language', label: 'Set Language (V7)' },
    { value: 'set_container_metadata', label: 'Set Container Metadata (V12)' }
]

// Common codec options for quick selection (reserved for future use)
const _COMMON_CODECS = {
    video: ['hevc', 'h264', 'vp9', 'av1', 'mpeg2video'],
    audio: ['truehd', 'dts-hd', 'flac', 'aac', 'ac3', 'eac3', 'dts', 'opus'],
    subtitle: ['subrip', 'ass', 'hdmv_pgs_subtitle', 'dvd_subtitle', 'mov_text']
}

/**
 * Generate unique ID for DOM elements
 */
let idCounter = 0
function generateId(prefix = 'cond') {
    return `${prefix}-${++idCounter}`
}

/**
 * Create a track filters builder component
 * @param {Object} filters - Current filter values
 * @param {Function} onUpdate - Callback when filters change
 * @param {string} trackType - Type of track (video, audio, subtitle, attachment)
 * @returns {HTMLElement} Filters container
 */
function createTrackFiltersBuilder(filters, onUpdate, trackType) {
    const container = document.createElement('div')
    container.className = 'track-filters-builder'

    const filtersData = { ...filters }

    function render() {
        container.innerHTML = `
            <div class="filter-row">
                <label class="form-label-inline">Language:</label>
                <input type="text" class="form-input form-input-small" id="${generateId('lang')}"
                       placeholder="e.g., eng or eng,jpn" value="${escapeAttr(filtersData.language || '')}"
                       aria-label="Filter by language code (comma-separated)">
            </div>
            <div class="filter-row">
                <label class="form-label-inline">Codec:</label>
                <input type="text" class="form-input form-input-small" id="${generateId('codec')}"
                       placeholder="e.g., hevc or hevc,h264" value="${escapeAttr(filtersData.codec || '')}"
                       aria-label="Filter by codec (comma-separated)">
            </div>
            <div class="filter-row filter-checkboxes">
                <label class="checkbox-label">
                    <input type="checkbox" id="${generateId('default')}" ${filtersData.is_default === true ? 'checked' : ''}
                           ${filtersData.is_default === false ? 'data-unchecked="true"' : ''}
                           aria-label="Filter for default tracks">
                    Is Default
                </label>
                <label class="checkbox-label">
                    <input type="checkbox" id="${generateId('forced')}" ${filtersData.is_forced === true ? 'checked' : ''}
                           ${filtersData.is_forced === false ? 'data-unchecked="true"' : ''}
                           aria-label="Filter for forced tracks">
                    Is Forced
                </label>
                <label class="checkbox-label">
                    <input type="checkbox" id="${generateId('notcomm')}" ${filtersData.not_commentary === true ? 'checked' : ''}
                           aria-label="Exclude commentary tracks">
                    Not Commentary (V8)
                </label>
            </div>
            ${trackType === 'audio' ? `
            <div class="filter-row">
                <label class="form-label-inline">Channels:</label>
                <select class="form-select form-select-small" id="${generateId('chanop')}"
                        aria-label="Channel count comparison operator">
                    <option value="">Any</option>
                    ${COMPARISON_OPERATORS.map(op => `<option value="${op.value}">${op.label}</option>`).join('')}
                </select>
                <input type="number" class="form-input form-input-small" id="${generateId('chanval')}"
                       placeholder="e.g., 6" min="1" max="32" value="${filtersData.channels?.value || ''}"
                       aria-label="Channel count value">
            </div>
            ` : ''}
            ${trackType === 'video' ? `
            <div class="filter-row">
                <label class="form-label-inline">Width:</label>
                <select class="form-select form-select-small" id="${generateId('widthop')}"
                        aria-label="Width comparison operator">
                    <option value="">Any</option>
                    ${COMPARISON_OPERATORS.map(op => `<option value="${op.value}">${op.label}</option>`).join('')}
                </select>
                <input type="number" class="form-input form-input-small" id="${generateId('widthval')}"
                       placeholder="e.g., 1920" min="1" value="${filtersData.width?.value || ''}"
                       aria-label="Width value in pixels">
            </div>
            <div class="filter-row">
                <label class="form-label-inline">Height:</label>
                <select class="form-select form-select-small" id="${generateId('heightop')}"
                        aria-label="Height comparison operator">
                    <option value="">Any</option>
                    ${COMPARISON_OPERATORS.map(op => `<option value="${op.value}">${op.label}</option>`).join('')}
                </select>
                <input type="number" class="form-input form-input-small" id="${generateId('heightval')}"
                       placeholder="e.g., 1080" min="1" value="${filtersData.height?.value || ''}"
                       aria-label="Height value in pixels">
            </div>
            ` : ''}
            <div class="filter-row">
                <label class="form-label-inline">Title:</label>
                <select class="form-select form-select-small" id="${generateId('titlemode')}"
                        aria-label="Title match mode">
                    <option value="contains" ${!filtersData.title?.regex ? 'selected' : ''}>Contains</option>
                    <option value="regex" ${filtersData.title?.regex ? 'selected' : ''}>Regex</option>
                </select>
                <input type="text" class="form-input form-input-small" id="${generateId('title')}"
                       placeholder="${filtersData.title?.regex ? 'Regex pattern' : 'Substring match'}"
                       value="${escapeAttr(filtersData.title?.regex || filtersData.title?.contains || filtersData.title || '')}"
                       aria-label="Filter by title">
            </div>
        `

        // Attach event listeners with debouncing for inputs (M5)
        let filterDebounceTimer
        const debouncedCollect = () => {
            clearTimeout(filterDebounceTimer)
            filterDebounceTimer = setTimeout(collectFilters, 150)
        }
        container.querySelectorAll('input, select').forEach(el => {
            el.addEventListener('change', collectFilters) // Immediate on change
            el.addEventListener('input', debouncedCollect) // Debounced on input
        })
    }

    function collectFilters() {
        const inputs = container.querySelectorAll('input, select')
        const newFilters = {}

        inputs.forEach(input => {
            const id = input.id
            if (id.includes('-lang-')) {
                if (input.value.trim()) {
                    const langs = input.value.split(',').map(l => l.trim()).filter(Boolean)
                    newFilters.language = langs.length === 1 ? langs[0] : langs
                }
            } else if (id.includes('-codec-')) {
                if (input.value.trim()) {
                    const codecs = input.value.split(',').map(c => c.trim()).filter(Boolean)
                    newFilters.codec = codecs.length === 1 ? codecs[0] : codecs
                }
            } else if (id.includes('-default-') && input.checked) {
                newFilters.is_default = true
            } else if (id.includes('-forced-') && input.checked) {
                newFilters.is_forced = true
            } else if (id.includes('-notcomm-') && input.checked) {
                newFilters.not_commentary = true
            } else if (id.includes('-chanop-') && input.value) {
                // Find the corresponding value input
                const valInput = container.querySelector('[id*="-chanval-"]')
                if (valInput && valInput.value) {
                    newFilters.channels = { operator: input.value, value: parseInt(valInput.value, 10) }
                }
            } else if (id.includes('-widthop-') && input.value) {
                const valInput = container.querySelector('[id*="-widthval-"]')
                if (valInput && valInput.value) {
                    newFilters.width = { operator: input.value, value: parseInt(valInput.value, 10) }
                }
            } else if (id.includes('-heightop-') && input.value) {
                const valInput = container.querySelector('[id*="-heightval-"]')
                if (valInput && valInput.value) {
                    newFilters.height = { operator: input.value, value: parseInt(valInput.value, 10) }
                }
            } else if (id.includes('-title-') && input.value.trim()) {
                const modeSelect = container.querySelector('[id*="-titlemode-"]')
                const mode = modeSelect ? modeSelect.value : 'contains'
                if (mode === 'regex') {
                    newFilters.title = { regex: input.value.trim() }
                } else {
                    newFilters.title = { contains: input.value.trim() }
                }
            }
        })

        Object.assign(filtersData, newFilters)
        onUpdate(newFilters)
    }

    render()
    return container
}

/**
 * Create a condition builder component
 * @param {Object} condition - Current condition data
 * @param {Function} onUpdate - Callback when condition changes
 * @param {number} nestingLevel - Current nesting depth (max 2)
 * @returns {HTMLElement} Condition builder container
 */
function createConditionBuilder(condition, onUpdate, nestingLevel = 0) {
    const container = document.createElement('div')
    container.className = 'condition-builder'
    container.dataset.level = nestingLevel

    const condData = condition ? { ...condition } : { type: 'exists' }

    function getConditionType(cond) {
        if (!cond) return 'exists'
        if (cond._type === 'is_original') return 'is_original'
        if (cond._type === 'is_dubbed') return 'is_dubbed'
        if (cond._type === 'plugin_metadata') return 'plugin_metadata'
        if (cond._type === 'container_metadata') return 'container_metadata'
        if (cond.conditions && Array.isArray(cond.conditions)) {
            // Check if it's AND or OR based on presence of specific markers
            // In the data model, AndCondition and OrCondition both have 'conditions' array
            // We need to check the actual type
            if (cond._type === 'or') return 'or'
            return 'and'
        }
        if (cond.inner !== undefined) return 'not'
        if (cond.track_index !== undefined || cond.threshold !== undefined) return 'audio_is_multi_language'
        if (cond.operator !== undefined && cond.value !== undefined) return 'count'
        if (cond.track_type !== undefined) return 'exists'
        return 'exists'
    }

    function render() {
        const currentType = condData._type || getConditionType(condData)

        // For nested conditions, limit available types (no further boolean nesting at level 2+)
        const availableTypes = nestingLevel >= 2
            ? CONDITION_TYPES.filter(t => !['and', 'or', 'not'].includes(t.value))
            : CONDITION_TYPES

        container.innerHTML = `
            <div class="condition-type-row">
                <label class="form-label-inline">Condition Type:</label>
                <select class="form-select condition-type-select">
                    ${availableTypes.map(t => `<option value="${t.value}" ${currentType === t.value ? 'selected' : ''}>${t.label}</option>`).join('')}
                </select>
            </div>
            <div class="condition-details"></div>
        `

        const typeSelect = container.querySelector('.condition-type-select')
        const detailsDiv = container.querySelector('.condition-details')

        typeSelect.addEventListener('change', () => {
            condData._type = typeSelect.value
            renderDetails()
            onUpdate(buildCondition())
        })

        condData._type = currentType

        function renderDetails() {
            const type = condData._type

            if (type === 'exists') {
                detailsDiv.innerHTML = `
                    <div class="condition-field-row">
                        <label class="form-label-inline">Track Type:</label>
                        <select class="form-select track-type-select">
                            ${TRACK_TYPES.map(t => `<option value="${t.value}" ${condData.track_type === t.value ? 'selected' : ''}>${t.label}</option>`).join('')}
                        </select>
                    </div>
                    <div class="filters-container"></div>
                `
                const trackTypeSelect = detailsDiv.querySelector('.track-type-select')
                const filtersContainer = detailsDiv.querySelector('.filters-container')

                condData.track_type = condData.track_type || 'video'
                trackTypeSelect.value = condData.track_type

                const filtersBuilder = createTrackFiltersBuilder(
                    condData.filters || {},
                    (filters) => {
                        condData.filters = filters
                        onUpdate(buildCondition())
                    },
                    condData.track_type
                )
                filtersContainer.appendChild(filtersBuilder)

                trackTypeSelect.addEventListener('change', () => {
                    condData.track_type = trackTypeSelect.value
                    // Re-render filters for new track type
                    filtersContainer.innerHTML = ''
                    const newFiltersBuilder = createTrackFiltersBuilder(
                        {},
                        (filters) => {
                            condData.filters = filters
                            onUpdate(buildCondition())
                        },
                        condData.track_type
                    )
                    filtersContainer.appendChild(newFiltersBuilder)
                    onUpdate(buildCondition())
                })
            } else if (type === 'count') {
                detailsDiv.innerHTML = `
                    <div class="condition-field-row">
                        <label class="form-label-inline">Track Type:</label>
                        <select class="form-select track-type-select">
                            ${TRACK_TYPES.map(t => `<option value="${t.value}" ${condData.track_type === t.value ? 'selected' : ''}>${t.label}</option>`).join('')}
                        </select>
                    </div>
                    <div class="condition-field-row">
                        <label class="form-label-inline">Count:</label>
                        <select class="form-select operator-select">
                            ${COMPARISON_OPERATORS.map(op => `<option value="${op.value}" ${condData.operator === op.value ? 'selected' : ''}>${op.label}</option>`).join('')}
                        </select>
                        <input type="number" class="form-input form-input-small count-value" min="0" value="${condData.value || 0}">
                    </div>
                    <div class="filters-container"></div>
                `
                const trackTypeSelect = detailsDiv.querySelector('.track-type-select')
                const operatorSelect = detailsDiv.querySelector('.operator-select')
                const countInput = detailsDiv.querySelector('.count-value')
                const filtersContainer = detailsDiv.querySelector('.filters-container')

                condData.track_type = condData.track_type || 'audio'
                condData.operator = condData.operator || 'gte'
                condData.value = condData.value || 1

                const filtersBuilder = createTrackFiltersBuilder(
                    condData.filters || {},
                    (filters) => {
                        condData.filters = filters
                        onUpdate(buildCondition())
                    },
                    condData.track_type
                )
                filtersContainer.appendChild(filtersBuilder)

                trackTypeSelect.addEventListener('change', () => {
                    condData.track_type = trackTypeSelect.value
                    filtersContainer.innerHTML = ''
                    const newFiltersBuilder = createTrackFiltersBuilder(
                        {},
                        (filters) => {
                            condData.filters = filters
                            onUpdate(buildCondition())
                        },
                        condData.track_type
                    )
                    filtersContainer.appendChild(newFiltersBuilder)
                    onUpdate(buildCondition())
                })
                operatorSelect.addEventListener('change', () => {
                    condData.operator = operatorSelect.value
                    onUpdate(buildCondition())
                })
                countInput.addEventListener('input', () => {
                    condData.value = parseInt(countInput.value, 10) || 0
                    onUpdate(buildCondition())
                })
            } else if (type === 'and' || type === 'or') {
                condData.conditions = condData.conditions || []
                detailsDiv.innerHTML = `
                    <div class="sub-conditions-list"></div>
                    <button type="button" class="btn-secondary btn-small add-sub-condition">Add Sub-Condition</button>
                `
                const subCondList = detailsDiv.querySelector('.sub-conditions-list')
                const addBtn = detailsDiv.querySelector('.add-sub-condition')

                function renderSubConditions() {
                    subCondList.innerHTML = ''
                    condData.conditions.forEach((subCond, idx) => {
                        const wrapper = document.createElement('div')
                        wrapper.className = 'sub-condition-wrapper'

                        const removeBtn = document.createElement('button')
                        removeBtn.type = 'button'
                        removeBtn.className = 'btn-icon btn-remove-sub'
                        removeBtn.textContent = '\u00d7'
                        removeBtn.title = 'Remove sub-condition'
                        removeBtn.setAttribute('aria-label', 'Remove this sub-condition')
                        removeBtn.onclick = () => {
                            // H3: Undo toast for sub-condition removal
                            const removedCond = condData.conditions.splice(idx, 1)[0]
                            const removedIdx = idx
                            renderSubConditions()
                            onUpdate(buildCondition())

                            showUndoToast('Sub-condition removed', () => {
                                condData.conditions.splice(removedIdx, 0, removedCond)
                                renderSubConditions()
                                onUpdate(buildCondition())
                            })
                        }

                        const subBuilder = createConditionBuilder(
                            subCond,
                            (updated) => {
                                condData.conditions[idx] = updated
                                onUpdate(buildCondition())
                            },
                            nestingLevel + 1
                        )

                        wrapper.appendChild(removeBtn)
                        wrapper.appendChild(subBuilder)
                        subCondList.appendChild(wrapper)
                    })
                }

                renderSubConditions()

                addBtn.onclick = () => {
                    condData.conditions.push({ _type: 'exists', track_type: 'audio' })
                    renderSubConditions()
                    onUpdate(buildCondition())

                    // H1: Focus management - focus the new sub-condition's type select
                    const typeSelects = subCondList.querySelectorAll('.condition-type-select')
                    const lastSelect = typeSelects[typeSelects.length - 1]
                    if (lastSelect) {
                        lastSelect.focus()
                    }
                }
            } else if (type === 'not') {
                detailsDiv.innerHTML = `
                    <div class="sub-condition-wrapper">
                        <span class="not-label">Negate:</span>
                        <div class="inner-condition-container"></div>
                    </div>
                `
                const innerContainer = detailsDiv.querySelector('.inner-condition-container')
                const innerBuilder = createConditionBuilder(
                    condData.inner || { _type: 'exists', track_type: 'audio' },
                    (updated) => {
                        condData.inner = updated
                        onUpdate(buildCondition())
                    },
                    nestingLevel + 1
                )
                innerContainer.appendChild(innerBuilder)
            } else if (type === 'audio_is_multi_language') {
                detailsDiv.innerHTML = `
                    <div class="condition-field-row">
                        <label class="form-label-inline">Track Index:</label>
                        <input type="number" class="form-input form-input-small track-index-input"
                               placeholder="All tracks" min="0" value="${condData.track_index ?? ''}">
                        <span class="form-hint">Leave empty to check all audio tracks</span>
                    </div>
                    <div class="condition-field-row">
                        <label class="form-label-inline">Threshold (%):</label>
                        <input type="number" class="form-input form-input-small threshold-input"
                               min="0" max="100" step="1" value="${(condData.threshold || 0.05) * 100}">
                        <span class="form-hint">Secondary language percentage to trigger</span>
                    </div>
                    <div class="condition-field-row">
                        <label class="form-label-inline">Primary Language:</label>
                        <input type="text" class="form-input form-input-small primary-lang-input"
                               placeholder="e.g., jpn (optional)" value="${condData.primary_language || ''}">
                    </div>
                `
                const trackIndexInput = detailsDiv.querySelector('.track-index-input')
                const thresholdInput = detailsDiv.querySelector('.threshold-input')
                const primaryLangInput = detailsDiv.querySelector('.primary-lang-input')

                trackIndexInput.addEventListener('input', () => {
                    condData.track_index = trackIndexInput.value ? parseInt(trackIndexInput.value, 10) : null
                    onUpdate(buildCondition())
                })
                thresholdInput.addEventListener('input', () => {
                    condData.threshold = (parseFloat(thresholdInput.value) || 5) / 100
                    onUpdate(buildCondition())
                })
                primaryLangInput.addEventListener('input', () => {
                    condData.primary_language = primaryLangInput.value.trim() || null
                    onUpdate(buildCondition())
                })
            } else if (type === 'is_original' || type === 'is_dubbed') {
                const labelPrefix = type === 'is_original' ? 'Original' : 'Dubbed'
                detailsDiv.innerHTML = `
                    <div class="condition-field-row">
                        <label class="checkbox-label">
                            <input type="checkbox" class="value-checkbox" ${condData.value !== false ? 'checked' : ''}>
                            Track is ${labelPrefix.toLowerCase()}
                        </label>
                    </div>
                    <div class="condition-field-row">
                        <label class="form-label-inline">Min Confidence (%):</label>
                        <input type="number" class="form-input form-input-small confidence-input"
                               min="0" max="100" step="1" value="${(condData.min_confidence ?? 0.7) * 100}">
                        <span class="form-hint">Minimum confidence threshold (default 70%)</span>
                    </div>
                    <div class="condition-field-row">
                        <label class="form-label-inline">Language:</label>
                        <input type="text" class="form-input form-input-small language-input"
                               placeholder="e.g., eng (optional)" value="${escapeAttr(condData.language || '')}">
                        <span class="form-hint">Limit check to specific language</span>
                    </div>
                `
                const valueCheckbox = detailsDiv.querySelector('.value-checkbox')
                const confidenceInput = detailsDiv.querySelector('.confidence-input')
                const languageInput = detailsDiv.querySelector('.language-input')

                valueCheckbox.addEventListener('change', () => {
                    condData.value = valueCheckbox.checked
                    onUpdate(buildCondition())
                })
                confidenceInput.addEventListener('input', () => {
                    condData.min_confidence = (parseFloat(confidenceInput.value) || 70) / 100
                    onUpdate(buildCondition())
                })
                languageInput.addEventListener('input', () => {
                    condData.language = languageInput.value.trim() || null
                    onUpdate(buildCondition())
                })
            } else if (type === 'plugin_metadata') {
                detailsDiv.innerHTML = `
                    <div class="condition-field-row">
                        <label class="form-label-inline">Plugin:</label>
                        <input type="text" class="form-input form-input-small plugin-name-input"
                               placeholder="e.g., radarr_metadata" value="${escapeAttr(condData.plugin || '')}">
                    </div>
                    <div class="condition-field-row">
                        <label class="form-label-inline">Field:</label>
                        <input type="text" class="form-input form-input-small field-input"
                               placeholder="e.g., title" value="${escapeAttr(condData.field || '')}">
                    </div>
                    <div class="condition-field-row">
                        <label class="form-label-inline">Operator:</label>
                        <select class="form-select operator-select">
                            ${METADATA_OPERATORS.map(op => `<option value="${op.value}" ${condData.operator === op.value ? 'selected' : ''}>${op.label}</option>`).join('')}
                        </select>
                    </div>
                    <div class="condition-field-row value-row">
                        <label class="form-label-inline">Value:</label>
                        <input type="text" class="form-input form-input-small value-input"
                               placeholder="Value to compare" value="${escapeAttr(condData.value ?? '')}">
                        <span class="form-hint">Not required for 'exists' operator</span>
                    </div>
                `
                const pluginInput = detailsDiv.querySelector('.plugin-name-input')
                const fieldInput = detailsDiv.querySelector('.field-input')
                const operatorSelect = detailsDiv.querySelector('.operator-select')
                const valueInput = detailsDiv.querySelector('.value-input')
                const valueRow = detailsDiv.querySelector('.value-row')

                condData.operator = condData.operator || 'eq'
                operatorSelect.value = condData.operator
                valueRow.style.display = condData.operator === 'exists' ? 'none' : ''

                pluginInput.addEventListener('input', () => {
                    condData.plugin = pluginInput.value.trim() || null
                    onUpdate(buildCondition())
                })
                fieldInput.addEventListener('input', () => {
                    condData.field = fieldInput.value.trim() || null
                    onUpdate(buildCondition())
                })
                operatorSelect.addEventListener('change', () => {
                    condData.operator = operatorSelect.value
                    valueRow.style.display = condData.operator === 'exists' ? 'none' : ''
                    onUpdate(buildCondition())
                })
                valueInput.addEventListener('input', () => {
                    condData.value = valueInput.value
                    onUpdate(buildCondition())
                })
            } else if (type === 'container_metadata') {
                detailsDiv.innerHTML = `
                    <div class="condition-field-row">
                        <label class="form-label-inline">Field:</label>
                        <input type="text" class="form-input form-input-small field-input"
                               placeholder="e.g., title, encoder" value="${escapeAttr(condData.field || '')}">
                    </div>
                    <div class="condition-field-row">
                        <label class="form-label-inline">Operator:</label>
                        <select class="form-select operator-select">
                            ${METADATA_OPERATORS.map(op => `<option value="${op.value}" ${condData.operator === op.value ? 'selected' : ''}>${op.label}</option>`).join('')}
                        </select>
                    </div>
                    <div class="condition-field-row value-row">
                        <label class="form-label-inline">Value:</label>
                        <input type="text" class="form-input form-input-small value-input"
                               placeholder="Value to compare" value="${escapeAttr(condData.value ?? '')}">
                        <span class="form-hint">Not required for 'exists' operator</span>
                    </div>
                `
                const fieldInput = detailsDiv.querySelector('.field-input')
                const operatorSelect = detailsDiv.querySelector('.operator-select')
                const valueInput = detailsDiv.querySelector('.value-input')
                const valueRow = detailsDiv.querySelector('.value-row')

                condData.operator = condData.operator || 'eq'
                operatorSelect.value = condData.operator
                valueRow.style.display = condData.operator === 'exists' ? 'none' : ''

                fieldInput.addEventListener('input', () => {
                    condData.field = fieldInput.value.trim() || null
                    onUpdate(buildCondition())
                })
                operatorSelect.addEventListener('change', () => {
                    condData.operator = operatorSelect.value
                    valueRow.style.display = condData.operator === 'exists' ? 'none' : ''
                    onUpdate(buildCondition())
                })
                valueInput.addEventListener('input', () => {
                    condData.value = valueInput.value
                    onUpdate(buildCondition())
                })
            }
        }

        renderDetails()
    }

    function buildCondition() {
        const type = condData._type

        if (type === 'exists') {
            const result = { track_type: condData.track_type || 'video' }
            if (condData.filters && Object.keys(condData.filters).length > 0) {
                result.filters = condData.filters
            }
            return result
        } else if (type === 'count') {
            const result = {
                track_type: condData.track_type || 'audio',
                operator: condData.operator || 'gte',
                value: condData.value || 1
            }
            if (condData.filters && Object.keys(condData.filters).length > 0) {
                result.filters = condData.filters
            }
            return result
        } else if (type === 'and') {
            return {
                _type: 'and',
                conditions: condData.conditions || []
            }
        } else if (type === 'or') {
            return {
                _type: 'or',
                conditions: condData.conditions || []
            }
        } else if (type === 'not') {
            return {
                _type: 'not',
                inner: condData.inner || { track_type: 'audio' }
            }
        } else if (type === 'audio_is_multi_language') {
            const result = {
                _type: 'audio_is_multi_language'
            }
            if (condData.track_index !== null && condData.track_index !== undefined) {
                result.track_index = condData.track_index
            }
            if (condData.threshold && condData.threshold !== 0.05) {
                result.threshold = condData.threshold
            }
            if (condData.primary_language) {
                result.primary_language = condData.primary_language
            }
            return result
        } else if (type === 'is_original' || type === 'is_dubbed') {
            const result = {
                _type: type,
                value: condData.value !== false
            }
            const conf = condData.min_confidence
            if (conf !== undefined && conf !== null && conf !== 0.7) {
                result.min_confidence = conf
            }
            if (condData.language) {
                result.language = condData.language
            }
            return result
        } else if (type === 'plugin_metadata') {
            const result = {
                _type: 'plugin_metadata',
                plugin: condData.plugin || '',
                field: condData.field || '',
                operator: condData.operator || 'eq'
            }
            if (condData.operator !== 'exists' && condData.value !== undefined && condData.value !== '') {
                result.value = condData.value
            }
            return result
        } else if (type === 'container_metadata') {
            const result = {
                _type: 'container_metadata',
                field: condData.field || '',
                operator: condData.operator || 'eq'
            }
            if (condData.operator !== 'exists' && condData.value !== undefined && condData.value !== '') {
                result.value = condData.value
            }
            return result
        }
        return condData
    }

    render()
    return container
}

/**
 * Create an action builder component
 * @param {Object} action - Current action data
 * @param {Function} onUpdate - Callback when action changes
 * @returns {HTMLElement} Action builder container
 */
function createActionBuilder(action, onUpdate) {
    const container = document.createElement('div')
    container.className = 'action-builder'

    const actionData = action ? { ...action } : { type: 'skip', skip_type: 'skip_video_transcode' }

    function getActionType(act) {
        if (!act) return 'skip'
        if (act._type === 'set_container_metadata') return 'set_container_metadata'
        if (act._type === 'set_language') return 'set_language'
        if (act.skip_type) return 'skip'
        if (act.message !== undefined && act._type === 'fail') return 'fail'
        if (act.message !== undefined) return 'warn'
        if (act._type === 'set_forced' || act.track_type === 'subtitle') return 'set_forced'
        if (act._type === 'set_default') return 'set_default'
        return 'skip'
    }

    function render() {
        const currentType = actionData._type || getActionType(actionData)

        container.innerHTML = `
            <div class="action-type-row">
                <select class="form-select action-type-select">
                    ${ACTION_TYPES.map(t => `<option value="${t.value}" ${currentType === t.value ? 'selected' : ''}>${t.label}</option>`).join('')}
                </select>
                <div class="action-details"></div>
            </div>
        `

        const typeSelect = container.querySelector('.action-type-select')
        const detailsDiv = container.querySelector('.action-details')

        actionData._type = currentType

        function renderDetails() {
            const type = actionData._type

            if (type === 'skip') {
                detailsDiv.innerHTML = `
                    <select class="form-select skip-type-select">
                        ${SKIP_TYPES.map(t => `<option value="${t.value}" ${actionData.skip_type === t.value ? 'selected' : ''}>${t.label}</option>`).join('')}
                    </select>
                `
                const skipSelect = detailsDiv.querySelector('.skip-type-select')
                actionData.skip_type = actionData.skip_type || 'skip_video_transcode'

                skipSelect.addEventListener('change', () => {
                    actionData.skip_type = skipSelect.value
                    onUpdate(buildAction())
                })
            } else if (type === 'warn' || type === 'fail') {
                detailsDiv.innerHTML = `
                    <input type="text" class="form-input message-input" placeholder="Message (supports {filename}, {path}, {rule_name})"
                           value="${escapeAttr(actionData.message || '')}">
                `
                const msgInput = detailsDiv.querySelector('.message-input')
                msgInput.addEventListener('input', () => {
                    actionData.message = msgInput.value
                    onUpdate(buildAction())
                })
            } else if (type === 'set_forced' || type === 'set_default') {
                detailsDiv.innerHTML = `
                    <select class="form-select track-type-select">
                        ${TRACK_TYPES.map(t => `<option value="${t.value}" ${actionData.track_type === t.value ? 'selected' : ''}>${t.label}</option>`).join('')}
                    </select>
                    <input type="text" class="form-input form-input-small lang-input" placeholder="Language (optional)"
                           value="${escapeAttr(actionData.language || '')}">
                    <label class="checkbox-label">
                        <input type="checkbox" class="value-checkbox" ${actionData.value !== false ? 'checked' : ''}>
                        Value
                    </label>
                `
                const trackSelect = detailsDiv.querySelector('.track-type-select')
                const langInput = detailsDiv.querySelector('.lang-input')
                const valueCheckbox = detailsDiv.querySelector('.value-checkbox')

                actionData.track_type = actionData.track_type || (type === 'set_forced' ? 'subtitle' : 'audio')

                trackSelect.addEventListener('change', () => {
                    actionData.track_type = trackSelect.value
                    onUpdate(buildAction())
                })
                langInput.addEventListener('input', () => {
                    actionData.language = langInput.value.trim() || null
                    onUpdate(buildAction())
                })
                valueCheckbox.addEventListener('change', () => {
                    actionData.value = valueCheckbox.checked
                    onUpdate(buildAction())
                })
            } else if (type === 'set_language') {
                detailsDiv.innerHTML = `
                    <div class="action-field-row">
                        <label class="form-label-inline">Track Type:</label>
                        <select class="form-select track-type-select">
                            ${TRACK_TYPES.map(t => `<option value="${t.value}" ${actionData.track_type === t.value ? 'selected' : ''}>${t.label}</option>`).join('')}
                        </select>
                    </div>
                    <div class="action-field-row">
                        <label class="form-label-inline">New Language:</label>
                        <input type="text" class="form-input form-input-small new-lang-input"
                               placeholder="e.g., eng" value="${escapeAttr(actionData.new_language || '')}">
                    </div>
                    <div class="action-field-row">
                        <label class="form-label-inline">Match Language:</label>
                        <input type="text" class="form-input form-input-small match-lang-input"
                               placeholder="Optional: only match tracks with this language" value="${escapeAttr(actionData.match_language || '')}">
                        <span class="form-hint">Only apply to tracks with this current language</span>
                    </div>
                `
                const trackSelect = detailsDiv.querySelector('.track-type-select')
                const newLangInput = detailsDiv.querySelector('.new-lang-input')
                const matchLangInput = detailsDiv.querySelector('.match-lang-input')

                actionData.track_type = actionData.track_type || 'audio'

                trackSelect.addEventListener('change', () => {
                    actionData.track_type = trackSelect.value
                    onUpdate(buildAction())
                })
                newLangInput.addEventListener('input', () => {
                    actionData.new_language = newLangInput.value.trim() || null
                    onUpdate(buildAction())
                })
                matchLangInput.addEventListener('input', () => {
                    actionData.match_language = matchLangInput.value.trim() || null
                    onUpdate(buildAction())
                })
            } else if (type === 'set_container_metadata') {
                detailsDiv.innerHTML = `
                    <div class="action-field-row">
                        <label class="form-label-inline">Field:</label>
                        <input type="text" class="form-input form-input-small field-input"
                               placeholder="e.g., title, encoder" value="${escapeAttr(actionData.field || '')}">
                    </div>
                    <div class="action-field-row">
                        <label class="form-label-inline">Value:</label>
                        <input type="text" class="form-input value-input"
                               placeholder="New value (empty to clear)" value="${escapeAttr(actionData.value ?? '')}">
                        <span class="form-hint">Leave empty to clear/delete the tag</span>
                    </div>
                `
                const fieldInput = detailsDiv.querySelector('.field-input')
                const valueInput = detailsDiv.querySelector('.value-input')

                fieldInput.addEventListener('input', () => {
                    actionData.field = fieldInput.value.trim()
                    onUpdate(buildAction())
                })
                valueInput.addEventListener('input', () => {
                    actionData.value = valueInput.value
                    onUpdate(buildAction())
                })
            }
        }

        typeSelect.addEventListener('change', () => {
            actionData._type = typeSelect.value
            renderDetails()
            onUpdate(buildAction())
        })

        renderDetails()
    }

    function buildAction() {
        const type = actionData._type

        if (type === 'skip') {
            return { skip_type: actionData.skip_type || 'skip_video_transcode' }
        } else if (type === 'warn') {
            return { _type: 'warn', message: actionData.message || '' }
        } else if (type === 'fail') {
            return { _type: 'fail', message: actionData.message || '' }
        } else if (type === 'set_forced') {
            const result = { _type: 'set_forced', track_type: actionData.track_type || 'subtitle' }
            if (actionData.language) result.language = actionData.language
            if (actionData.value === false) result.value = false
            return result
        } else if (type === 'set_default') {
            const result = { _type: 'set_default', track_type: actionData.track_type || 'audio' }
            if (actionData.language) result.language = actionData.language
            if (actionData.value === false) result.value = false
            return result
        } else if (type === 'set_language') {
            const result = {
                _type: 'set_language',
                track_type: actionData.track_type || 'audio'
            }
            if (actionData.new_language) {
                result.new_language = actionData.new_language
            }
            if (actionData.match_language) {
                result.match_language = actionData.match_language
            }
            return result
        } else if (type === 'set_container_metadata') {
            const result = {
                _type: 'set_container_metadata',
                field: actionData.field || ''
            }
            if (actionData.value !== undefined) {
                result.value = actionData.value
            }
            return result
        }
        return actionData
    }

    render()
    return container
}

/**
 * Create an actions list component
 * @param {Array} actions - Current list of actions
 * @param {Function} onUpdate - Callback when actions change
 * @param {string} label - Label for the actions list
 * @returns {HTMLElement} Actions list container
 */
function createActionsList(actions, onUpdate, label) {
    const container = document.createElement('div')
    container.className = 'actions-list'

    const actionsData = actions ? [...actions] : []

    function render() {
        container.innerHTML = `
            <div class="actions-header">
                <span class="actions-label">${label}:</span>
                <button type="button" class="btn-secondary btn-small add-action-btn">Add Action</button>
            </div>
            <div class="actions-items"></div>
        `

        const itemsDiv = container.querySelector('.actions-items')
        const addBtn = container.querySelector('.add-action-btn')

        actionsData.forEach((action, idx) => {
            const wrapper = document.createElement('div')
            wrapper.className = 'action-item-wrapper'

            const removeBtn = document.createElement('button')
            removeBtn.type = 'button'
            removeBtn.className = 'btn-icon btn-remove-action'
            removeBtn.textContent = '\u00d7'
            removeBtn.title = 'Remove action'
            removeBtn.setAttribute('aria-label', 'Remove this action')
            removeBtn.onclick = () => {
                // H3: Undo toast for action removal
                const removedAction = actionsData.splice(idx, 1)[0]
                const removedIdx = idx
                render()
                onUpdate([...actionsData])

                showUndoToast('Action removed', () => {
                    actionsData.splice(removedIdx, 0, removedAction)
                    render()
                    onUpdate([...actionsData])
                })
            }

            const actionBuilder = createActionBuilder(action, (updated) => {
                actionsData[idx] = updated
                onUpdate([...actionsData])
            })

            wrapper.appendChild(removeBtn)
            wrapper.appendChild(actionBuilder)
            itemsDiv.appendChild(wrapper)
        })

        if (actionsData.length === 0) {
            const empty = document.createElement('p')
            empty.className = 'actions-empty'
            empty.textContent = 'No actions configured'
            itemsDiv.appendChild(empty)
        }

        addBtn.onclick = () => {
            actionsData.push({ _type: 'skip', skip_type: 'skip_video_transcode' })
            render()
            onUpdate([...actionsData])

            // H1: Focus management - focus the new action's type select
            const actionSelects = itemsDiv.querySelectorAll('.action-type-select')
            const lastSelect = actionSelects[actionSelects.length - 1]
            if (lastSelect) {
                lastSelect.focus()
            }
        }
    }

    render()
    return container
}

/**
 * Create a single rule builder component
 * @param {Object} rule - Rule data
 * @param {Function} onUpdate - Callback when rule changes
 * @param {Function} onRemove - Callback to remove the rule
 * @returns {HTMLElement} Rule builder container
 */
function createRuleBuilder(rule, onUpdate, onRemove) {
    const container = document.createElement('div')
    container.className = 'conditional-rule-builder'

    const ruleData = rule ? { ...rule } : {
        name: 'New Rule',
        when: { track_type: 'audio' },
        then: [],
        else: null
    }

    function render() {
        container.innerHTML = `
            <div class="rule-header">
                <input type="text" class="form-input rule-name-input" placeholder="Rule name" value="${escapeAttr(ruleData.name || '')}">
                <button type="button" class="btn-icon btn-remove-rule" title="Remove rule">\u00d7</button>
            </div>
            <div class="rule-condition">
                <h5 class="rule-section-title">When (Condition):</h5>
                <div class="condition-container"></div>
            </div>
            <div class="rule-actions">
                <div class="then-actions-container"></div>
                <div class="else-actions-container"></div>
            </div>
        `

        const nameInput = container.querySelector('.rule-name-input')
        const removeBtn = container.querySelector('.btn-remove-rule')
        const conditionContainer = container.querySelector('.condition-container')
        const thenContainer = container.querySelector('.then-actions-container')
        const elseContainer = container.querySelector('.else-actions-container')

        nameInput.addEventListener('input', () => {
            ruleData.name = nameInput.value
            onUpdate(buildRule())
        })

        removeBtn.onclick = onRemove

        // Condition builder
        const condBuilder = createConditionBuilder(ruleData.when, (updated) => {
            ruleData.when = updated
            onUpdate(buildRule())
        }, 0)
        conditionContainer.appendChild(condBuilder)

        // Then actions
        const thenList = createActionsList(ruleData.then || [], (updated) => {
            ruleData.then = updated
            onUpdate(buildRule())
        }, 'Then Actions')
        thenContainer.appendChild(thenList)

        // Else actions
        const elseList = createActionsList(ruleData.else || [], (updated) => {
            ruleData.else = updated.length > 0 ? updated : null
            onUpdate(buildRule())
        }, 'Else Actions (optional)')
        elseContainer.appendChild(elseList)
    }

    function buildRule() {
        return {
            name: ruleData.name || 'Unnamed Rule',
            when: ruleData.when || { track_type: 'audio' },
            then: ruleData.then || [],
            else: ruleData.else || null
        }
    }

    render()
    return container
}

/**
 * Initialize the conditional rules section
 * @param {Object} policyData - Current policy data
 * @param {Function} onUpdate - Callback when rules change
 * @returns {Object} Controller with methods to get/set state
 */
export function initConditionalSection(policyData, onUpdate) {
    const rulesListEl = document.getElementById('conditional-rules-list')
    const addRuleBtn = document.getElementById('add-conditional-rule-btn')

    if (!rulesListEl || !addRuleBtn) {
        console.warn('Conditional section elements not found')
        return null
    }

    // Insert match mode selector before the rules list
    let matchModeSelect = document.getElementById('rules-match-mode')
    if (!matchModeSelect) {
        const matchModeContainer = document.createElement('div')
        matchModeContainer.className = 'form-group mb-md'
        matchModeContainer.innerHTML = `
            <label class="form-label" for="rules-match-mode">Match Mode:</label>
            <select id="rules-match-mode" class="form-select">
                <option value="first">First match wins (stop after first match)</option>
                <option value="all">All matches (execute every matching rule)</option>
            </select>
        `
        rulesListEl.parentNode.insertBefore(matchModeContainer, rulesListEl)
        matchModeSelect = document.getElementById('rules-match-mode')
    }

    // Internal state - V13 rules is {match, items}, extract items array
    let matchMode = 'first'
    let rules = []
    if (policyData.rules) {
        if (policyData.rules.items && Array.isArray(policyData.rules.items)) {
            matchMode = policyData.rules.match || 'first'
            rules = [...policyData.rules.items]
        } else if (Array.isArray(policyData.rules)) {
            // Fallback for legacy flat array format
            rules = [...policyData.rules]
        }
    }

    // Sync match mode select with state
    matchModeSelect.value = matchMode
    matchModeSelect.addEventListener('change', () => {
        matchMode = matchModeSelect.value
        notifyUpdate()
    })

    function notifyUpdate() {
        onUpdate(rules.length > 0 ? { match: matchMode, items: [...rules] } : null)
    }

    function renderRules() {
        rulesListEl.innerHTML = ''

        if (rules.length === 0) {
            const empty = document.createElement('p')
            empty.className = 'accordion-list-empty'
            empty.textContent = 'No conditional rules configured.'
            rulesListEl.appendChild(empty)
            return
        }

        rules.forEach((rule, idx) => {
            const ruleBuilder = createRuleBuilder(
                rule,
                (updated) => {
                    rules[idx] = updated
                    notifyUpdate()
                },
                () => {
                    // H3: Undo toast for rule removal
                    const removedRule = rules.splice(idx, 1)[0]
                    const removedIdx = idx
                    renderRules()
                    notifyUpdate()

                    showUndoToast('Rule removed', () => {
                        rules.splice(removedIdx, 0, removedRule)
                        renderRules()
                        notifyUpdate()
                    })
                }
            )
            rulesListEl.appendChild(ruleBuilder)
        })
    }

    // Add rule button handler
    addRuleBtn.onclick = () => {
        rules.push({
            name: `Rule ${rules.length + 1}`,
            when: { track_type: 'audio' },
            then: [],
            else: null
        })
        renderRules()
        notifyUpdate()

        // H1: Focus management - focus the newly added rule's name input
        const inputs = rulesListEl.querySelectorAll('.rule-name-input')
        const lastInput = inputs[inputs.length - 1]
        if (lastInput) {
            lastInput.focus()
            lastInput.select()
        }
    }

    // Initial render
    renderRules()

    // Return controller
    return {
        /**
         * Get current conditional rules configuration
         * @returns {Object|null} Rules config {match, items} or null if empty
         */
        getConfig() {
            return rules.length > 0 ? { match: matchMode, items: [...rules] } : null
        },

        /**
         * Set conditional rules configuration
         * @param {Object|null} config - Rules config {match, items} or null
         */
        setConfig(config) {
            if (config && config.items && Array.isArray(config.items)) {
                matchMode = config.match || 'first'
                rules = [...config.items]
            } else if (Array.isArray(config)) {
                rules = [...config]
            } else {
                rules = []
            }
            matchModeSelect.value = matchMode
            renderRules()
        },

        /**
         * Get/set the match mode
         * @returns {string} Current match mode ('first' or 'all')
         */
        getMatchMode() {
            return matchMode
        },

        setMatchMode(mode) {
            matchMode = mode
            matchModeSelect.value = matchMode
            notifyUpdate()
        },

        /**
         * Refresh the UI with current policy data
         * @param {Object} policyData - Policy data
         */
        refresh(policyData) {
            if (policyData.rules && policyData.rules.items && Array.isArray(policyData.rules.items)) {
                matchMode = policyData.rules.match || 'first'
                rules = [...policyData.rules.items]
            } else if (Array.isArray(policyData.rules)) {
                rules = [...policyData.rules]
            } else {
                rules = []
            }
            matchModeSelect.value = matchMode
            renderRules()
        }
    }
}

// Export condition builder for reuse by other sections (e.g., synthesis create_if)
export { createConditionBuilder }
