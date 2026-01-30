/**
 * Reusable Confirmation Modal Component
 *
 * Accessible modal dialog using native <dialog> element.
 * Focus trapping and scroll lock are handled natively by the browser.
 */

class ConfirmationModal {
    constructor() {
        this._dialog = null
        this._resolve = null
        this._focusedElementBeforeModal = null
    }

    /**
     * Show confirmation modal with a message
     * @param {string} message - The confirmation message to display
     * @param {Object} options - Optional configuration
     * @param {string} options.confirmText - Text for confirm button (default: "OK")
     * @param {string} options.cancelText - Text for cancel button (default: "Cancel")
     * @param {string} options.title - Modal title (default: "Confirm")
     * @param {boolean} options.focusCancel - Focus cancel button instead of confirm (default: false)
     *                                        Recommended for destructive/irreversible actions
     * @returns {Promise<boolean>} - Resolves to true if confirmed, false if cancelled
     */
    show(message, options = {}) {
        const {
            confirmText = 'OK',
            cancelText = 'Cancel',
            title = 'Confirm',
            focusCancel = false
        } = options

        return new Promise((resolve) => {
            this._resolve = resolve
            this._focusedElementBeforeModal = document.activeElement

            // Create native dialog element
            this._dialog = document.createElement('dialog')
            this._dialog.className = 'modal-dialog'
            this._dialog.setAttribute('aria-labelledby', 'modal-title')
            this._dialog.setAttribute('aria-describedby', 'modal-message')

            // Modal content
            this._dialog.innerHTML = `
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

            // Append to body and show as modal
            document.body.appendChild(this._dialog)

            // Set up event listeners
            const confirmBtn = this._dialog.querySelector('.modal-btn-confirm')
            const cancelBtn = this._dialog.querySelector('.modal-btn-cancel')

            confirmBtn.addEventListener('click', () => this._close(true))
            cancelBtn.addEventListener('click', () => this._close(false))

            // Backdrop click closes modal (cancel)
            this._dialog.addEventListener('click', (e) => {
                if (e.target === this._dialog) {
                    this._close(false)
                }
            })

            // Native dialog handles Escape key; listen for close event
            this._dialog.addEventListener('close', () => {
                // If close fired without _close() being called, treat as cancel
                if (this._resolve) {
                    this._cleanup()
                    resolve(false)
                }
            })

            // Show as modal (provides focus trapping and scroll lock natively)
            this._dialog.showModal()

            // Focus the appropriate button
            if (focusCancel) {
                cancelBtn.focus()
            } else {
                confirmBtn.focus()
            }
        })
    }

    /**
     * Close modal and resolve promise
     * @private
     */
    _close(result) {
        const resolve = this._resolve
        this._resolve = null

        this._dialog.close()
        this._cleanup()

        // Restore focus
        if (this._focusedElementBeforeModal) {
            this._focusedElementBeforeModal.focus()
            this._focusedElementBeforeModal = null
        }

        // Resolve promise
        if (resolve) {
            resolve(result)
        }
    }

    /**
     * Remove dialog element from DOM
     * @private
     */
    _cleanup() {
        if (this._dialog) {
            this._dialog.remove()
            this._dialog = null
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
