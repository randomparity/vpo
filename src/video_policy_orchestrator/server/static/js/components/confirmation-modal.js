/**
 * Reusable Confirmation Modal Component
 *
 * Accessible modal dialog for confirmations with focus trapping and keyboard support.
 */

class ConfirmationModal {
    constructor() {
        this.modal = null
        this.overlay = null
        this.resolve = null
        this.focusedElementBeforeModal = null
        this._handleKeyDown = this._handleKeyDown.bind(this)
    }

    /**
     * Show confirmation modal with a message
     * @param {string} message - The confirmation message to display
     * @param {Object} options - Optional configuration
     * @param {string} options.confirmText - Text for confirm button (default: "OK")
     * @param {string} options.cancelText - Text for cancel button (default: "Cancel")
     * @param {string} options.title - Modal title (default: "Confirm")
     * @returns {Promise<boolean>} - Resolves to true if confirmed, false if cancelled
     */
    show(message, options = {}) {
        const {
            confirmText = 'OK',
            cancelText = 'Cancel',
            title = 'Confirm'
        } = options

        return new Promise((resolve) => {
            this.resolve = resolve
            this.focusedElementBeforeModal = document.activeElement

            // Create overlay
            this.overlay = document.createElement('div')
            this.overlay.className = 'modal-overlay'
            this.overlay.setAttribute('role', 'presentation')

            // Create modal dialog
            this.modal = document.createElement('div')
            this.modal.className = 'modal-dialog'
            this.modal.setAttribute('role', 'alertdialog')
            this.modal.setAttribute('aria-modal', 'true')
            this.modal.setAttribute('aria-labelledby', 'modal-title')
            this.modal.setAttribute('aria-describedby', 'modal-message')

            // Modal content
            this.modal.innerHTML = `
                <div class="modal-header">
                    <h2 id="modal-title" class="modal-title">${this._escapeHtml(title)}</h2>
                </div>
                <div class="modal-body">
                    <p id="modal-message" class="modal-message">${this._escapeHtml(message)}</p>
                </div>
                <div class="modal-footer">
                    <button type="button" class="modal-btn modal-btn-cancel">${this._escapeHtml(cancelText)}</button>
                    <button type="button" class="modal-btn modal-btn-confirm">${this._escapeHtml(confirmText)}</button>
                </div>
            `

            // Append to body
            document.body.appendChild(this.overlay)
            document.body.appendChild(this.modal)

            // Set up event listeners
            const confirmBtn = this.modal.querySelector('.modal-btn-confirm')
            const cancelBtn = this.modal.querySelector('.modal-btn-cancel')

            confirmBtn.addEventListener('click', () => this._confirm(true))
            cancelBtn.addEventListener('click', () => this._confirm(false))
            this.overlay.addEventListener('click', () => this._confirm(false))

            // Keyboard support
            document.addEventListener('keydown', this._handleKeyDown)

            // Focus confirm button
            confirmBtn.focus()

            // Prevent body scroll
            document.body.style.overflow = 'hidden'
        })
    }

    /**
     * Handle keyboard events
     * @private
     */
    _handleKeyDown(e) {
        if (e.key === 'Escape') {
            e.preventDefault()
            this._confirm(false)
        } else if (e.key === 'Tab') {
            // Trap focus within modal
            this._trapFocus(e)
        }
    }

    /**
     * Trap focus within the modal
     * @private
     */
    _trapFocus(e) {
        const focusableElements = this.modal.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        )
        const firstElement = focusableElements[0]
        const lastElement = focusableElements[focusableElements.length - 1]

        if (e.shiftKey && document.activeElement === firstElement) {
            e.preventDefault()
            lastElement.focus()
        } else if (!e.shiftKey && document.activeElement === lastElement) {
            e.preventDefault()
            firstElement.focus()
        }
    }

    /**
     * Close modal and resolve promise
     * @private
     */
    _confirm(result) {
        // Remove event listeners
        document.removeEventListener('keydown', this._handleKeyDown)

        // Restore body scroll
        document.body.style.overflow = ''

        // Remove elements
        if (this.modal) {
            this.modal.remove()
            this.modal = null
        }
        if (this.overlay) {
            this.overlay.remove()
            this.overlay = null
        }

        // Restore focus
        if (this.focusedElementBeforeModal) {
            this.focusedElementBeforeModal.focus()
        }

        // Resolve promise
        if (this.resolve) {
            this.resolve(result)
            this.resolve = null
        }
    }

    /**
     * Escape HTML to prevent XSS
     * @private
     */
    _escapeHtml(text) {
        const div = document.createElement('div')
        div.textContent = text
        return div.innerHTML
    }
}

// Export singleton instance
window.ConfirmationModal = new ConfirmationModal()
