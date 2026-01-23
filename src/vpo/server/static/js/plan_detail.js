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
        if (!toastEl) return
        toastEl.style.display = 'none'
        if (toastTimer) {
            clearTimeout(toastTimer)
            toastTimer = null
        }
    }

    /**
     * Show toast notification.
     * @param {string|HTMLElement|DocumentFragment} message - Message to display
     * @param {string} type - Toast type (success, error)
     */
    function showToast(message, type) {
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

        const closeBtn = document.createElement('button')
        closeBtn.type = 'button'
        closeBtn.className = 'toast-close'
        closeBtn.setAttribute('aria-label', 'Dismiss notification')
        closeBtn.innerHTML = '&times;'
        closeBtn.addEventListener('click', hideToast)
        toastEl.appendChild(closeBtn)

        toastEl.style.display = 'flex'

        toastTimer = setTimeout(hideToast, 5000)
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
                const messageEl = document.createDocumentFragment()
                messageEl.appendChild(document.createTextNode('Plan approved successfully'))

                if (data.job_url) {
                    messageEl.appendChild(document.createTextNode('. '))
                    const link = document.createElement('a')
                    link.href = data.job_url
                    link.textContent = 'View job'
                    messageEl.appendChild(link)
                }

                showToast(messageEl, 'success')

                // Redirect to plans list after short delay
                setTimeout(function () {
                    window.location.href = '/plans'
                }, 1500)
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
                showToast('Plan rejected', 'success')

                // Redirect to plans list after short delay
                setTimeout(function () {
                    window.location.href = '/plans'
                }, 1500)
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
