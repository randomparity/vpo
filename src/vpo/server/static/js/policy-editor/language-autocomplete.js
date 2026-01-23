/**
 * Accessible Language Autocomplete Component (256-policy-editor-enhancements T023)
 *
 * Implements WAI-ARIA 1.2 combobox pattern for language selection.
 * Features:
 * - Keyboard navigation (Arrow keys, Enter, Escape)
 * - Screen reader announcements via aria-live
 * - Focus management
 * - Filter-as-you-type suggestions
 */

import { searchLanguages } from './language-data.js'

/**
 * Create an accessible language autocomplete component
 * @param {HTMLElement} container - Container element for the autocomplete
 * @param {object} options - Configuration options
 * @param {string} options.inputId - ID for the input element
 * @param {string} options.listboxId - ID for the listbox element
 * @param {string} options.label - Label for the input (aria-label)
 * @param {string} options.placeholder - Placeholder text
 * @param {function} options.onSelect - Callback when language is selected
 * @returns {object} Controller object with methods
 */
export function createLanguageAutocomplete(container, options) {
    const {
        inputId,
        listboxId,
        label,
        placeholder = 'e.g., eng, jpn, fra',
        onSelect,
    } = options

    // Track state
    let isOpen = false
    let activeIndex = -1
    let suggestions = []
    let debounceTimer = null

    // Create DOM structure
    const wrapper = document.createElement('div')
    wrapper.className = 'language-autocomplete'

    const input = document.createElement('input')
    input.type = 'text'
    input.id = inputId
    input.className = 'language-autocomplete-input'
    input.placeholder = placeholder
    input.setAttribute('role', 'combobox')
    input.setAttribute('aria-autocomplete', 'list')
    input.setAttribute('aria-expanded', 'false')
    input.setAttribute('aria-controls', listboxId)
    input.setAttribute('aria-label', label)
    input.setAttribute('aria-describedby', `${inputId}-hint`)
    input.setAttribute('autocomplete', 'off')
    input.maxLength = 3

    const listbox = document.createElement('ul')
    listbox.id = listboxId
    listbox.className = 'language-autocomplete-listbox'
    listbox.setAttribute('role', 'listbox')
    listbox.setAttribute('aria-label', `${label} suggestions`)
    listbox.hidden = true

    const hint = document.createElement('span')
    hint.id = `${inputId}-hint`
    hint.className = 'language-autocomplete-hint'
    hint.textContent = ''

    // Screen reader announcements
    const liveRegion = document.createElement('span')
    liveRegion.className = 'sr-only'
    liveRegion.setAttribute('aria-live', 'polite')
    liveRegion.setAttribute('aria-atomic', 'true')

    wrapper.appendChild(input)
    wrapper.appendChild(listbox)
    wrapper.appendChild(hint)
    wrapper.appendChild(liveRegion)
    container.appendChild(wrapper)

    /**
     * Update suggestions based on input value
     */
    async function updateSuggestions() {
        const query = input.value.trim()
        suggestions = await searchLanguages(query, 8)

        // Clear existing options
        listbox.innerHTML = ''

        if (suggestions.length === 0) {
            closeListbox()
            hint.textContent = query.length > 0 ? 'No matches. Press Enter to add custom code.' : ''
            return
        }

        // Create option elements
        suggestions.forEach((lang, index) => {
            const option = document.createElement('li')
            option.id = `${listboxId}-option-${index}`
            option.className = 'language-autocomplete-option'
            option.setAttribute('role', 'option')
            option.setAttribute('aria-selected', 'false')
            option.dataset.code = lang.code

            const code = document.createElement('span')
            code.className = 'option-code'
            code.textContent = lang.code

            const name = document.createElement('span')
            name.className = 'option-name'
            name.textContent = lang.name

            option.appendChild(code)
            option.appendChild(name)

            option.addEventListener('click', () => selectOption(index))
            option.addEventListener('mouseenter', () => setActiveOption(index))

            listbox.appendChild(option)
        })

        openListbox()
        announce(`${suggestions.length} language${suggestions.length === 1 ? '' : 's'} available`)
    }

    /**
     * Open the listbox
     */
    function openListbox() {
        if (suggestions.length === 0) return
        isOpen = true
        listbox.hidden = false
        input.setAttribute('aria-expanded', 'true')
    }

    /**
     * Close the listbox
     */
    function closeListbox() {
        isOpen = false
        listbox.hidden = true
        input.setAttribute('aria-expanded', 'false')
        input.removeAttribute('aria-activedescendant')
        activeIndex = -1

        // Clear visual active state
        const options = listbox.querySelectorAll('[role="option"]')
        options.forEach(opt => {
            opt.classList.remove('active')
            opt.setAttribute('aria-selected', 'false')
        })
    }

    /**
     * Set the active (highlighted) option
     * @param {number} index - Index of option to activate
     */
    function setActiveOption(index) {
        const options = listbox.querySelectorAll('[role="option"]')

        // Clear previous active
        options.forEach(opt => {
            opt.classList.remove('active')
            opt.setAttribute('aria-selected', 'false')
        })

        // Set new active
        if (index >= 0 && index < options.length) {
            activeIndex = index
            const option = options[index]
            option.classList.add('active')
            option.setAttribute('aria-selected', 'true')
            input.setAttribute('aria-activedescendant', option.id)

            // Scroll option into view
            option.scrollIntoView({ block: 'nearest' })

            // Announce for screen readers
            const lang = suggestions[index]
            announce(`${lang.code} - ${lang.name}`)
        } else {
            activeIndex = -1
            input.removeAttribute('aria-activedescendant')
        }
    }

    /**
     * Select an option
     * @param {number} index - Index of option to select
     */
    function selectOption(index) {
        if (index >= 0 && index < suggestions.length) {
            const lang = suggestions[index]

            // Call onSelect first - only clear if it succeeds
            let success = true
            if (onSelect) {
                success = onSelect(lang.code, lang.name) !== false
            }

            if (success) {
                input.value = ''
                closeListbox()
                hint.textContent = ''
                clearError()
                announce(`${lang.code} selected`)
            }
            input.focus()
        }
    }

    /**
     * Announce message to screen readers
     * @param {string} message - Message to announce
     */
    function announce(message) {
        liveRegion.textContent = ''
        // Small delay to ensure announcement
        setTimeout(() => {
            liveRegion.textContent = message
        }, 50)
    }

    /**
     * Show error state on input
     * @param {string} message - Error message for hint
     */
    function showError(message) {
        input.classList.add('input-error')
        hint.textContent = message
        hint.classList.add('error')
        announce(message)

        // Clear error state after 2 seconds
        setTimeout(() => {
            input.classList.remove('input-error')
            hint.classList.remove('error')
            if (hint.textContent === message) {
                hint.textContent = ''
            }
        }, 2000)
    }

    /**
     * Clear any error state on input
     */
    function clearError() {
        input.classList.remove('input-error')
        hint.classList.remove('error')
    }

    /**
     * Handle keyboard navigation
     */
    function handleKeydown(e) {
        switch (e.key) {
        case 'ArrowDown':
            e.preventDefault()
            if (!isOpen) {
                updateSuggestions()
            } else {
                const nextIndex = activeIndex < suggestions.length - 1 ? activeIndex + 1 : 0
                setActiveOption(nextIndex)
            }
            break

        case 'ArrowUp':
            e.preventDefault()
            if (isOpen) {
                const prevIndex = activeIndex > 0 ? activeIndex - 1 : suggestions.length - 1
                setActiveOption(prevIndex)
            }
            break

        case 'Enter':
            e.preventDefault()
            if (isOpen && activeIndex >= 0) {
                selectOption(activeIndex)
            } else if (input.value.trim()) {
                // Allow direct entry if no suggestion selected
                const code = input.value.trim().toLowerCase()
                if (/^[a-z]{2,3}$/.test(code)) {
                    // Call onSelect first - only clear if it succeeds
                    let success = true
                    if (onSelect) {
                        success = onSelect(code, null) !== false
                    }
                    if (success) {
                        input.value = ''
                        closeListbox()
                        hint.textContent = ''
                        clearError()
                    }
                } else {
                    // Show error for invalid format
                    showError('Enter 2 or 3 letter code')
                }
            }
            break

        case 'Escape':
            if (isOpen) {
                e.preventDefault()
                closeListbox()
            }
            break

        case 'Tab':
            closeListbox()
            break
        }
    }

    // Event listeners
    input.addEventListener('input', () => {
        // Debounce input to avoid excessive filtering on every keystroke
        clearTimeout(debounceTimer)
        debounceTimer = setTimeout(() => {
            updateSuggestions()
        }, 150)
    })

    input.addEventListener('keydown', handleKeydown)

    input.addEventListener('focus', () => {
        if (input.value.trim() || suggestions.length > 0) {
            updateSuggestions()
        }
    })

    input.addEventListener('blur', () => {
        // Delay close to allow click on option (200ms for touch device support)
        setTimeout(() => {
            if (!wrapper.contains(document.activeElement)) {
                closeListbox()
            }
        }, 200)
    })

    // Close on outside click (named function for cleanup)
    function handleDocumentClick(e) {
        if (!wrapper.contains(e.target)) {
            closeListbox()
        }
    }
    document.addEventListener('click', handleDocumentClick)

    // Return controller
    return {
        input,
        listbox,
        getValue: () => input.value,
        setValue: (value) => {
            input.value = value
        },
        focus: () => input.focus(),
        clear: () => {
            input.value = ''
            closeListbox()
            hint.textContent = ''
        },
        destroy: () => {
            clearTimeout(debounceTimer)
            document.removeEventListener('click', handleDocumentClick)
            wrapper.remove()
        },
    }
}
