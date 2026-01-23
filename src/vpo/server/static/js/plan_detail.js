/**
 * Plan Detail JavaScript
 *
 * Handles approve/reject actions on the plan detail page.
 */

(function () {
    'use strict'

    // DOM elements
    const approveBtn = document.getElementById('btn-approve')
    const rejectBtn = document.getElementById('btn-reject')
    const toastEl = document.getElementById('plan-toast')

    // Track in-flight requests
    let pendingAction = false

    // Toast timer
    let toastTimer = null

    /**
     * Hide the toast notification.
     */
    function hideToast() {
        if (typeof window.ToastManager !== 'undefined') {
            window.ToastManager.hideToast(toastEl)
            return
        }

        if (!toastEl) return
        toastEl.style.display = 'none'
        if (toastTimer) {
            clearTimeout(toastTimer)
            toastTimer = null
        }
    }

    /**
     * Show toast notification with optional action buttons.
     * @param {string|HTMLElement|DocumentFragment} message - Message to display
     * @param {string} type - Toast type (success, error)
     * @param {Object} options - Optional configuration
     * @param {Array} options.actions - Array of {label, href?, onClick?} action buttons
     * @param {number} options.duration - Auto-dismiss duration in ms (0 for no auto-dismiss)
     */
    function showToast(message, type, options) {
        if (typeof window.ToastManager !== 'undefined') {
            window.ToastManager.showToast(toastEl, message, type, options)
            return
        }

        // Fallback implementation
        if (!toastEl) return

        if (toastTimer) {
            clearTimeout(toastTimer)
        }

        toastEl.innerHTML = ''
        toastEl.className = 'plans-toast plans-toast--' + type

        const messageSpan = document.createElement('span')
        messageSpan.className = 'toast-message'

        if (typeof message === 'string') {
            messageSpan.textContent = message
        } else if (message instanceof DocumentFragment || message instanceof HTMLElement) {
            messageSpan.appendChild(message)
        }

        toastEl.appendChild(messageSpan)

        // Add action buttons if provided
        options = options || {}
        if (options.actions && options.actions.length > 0) {
            const actionsDiv = document.createElement('div')
            actionsDiv.className = 'toast-actions'

            options.actions.forEach(function (action) {
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
                        hideToast()
                    })
                    actionsDiv.appendChild(btn)
                }
            })

            toastEl.appendChild(actionsDiv)
        }

        const closeBtn = document.createElement('button')
        closeBtn.type = 'button'
        closeBtn.className = 'toast-close'
        closeBtn.setAttribute('aria-label', 'Dismiss notification')
        closeBtn.innerHTML = '&times;'
        closeBtn.addEventListener('click', hideToast)
        toastEl.appendChild(closeBtn)

        toastEl.style.display = 'flex'

        // Auto-dismiss unless duration is 0
        const duration = options.duration !== undefined ? options.duration : 0
        if (duration > 0) {
            toastTimer = setTimeout(hideToast, duration)
        }
    }

    /**
     * Set loading state on a button.
     * @param {HTMLElement} btn - Button element
     * @param {boolean} loading - Whether to show loading state
     */
    function setButtonLoading(btn, loading) {
        if (!btn) return

        if (loading) {
            btn.disabled = true
            btn.classList.add('is-loading')
            btn.setAttribute('aria-busy', 'true')
        } else {
            btn.disabled = false
            btn.classList.remove('is-loading')
            btn.setAttribute('aria-busy', 'false')
        }
    }

    /**
     * Navigate to plans list.
     */
    function navigateToPlans() {
        window.location.href = '/plans'
    }

    /**
     * Handle approve action.
     */
    async function handleApprove() {
        if (pendingAction) return

        const planId = approveBtn.getAttribute('data-plan-id')
        if (!planId) return

        // Show confirmation modal
        if (typeof window.ConfirmationModal === 'undefined') {
            console.error('[PlanDetail] ConfirmationModal not loaded')
            showToast('Unable to show confirmation dialog. Please refresh the page.', 'error')
            return
        }

        const confirmed = await window.ConfirmationModal.show(
            'This will queue a job to apply the planned changes to the file. Continue?',
            {
                title: 'Approve Plan',
                confirmText: 'Approve and Queue',
                cancelText: 'Cancel'
            }
        )
        if (!confirmed) return

        pendingAction = true
        setButtonLoading(approveBtn, true)
        if (rejectBtn) rejectBtn.disabled = true

        try {
            const response = await fetch('/api/plans/' + planId + '/approve', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': window.CSRF_TOKEN
                }
            })

            const data = await response.json()

            if (data.success) {
                // Build action buttons for the toast
                const actions = []

                if (data.job_url) {
                    actions.push({
                        label: 'View Job',
                        href: data.job_url
                    })
                }

                actions.push({
                    label: 'Continue',
                    onClick: navigateToPlans
                })

                showToast('Plan approved successfully', 'success', {
                    actions: actions,
                    duration: 0  // Don't auto-dismiss - let user choose
                })
            } else {
                showToast(data.error || 'Failed to approve plan', 'error')
                setButtonLoading(approveBtn, false)
                if (rejectBtn) rejectBtn.disabled = false
            }
        } catch (error) {
            console.error('Error approving plan:', error)
            showToast('Failed to approve plan', 'error')
            setButtonLoading(approveBtn, false)
            if (rejectBtn) rejectBtn.disabled = false
        } finally {
            pendingAction = false
        }
    }

    /**
     * Handle reject action.
     */
    async function handleReject() {
        if (pendingAction) return

        const planId = rejectBtn.getAttribute('data-plan-id')
        if (!planId) return

        // Show confirmation modal
        if (typeof window.ConfirmationModal === 'undefined') {
            console.error('[PlanDetail] ConfirmationModal not loaded')
            showToast('Unable to show confirmation dialog. Please refresh the page.', 'error')
            return
        }

        const confirmed = await window.ConfirmationModal.show(
            'Are you sure you want to reject this plan? This cannot be undone.',
            {
                title: 'Reject Plan',
                confirmText: 'Reject',
                cancelText: 'Cancel',
                focusCancel: true
            }
        )
        if (!confirmed) return

        pendingAction = true
        setButtonLoading(rejectBtn, true)
        if (approveBtn) approveBtn.disabled = true

        try {
            const response = await fetch('/api/plans/' + planId + '/reject', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': window.CSRF_TOKEN
                }
            })

            const data = await response.json()

            if (data.success) {
                showToast('Plan rejected', 'success', {
                    actions: [{
                        label: 'Continue',
                        onClick: navigateToPlans
                    }],
                    duration: 0  // Don't auto-dismiss - let user choose
                })
            } else {
                showToast(data.error || 'Failed to reject plan', 'error')
                setButtonLoading(rejectBtn, false)
                if (approveBtn) approveBtn.disabled = false
            }
        } catch (error) {
            console.error('Error rejecting plan:', error)
            showToast('Failed to reject plan', 'error')
            setButtonLoading(rejectBtn, false)
            if (approveBtn) approveBtn.disabled = false
        } finally {
            pendingAction = false
        }
    }

    // Event listeners
    if (approveBtn) {
        approveBtn.addEventListener('click', handleApprove)
    }
    if (rejectBtn) {
        rejectBtn.addEventListener('click', handleReject)
    }

    // Format timestamps on page load
    document.querySelectorAll('time[data-timestamp]').forEach(function (el) {
        const timestamp = el.getAttribute('data-timestamp')
        if (timestamp) {
            try {
                const date = new Date(timestamp)
                el.textContent = date.toLocaleString()
            } catch {
                // Keep original text
            }
        }
    })
})()
