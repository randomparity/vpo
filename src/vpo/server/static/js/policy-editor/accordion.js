/**
 * Accordion Component for Policy Editor (036-v9-policy-editor)
 *
 * Provides collapsible accordion sections using HTML5 <details> elements.
 * Features:
 * - Keyboard navigation (Enter/Space to toggle, Tab to navigate)
 * - ARIA attributes for accessibility
 * - CSS transitions for smooth animation
 * - Event callbacks for section state changes
 */

/**
 * Initialize accordion functionality for a container
 * @param {string|HTMLElement} container - Container selector or element
 * @param {Object} options - Configuration options
 * @param {function} options.onToggle - Callback when section is toggled
 * @param {boolean} options.allowMultiple - Allow multiple sections open (default: true)
 * @returns {Object} Accordion controller with methods to manipulate sections
 */
export function initAccordion(container, options = {}) {
    const containerEl = typeof container === 'string'
        ? document.querySelector(container)
        : container

    if (!containerEl) {
        console.warn('Accordion container not found')
        return null
    }

    const {
        onToggle = null,
        allowMultiple = true
    } = options

    // Find all accordion sections
    const sections = containerEl.querySelectorAll('details.accordion-section')

    if (sections.length === 0) {
        console.warn('No accordion sections found')
        return null
    }

    /**
     * Handle toggle event on a section
     * @param {HTMLDetailsElement} section - The section being toggled
     * @param {Event} event - Toggle event
     */
    function handleToggle(section, event) {
        const isOpen = section.open
        const sectionId = section.id || section.querySelector('summary')?.textContent?.trim()

        // Update ARIA attribute
        const summary = section.querySelector('summary')
        if (summary) {
            summary.setAttribute('aria-expanded', isOpen ? 'true' : 'false')
        }

        // If allowMultiple is false, close other sections when one opens
        if (!allowMultiple && isOpen) {
            sections.forEach(s => {
                if (s !== section && s.open) {
                    s.open = false
                    const sum = s.querySelector('summary')
                    if (sum) {
                        sum.setAttribute('aria-expanded', 'false')
                    }
                }
            })
        }

        // Call toggle callback if provided
        if (onToggle) {
            onToggle({
                section,
                sectionId,
                isOpen,
                event
            })
        }
    }

    /**
     * Handle keyboard navigation on summary
     * @param {HTMLElement} summary - Summary element
     * @param {KeyboardEvent} event - Keyboard event
     */
    function handleKeyboard(summary, event) {
        // Enter and Space are handled natively by <summary>
        // Add support for arrow keys to navigate between sections
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault()

            const summaries = Array.from(containerEl.querySelectorAll('details.accordion-section > summary'))
            const currentIndex = summaries.indexOf(summary)

            let targetIndex
            if (event.key === 'ArrowDown') {
                targetIndex = (currentIndex + 1) % summaries.length
            } else {
                targetIndex = (currentIndex - 1 + summaries.length) % summaries.length
            }

            summaries[targetIndex]?.focus()
        }

        // Home and End to go to first/last section
        if (event.key === 'Home') {
            event.preventDefault()
            const summaries = containerEl.querySelectorAll('details.accordion-section > summary')
            summaries[0]?.focus()
        }

        if (event.key === 'End') {
            event.preventDefault()
            const summaries = containerEl.querySelectorAll('details.accordion-section > summary')
            summaries[summaries.length - 1]?.focus()
        }
    }

    // Initialize each section
    sections.forEach(section => {
        const summary = section.querySelector('summary')

        if (summary) {
            // Set initial ARIA attributes
            // Note: role="button" is implicit for <summary> elements, so we don't set it
            summary.setAttribute('aria-expanded', section.open ? 'true' : 'false')

            // Add keyboard handler
            summary.addEventListener('keydown', (e) => handleKeyboard(summary, e))
        }

        // Add toggle handler
        section.addEventListener('toggle', (e) => handleToggle(section, e))
    })

    // Return controller object
    return {
        /**
         * Open a section by ID or index
         * @param {string|number} sectionIdentifier - Section ID or index
         */
        open(sectionIdentifier) {
            const section = typeof sectionIdentifier === 'number'
                ? sections[sectionIdentifier]
                : containerEl.querySelector(`#${sectionIdentifier}`)

            if (section) {
                section.open = true
            }
        },

        /**
         * Close a section by ID or index
         * @param {string|number} sectionIdentifier - Section ID or index
         */
        close(sectionIdentifier) {
            const section = typeof sectionIdentifier === 'number'
                ? sections[sectionIdentifier]
                : containerEl.querySelector(`#${sectionIdentifier}`)

            if (section) {
                section.open = false
            }
        },

        /**
         * Toggle a section by ID or index
         * @param {string|number} sectionIdentifier - Section ID or index
         */
        toggle(sectionIdentifier) {
            const section = typeof sectionIdentifier === 'number'
                ? sections[sectionIdentifier]
                : containerEl.querySelector(`#${sectionIdentifier}`)

            if (section) {
                section.open = !section.open
            }
        },

        /**
         * Open all sections
         */
        openAll() {
            sections.forEach(s => { s.open = true })
        },

        /**
         * Close all sections
         */
        closeAll() {
            sections.forEach(s => { s.open = false })
        },

        /**
         * Get currently open section IDs
         * @returns {string[]} Array of open section IDs
         */
        getOpenSections() {
            return Array.from(sections)
                .filter(s => s.open)
                .map(s => s.id)
        },

        /**
         * Get section count
         * @returns {number} Number of sections
         */
        getSectionCount() {
            return sections.length
        },

        /**
         * Check if a section is open
         * @param {string|number} sectionIdentifier - Section ID or index
         * @returns {boolean} True if section is open
         */
        isOpen(sectionIdentifier) {
            const section = typeof sectionIdentifier === 'number'
                ? sections[sectionIdentifier]
                : containerEl.querySelector(`#${sectionIdentifier}`)

            return section?.open ?? false
        }
    }
}

export default { initAccordion }
