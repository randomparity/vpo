/**
 * Shared Toast Manager
 *
 * Provides consistent toast notifications across the application.
 * Usage:
 *   import { showToast, hideToast } from '/static/js/components/toast-manager.js'
 *   showToast(toastEl, 'Message', 'success')
 *   showToast(toastEl, 'Message', 'success', { duration: 5000, actions: [...] })
 */

const ToastManager = (function () {
    'use strict'

    // Active toast timers by element ID
    const timers = new Map()

    /**
     * Hide a toast notification.
     * @param {HTMLElement} toastEl - Toast container element
     */
    function hideToast(toastEl) {
        if (!toastEl) return

        toastEl.style.display = 'none'
        toastEl.innerHTML = ''

        const timerId = timers.get(toastEl.id)
        if (timerId) {
            clearTimeout(timerId)
            timers.delete(toastEl.id)
        }
    }

    /**
     * Show a toast notification.
     * @param {HTMLElement} toastEl - Toast container element
     * @param {string|HTMLElement|DocumentFragment} message - Message to display
     * @param {string} type - Toast type: 'success', 'error', 'info', 'warning'
     * @param {Object} options - Optional configuration
     * @param {number} options.duration - Auto-dismiss time in ms (default 5000, 0 for no auto-dismiss)
     * @param {boolean} options.dismissible - Show close button (default true)
     * @param {Array} options.actions - Array of {label, href?, onClick?} action buttons
     */
    function showToast(toastEl, message, type, options) {
        if (!toastEl) return

        options = options || {}
        const duration = options.duration !== undefined ? options.duration : 5000
        const dismissible = options.dismissible !== undefined ? options.dismissible : true
        const actions = options.actions || []

        // Clear any existing timer
        const existingTimer = timers.get(toastEl.id)
        if (existingTimer) {
            clearTimeout(existingTimer)
            timers.delete(toastEl.id)
        }

        // Reset toast
        toastEl.innerHTML = ''
        toastEl.className = 'plans-toast plans-toast--' + type

        // Create message element
        const messageSpan = document.createElement('span')
        messageSpan.className = 'toast-message'

        if (typeof message === 'string') {
            messageSpan.textContent = message
        } else if (message instanceof DocumentFragment || message instanceof HTMLElement) {
            messageSpan.appendChild(message)
        }
        toastEl.appendChild(messageSpan)

        // Add action buttons if provided
        if (actions.length > 0) {
            const actionsDiv = document.createElement('div')
            actionsDiv.className = 'toast-actions'

            actions.forEach(function (action) {
                if (action.href) {
                    const link = document.createElement('a')
                    link.href = action.href
                    link.className = 'toast-action-btn'
                    link.textContent = action.label
                    actionsDiv.appendChild(link)
                } else if (action.onClick) {
                    const btn = document.createElement('button')
                    btn.type = 'button'
                    btn.className = 'toast-action-btn'
                    btn.textContent = action.label
                    btn.addEventListener('click', function () {
                        action.onClick()
                        hideToast(toastEl)
                    })
                    actionsDiv.appendChild(btn)
                }
            })

            toastEl.appendChild(actionsDiv)
        }

        // Add close button if dismissible
        if (dismissible) {
            const closeBtn = document.createElement('button')
            closeBtn.type = 'button'
            closeBtn.className = 'toast-close'
            closeBtn.setAttribute('aria-label', 'Dismiss notification')
            closeBtn.innerHTML = '&times;'
            closeBtn.addEventListener('click', function () {
                hideToast(toastEl)
            })
            toastEl.appendChild(closeBtn)
        }

        // Show toast
        toastEl.style.display = 'flex'

        // Set auto-dismiss timer if duration > 0
        if (duration > 0) {
            const timerId = setTimeout(function () {
                hideToast(toastEl)
            }, duration)
            timers.set(toastEl.id, timerId)
        }
    }

    /**
     * Update toast message without resetting timer.
     * Useful for progress updates during bulk operations.
     * @param {HTMLElement} toastEl - Toast container element
     * @param {string} message - New message text
     */
    function updateToastMessage(toastEl, message) {
        if (!toastEl) return

        const messageSpan = toastEl.querySelector('.toast-message')
        if (messageSpan) {
            messageSpan.textContent = message
        }
    }

    // Export public API
    return {
        showToast: showToast,
        hideToast: hideToast,
        updateToastMessage: updateToastMessage
    }
})()

// Make available globally for non-module scripts
if (typeof window !== 'undefined') {
    window.ToastManager = ToastManager
}
