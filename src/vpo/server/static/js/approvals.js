/**
 * Approvals Dashboard JavaScript
 *
 * Handles fetching pending plans, rendering the table,
 * individual and bulk approve/reject actions.
 */

(function () {
    'use strict'

    // Session storage key for selection persistence
    const SELECTION_STORAGE_KEY = 'vpo_selected_approvals'

    // State
    let currentOffset = 0
    const pageSize = 50
    let currentSince = ''
    let totalPlans = 0
    let pendingActions = {}
    let selectedPlans = new Set()
    let lastFocusedPlanId = null
    let currentFetchController = null
    let bulkOperationController = null

    // DOM elements
    const loadingEl = document.getElementById('approvals-loading')
    const contentEl = document.getElementById('approvals-content')
    const tableBodyEl = document.getElementById('approvals-table-body')
    const tableEl = document.getElementById('approvals-table')
    const emptyEl = document.getElementById('approvals-empty')
    const paginationEl = document.getElementById('approvals-pagination')
    const paginationInfoEl = document.getElementById('approvals-pagination-info')
    const prevBtnEl = document.getElementById('approvals-prev-btn')
    const nextBtnEl = document.getElementById('approvals-next-btn')
    const toastEl = document.getElementById('approvals-toast')
    const countTextEl = document.getElementById('approvals-count-text')
    const bulkActionsEl = document.getElementById('approvals-bulk-actions')
    const bulkApproveBtn = document.getElementById('bulk-approve-btn')
    const bulkRejectBtn = document.getElementById('bulk-reject-btn')
    const selectAllCheckbox = document.getElementById('select-all-approvals')

    /**
     * Format an ISO timestamp to a relative time string.
     */
    function formatRelativeTime(isoString) {
        if (!isoString) return '-'

        try {
            const date = new Date(isoString)
            const now = new Date()
            const diffMs = now - date
            const diffSec = Math.floor(diffMs / 1000)
            const diffMin = Math.floor(diffSec / 60)
            const diffHour = Math.floor(diffMin / 60)
            const diffDay = Math.floor(diffHour / 24)

            if (diffSec < 60) return 'just now'
            if (diffMin < 60) return diffMin === 1 ? '1 minute ago' : diffMin + ' minutes ago'
            if (diffHour < 24) return diffHour === 1 ? '1 hour ago' : diffHour + ' hours ago'
            if (diffDay < 7) return diffDay === 1 ? '1 day ago' : diffDay + ' days ago'

            return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
        } catch {
            return isoString
        }
    }

    /**
     * Escape HTML to prevent XSS.
     */
    function escapeHtml(str) {
        if (!str) return ''
        const div = document.createElement('div')
        div.textContent = str
        return div.innerHTML
    }

    /**
     * Format source file display.
     */
    function formatSourceDisplay(plan) {
        if (plan.file_deleted) {
            return '<span class="plan-file-deleted">[Deleted]</span> ' + escapeHtml(plan.filename)
        }
        return escapeHtml(plan.filename)
    }

    /**
     * Create action buttons for a plan row.
     */
    function createActionButtons(plan) {
        const shortId = plan.id_short || plan.id.substring(0, 8)

        return '<div class="plan-actions">' +
            '<button type="button" class="plan-action-btn plan-action-approve" ' +
                'data-plan-id="' + escapeHtml(plan.id) + '" ' +
                'data-action="approve" ' +
                'aria-label="Approve plan ' + escapeHtml(shortId) + '" ' +
                'title="Approve this plan">' +
                '<span class="btn-text">Approve</span>' +
                '<span class="btn-spinner" aria-hidden="true"></span>' +
            '</button>' +
            '<button type="button" class="plan-action-btn plan-action-reject" ' +
                'data-plan-id="' + escapeHtml(plan.id) + '" ' +
                'data-action="reject" ' +
                'aria-label="Reject plan ' + escapeHtml(shortId) + '" ' +
                'title="Reject this plan">' +
                '<span class="btn-text">Reject</span>' +
                '<span class="btn-spinner" aria-hidden="true"></span>' +
            '</button>' +
        '</div>'
    }

    /**
     * Render a single plan row.
     */
    function renderPlanRow(plan) {
        const shortId = plan.id_short || plan.id.substring(0, 8)
        const remuxIndicator = plan.requires_remux
            ? ' <span class="plan-remux-indicator" title="Requires container remux">*</span>'
            : ''
        const isChecked = selectedPlans.has(plan.id) ? 'checked' : ''

        return '<tr class="plan-row plan-row-clickable" ' +
            'data-plan-id="' + escapeHtml(plan.id) + '" ' +
            'tabindex="0" ' +
            'role="row" ' +
            'aria-label="Plan ' + escapeHtml(shortId) + ' for ' + escapeHtml(plan.filename) + '">' +
            '<td class="plan-select">' +
                '<input type="checkbox" class="plan-checkbox" ' +
                    'data-plan-id="' + escapeHtml(plan.id) + '" ' +
                    'aria-label="Select plan ' + escapeHtml(shortId) + '" ' + isChecked + '>' +
            '</td>' +
            '<td class="plan-id" title="' + escapeHtml(plan.id) + '">' + escapeHtml(shortId) + '</td>' +
            '<td class="plan-file">' + formatSourceDisplay(plan) + '</td>' +
            '<td class="plan-policy">' + escapeHtml(plan.policy_name) + '</td>' +
            '<td class="plan-action-count">' + plan.action_count + remuxIndicator + '</td>' +
            '<td class="plan-created">' + formatRelativeTime(plan.created_at) + '</td>' +
            '<td class="plan-actions-cell">' + createActionButtons(plan) + '</td>' +
            '</tr>'
    }

    /**
     * Render the plans table.
     */
    function renderPlansTable(plans) {
        if (plans.length === 0) {
            tableEl.style.display = 'none'
            emptyEl.style.display = 'block'
            bulkActionsEl.style.display = 'none'
            return
        }

        tableEl.style.display = 'table'
        emptyEl.style.display = 'none'
        bulkActionsEl.style.display = 'flex'

        const html = plans.map(renderPlanRow).join('')
        tableBodyEl.innerHTML = html

        updateSelectAllState()
        restoreFocusAfterRefresh()
    }

    /**
     * Restore focus to the next available row after an action.
     */
    function restoreFocusAfterRefresh() {
        if (!lastFocusedPlanId) return

        // Try to focus the same plan
        let row = tableBodyEl.querySelector('[data-plan-id="' + lastFocusedPlanId + '"]')

        // If not found, focus the first row
        if (!row) {
            row = tableBodyEl.querySelector('.plan-row-clickable')
        }

        if (row) {
            row.focus()
        }

        // Clear after restoration attempt
        lastFocusedPlanId = null
    }

    /**
     * Update the count text.
     */
    function updateCountText() {
        const text = totalPlans === 1
            ? '1 pending approval'
            : totalPlans + ' pending approvals'
        countTextEl.textContent = text
    }

    /**
     * Update pagination controls.
     */
    function updatePagination() {
        if (totalPlans <= pageSize) {
            paginationEl.style.display = 'none'
            return
        }

        paginationEl.style.display = 'flex'
        const start = currentOffset + 1
        const end = Math.min(currentOffset + pageSize, totalPlans)
        paginationInfoEl.textContent = 'Showing ' + start + '-' + end + ' of ' + totalPlans + ' pending'
        prevBtnEl.disabled = currentOffset === 0
        nextBtnEl.disabled = currentOffset + pageSize >= totalPlans

        // Add aria-current to indicate current page range
        const totalPages = Math.ceil(totalPlans / pageSize)
        const currentPage = Math.floor(currentOffset / pageSize) + 1
        paginationInfoEl.setAttribute('aria-label', 'Page ' + currentPage + ' of ' + totalPages)
    }

    /**
     * Build query string for pending plans.
     */
    function buildQueryString() {
        const params = new URLSearchParams()
        params.set('status', 'pending')
        if (currentSince) params.set('since', currentSince)
        params.set('limit', pageSize.toString())
        params.set('offset', currentOffset.toString())
        return '?' + params.toString()
    }

    // Toast management using shared component if available
    let toastTimer = null

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

    function showToast(message, type, options) {
        if (typeof window.ToastManager !== 'undefined') {
            window.ToastManager.showToast(toastEl, message, type, options)
            return
        }

        // Fallback implementation
        if (!toastEl) return
        if (toastTimer) clearTimeout(toastTimer)

        toastEl.innerHTML = ''
        toastEl.className = 'plans-toast plans-toast--' + type

        const messageSpan = document.createElement('span')
        messageSpan.className = 'toast-message'
        if (typeof message === 'string') {
            messageSpan.textContent = message
        } else {
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

    function updateToastMessage(message) {
        if (typeof window.ToastManager !== 'undefined') {
            window.ToastManager.updateToastMessage(toastEl, message)
            return
        }

        const messageSpan = toastEl ? toastEl.querySelector('.toast-message') : null
        if (messageSpan) {
            messageSpan.textContent = message
        }
    }

    // Selection persistence
    function saveSelectionToStorage() {
        try {
            const ids = Array.from(selectedPlans)
            sessionStorage.setItem(SELECTION_STORAGE_KEY, JSON.stringify(ids))
        } catch {
            // Storage may be unavailable
        }
    }

    function loadSelectionFromStorage() {
        try {
            const stored = sessionStorage.getItem(SELECTION_STORAGE_KEY)
            if (stored) {
                const ids = JSON.parse(stored)
                if (Array.isArray(ids)) {
                    selectedPlans = new Set(ids)
                }
            }
        } catch {
            // Storage may be unavailable or corrupted
        }
    }

    function clearSelectionStorage() {
        try {
            sessionStorage.removeItem(SELECTION_STORAGE_KEY)
        } catch {
            // Storage may be unavailable
        }
    }

    /**
     * Fetch pending plans from the API.
     */
    async function fetchPlans() {
        // Cancel any pending fetch
        if (currentFetchController) {
            currentFetchController.abort()
        }
        currentFetchController = new AbortController()

        try {
            const response = await fetch('/api/plans' + buildQueryString(), {
                signal: currentFetchController.signal
            })
            if (!response.ok) throw new Error('Failed to fetch plans: ' + response.status)

            const data = await response.json()
            totalPlans = data.total
            renderPlansTable(data.plans)
            updateCountText()
            updatePagination()

            loadingEl.style.display = 'none'
            contentEl.style.display = 'block'
        } catch (error) {
            if (error.name === 'AbortError') {
                // Fetch was cancelled, ignore
                return
            }
            console.error('Error fetching plans:', error)
            loadingEl.textContent = 'Error loading approvals. Please refresh the page.'
            loadingEl.style.color = 'var(--color-error)'
        } finally {
            currentFetchController = null
        }
    }

    /**
     * Set loading state on a button.
     */
    function setButtonLoading(btn, loading) {
        if (!btn) return
        btn.disabled = loading
        btn.classList.toggle('is-loading', loading)
        btn.setAttribute('aria-busy', loading.toString())
    }

    /**
     * Remove a row from the table with optimistic UI.
     * Returns the removed row data for potential restoration.
     */
    function removeRowOptimistically(planId) {
        const row = tableBodyEl.querySelector('[data-plan-id="' + planId + '"]')
        if (!row) return null

        const rowData = {
            element: row,
            nextSibling: row.nextElementSibling,
            html: row.outerHTML
        }

        row.remove()
        return rowData
    }

    /**
     * Restore a previously removed row.
     */
    function restoreRow(rowData) {
        if (!rowData || !rowData.html) return

        const temp = document.createElement('tbody')
        temp.innerHTML = rowData.html
        const row = temp.firstElementChild

        if (rowData.nextSibling && rowData.nextSibling.parentNode === tableBodyEl) {
            tableBodyEl.insertBefore(row, rowData.nextSibling)
        } else {
            tableBodyEl.appendChild(row)
        }
    }

    /**
     * Handle approve action.
     */
    async function handleApprove(planId, btn) {
        if (pendingActions[planId]) return

        if (typeof window.ConfirmationModal === 'undefined') {
            showToast('Confirmation dialog not available. Please refresh.', 'error')
            return
        }

        const confirmed = await window.ConfirmationModal.show(
            'This will queue a job to apply the planned changes. Continue?',
            { title: 'Approve Plan', confirmText: 'Approve and Queue', cancelText: 'Cancel' }
        )
        if (!confirmed) return

        // Track last focused for restoration
        lastFocusedPlanId = planId

        pendingActions[planId] = true
        setButtonLoading(btn, true)

        // Optimistic removal
        const removedRow = removeRowOptimistically(planId)

        try {
            const response = await fetch('/api/plans/' + planId + '/approve', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': window.CSRF_TOKEN }
            })
            const data = await response.json()

            if (data.success) {
                selectedPlans.delete(planId)
                saveSelectionToStorage()

                const msg = document.createDocumentFragment()
                msg.appendChild(document.createTextNode('Plan approved'))
                if (data.job_url) {
                    msg.appendChild(document.createTextNode('. '))
                    const link = document.createElement('a')
                    link.href = data.job_url
                    link.textContent = 'View job'
                    msg.appendChild(link)
                }
                showToast(msg, 'success')
                fetchPlans()
            } else {
                // Restore row on failure
                restoreRow(removedRow)
                showToast(data.error || 'Failed to approve plan', 'error')
                setButtonLoading(btn, false)
            }
        } catch (error) {
            // Restore row on failure
            restoreRow(removedRow)
            console.error('Error approving plan:', error)
            showToast('Failed to approve plan', 'error')
            setButtonLoading(btn, false)
        } finally {
            delete pendingActions[planId]
        }
    }

    /**
     * Handle reject action.
     */
    async function handleReject(planId, btn) {
        if (pendingActions[planId]) return

        if (typeof window.ConfirmationModal === 'undefined') {
            showToast('Confirmation dialog not available. Please refresh.', 'error')
            return
        }

        const confirmed = await window.ConfirmationModal.show(
            'Are you sure you want to reject this plan? This cannot be undone.',
            { title: 'Reject Plan', confirmText: 'Reject', cancelText: 'Cancel', focusCancel: true }
        )
        if (!confirmed) return

        // Track last focused for restoration
        lastFocusedPlanId = planId

        pendingActions[planId] = true
        setButtonLoading(btn, true)

        // Optimistic removal
        const removedRow = removeRowOptimistically(planId)

        try {
            const response = await fetch('/api/plans/' + planId + '/reject', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': window.CSRF_TOKEN }
            })
            const data = await response.json()

            if (data.success) {
                selectedPlans.delete(planId)
                saveSelectionToStorage()
                showToast('Plan rejected', 'success')
                fetchPlans()
            } else {
                // Restore row on failure
                restoreRow(removedRow)
                showToast(data.error || 'Failed to reject plan', 'error')
                setButtonLoading(btn, false)
            }
        } catch (error) {
            // Restore row on failure
            restoreRow(removedRow)
            console.error('Error rejecting plan:', error)
            showToast('Failed to reject plan', 'error')
            setButtonLoading(btn, false)
        } finally {
            delete pendingActions[planId]
        }
    }

    /**
     * Handle bulk approve with progress feedback.
     */
    async function handleBulkApprove() {
        const planIds = Array.from(selectedPlans)
        if (planIds.length === 0) {
            showToast('No plans selected', 'error')
            return
        }

        if (typeof window.ConfirmationModal === 'undefined') {
            showToast('Confirmation dialog not available. Please refresh.', 'error')
            return
        }

        const msg = planIds.length === 1
            ? 'Approve 1 selected plan?'
            : 'Approve ' + planIds.length + ' selected plans?'

        const confirmed = await window.ConfirmationModal.show(msg, {
            title: 'Bulk Approve',
            confirmText: 'Approve Selected',
            cancelText: 'Cancel'
        })
        if (!confirmed) return

        setButtonLoading(bulkApproveBtn, true)
        setButtonLoading(bulkRejectBtn, true)

        // Create abort controller for cancellation
        bulkOperationController = new AbortController()

        let successCount = 0
        let errorCount = 0
        const total = planIds.length

        // Show initial progress toast
        showToast('Approving 1 of ' + total + '...', 'info', { duration: 0 })

        for (let i = 0; i < planIds.length; i++) {
            // Check for cancellation
            if (bulkOperationController.signal.aborted) {
                break
            }

            const planId = planIds[i]
            updateToastMessage('Approving ' + (i + 1) + ' of ' + total + '...')

            try {
                const response = await fetch('/api/plans/' + planId + '/approve', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': window.CSRF_TOKEN },
                    signal: bulkOperationController.signal
                })
                const data = await response.json()
                if (data.success) successCount++
                else errorCount++
            } catch (error) {
                if (error.name === 'AbortError') {
                    break
                }
                errorCount++
            }
        }

        bulkOperationController = null
        setButtonLoading(bulkApproveBtn, false)
        setButtonLoading(bulkRejectBtn, false)

        if (errorCount === 0) {
            showToast(successCount + ' plan(s) approved', 'success')
        } else {
            showToast(successCount + ' approved, ' + errorCount + ' failed', 'error')
        }

        selectedPlans.clear()
        clearSelectionStorage()
        fetchPlans()
    }

    /**
     * Handle bulk reject with progress feedback.
     */
    async function handleBulkReject() {
        const planIds = Array.from(selectedPlans)
        if (planIds.length === 0) {
            showToast('No plans selected', 'error')
            return
        }

        if (typeof window.ConfirmationModal === 'undefined') {
            showToast('Confirmation dialog not available. Please refresh.', 'error')
            return
        }

        const msg = planIds.length === 1
            ? 'Reject 1 selected plan? This cannot be undone.'
            : 'Reject ' + planIds.length + ' selected plans? This cannot be undone.'

        const confirmed = await window.ConfirmationModal.show(msg, {
            title: 'Bulk Reject',
            confirmText: 'Reject Selected',
            cancelText: 'Cancel',
            focusCancel: true
        })
        if (!confirmed) return

        setButtonLoading(bulkApproveBtn, true)
        setButtonLoading(bulkRejectBtn, true)

        // Create abort controller for cancellation
        bulkOperationController = new AbortController()

        let successCount = 0
        let errorCount = 0
        const total = planIds.length

        // Show initial progress toast
        showToast('Rejecting 1 of ' + total + '...', 'info', { duration: 0 })

        for (let i = 0; i < planIds.length; i++) {
            // Check for cancellation
            if (bulkOperationController.signal.aborted) {
                break
            }

            const planId = planIds[i]
            updateToastMessage('Rejecting ' + (i + 1) + ' of ' + total + '...')

            try {
                const response = await fetch('/api/plans/' + planId + '/reject', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': window.CSRF_TOKEN },
                    signal: bulkOperationController.signal
                })
                const data = await response.json()
                if (data.success) successCount++
                else errorCount++
            } catch (error) {
                if (error.name === 'AbortError') {
                    break
                }
                errorCount++
            }
        }

        bulkOperationController = null
        setButtonLoading(bulkApproveBtn, false)
        setButtonLoading(bulkRejectBtn, false)

        if (errorCount === 0) {
            showToast(successCount + ' plan(s) rejected', 'success')
        } else {
            showToast(successCount + ' rejected, ' + errorCount + ' failed', 'error')
        }

        selectedPlans.clear()
        clearSelectionStorage()
        fetchPlans()
    }

    /**
     * Update select all checkbox state.
     */
    function updateSelectAllState() {
        const checkboxes = tableBodyEl.querySelectorAll('.plan-checkbox')
        const allChecked = checkboxes.length > 0 && Array.from(checkboxes).every(cb => cb.checked)
        const someChecked = Array.from(checkboxes).some(cb => cb.checked)

        if (selectAllCheckbox) {
            selectAllCheckbox.checked = allChecked
            selectAllCheckbox.indeterminate = someChecked && !allChecked
        }
    }

    /**
     * Handle row click for navigation.
     */
    function handleRowClick(planId) {
        window.location.href = '/plans/' + planId
    }

    // Event listeners
    if (prevBtnEl) prevBtnEl.addEventListener('click', function () {
        if (currentOffset >= pageSize) {
            currentOffset -= pageSize
            fetchPlans()
        }
    })

    if (nextBtnEl) nextBtnEl.addEventListener('click', function () {
        if (currentOffset + pageSize < totalPlans) {
            currentOffset += pageSize
            fetchPlans()
        }
    })

    const timeFilterEl = document.getElementById('filter-time')
    if (timeFilterEl) timeFilterEl.addEventListener('change', function (e) {
        currentSince = e.target.value
        currentOffset = 0
        fetchPlans()
    })

    if (selectAllCheckbox) selectAllCheckbox.addEventListener('change', function (e) {
        const checkboxes = tableBodyEl.querySelectorAll('.plan-checkbox')
        checkboxes.forEach(function (cb) {
            cb.checked = e.target.checked
            const planId = cb.getAttribute('data-plan-id')
            if (e.target.checked) {
                selectedPlans.add(planId)
            } else {
                selectedPlans.delete(planId)
            }
        })
        saveSelectionToStorage()
    })

    if (bulkApproveBtn) bulkApproveBtn.addEventListener('click', handleBulkApprove)
    if (bulkRejectBtn) bulkRejectBtn.addEventListener('click', handleBulkReject)

    // Event delegation for table body
    if (tableBodyEl) {
        tableBodyEl.addEventListener('click', function (e) {
            // Handle checkbox clicks
            const checkbox = e.target.closest('.plan-checkbox')
            if (checkbox) {
                e.stopPropagation()
                const planId = checkbox.getAttribute('data-plan-id')
                if (checkbox.checked) {
                    selectedPlans.add(planId)
                } else {
                    selectedPlans.delete(planId)
                }
                updateSelectAllState()
                saveSelectionToStorage()
                return
            }

            // Handle action button clicks
            const btn = e.target.closest('.plan-action-btn')
            if (btn) {
                e.stopPropagation()
                const planId = btn.getAttribute('data-plan-id')
                const action = btn.getAttribute('data-action')
                if (!planId || !action || btn.disabled) return

                if (action === 'approve') handleApprove(planId, btn)
                else if (action === 'reject') handleReject(planId, btn)
                return
            }

            // Handle row clicks for navigation
            const row = e.target.closest('.plan-row-clickable')
            if (row) {
                const planId = row.getAttribute('data-plan-id')
                if (planId) handleRowClick(planId)
            }
        })

        // Keyboard navigation
        tableBodyEl.addEventListener('keydown', function (e) {
            const row = e.target.closest('.plan-row-clickable')
            if (!row) return
            if (e.target.closest('.plan-action-btn') || e.target.closest('.plan-checkbox')) return

            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                const planId = row.getAttribute('data-plan-id')
                if (planId) handleRowClick(planId)
            }
        })
    }

    // Load persisted selections and initialize
    loadSelectionFromStorage()
    fetchPlans()
})()
