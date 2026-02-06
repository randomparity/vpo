/**
 * Plans Dashboard JavaScript (026-plans-list-view)
 *
 * Handles fetching plans from the API, rendering the table,
 * filtering, pagination, inline actions, and live polling updates.
 */

(function () {
    'use strict'

    // State
    let currentOffset = 0
    const pageSize = 50
    let currentFilters = {
        status: '',
        since: ''
    }
    let totalPlans = 0

    // Cached plan data for comparison
    var cachedPlans = {}

    // Polling instance
    var pollingInstance = null

    // Track initialization to prevent double init
    var initialized = false

    // Track in-flight action requests to prevent double-submit
    var pendingActions = {}

    // DOM elements
    const loadingEl = document.getElementById('plans-loading')
    const contentEl = document.getElementById('plans-content')
    const tableBodyEl = document.getElementById('plans-table-body')
    const tableEl = document.getElementById('plans-table')
    const emptyEl = document.getElementById('plans-empty')
    const emptyTitleEl = document.getElementById('plans-empty-title')
    const emptyHintEl = document.getElementById('plans-empty-hint')
    const paginationEl = document.getElementById('plans-pagination')
    const paginationInfoEl = document.getElementById('plans-pagination-info')
    const prevBtnEl = document.getElementById('plans-prev-btn')
    const nextBtnEl = document.getElementById('plans-next-btn')
    const toastEl = document.getElementById('plans-toast')

    // Shared utilities
    var escapeHtml = window.VPOUtils.escapeHtml
    var _formatRelativeTime = window.VPOUtils.formatRelativeTime
    function formatRelativeTime(input) {
        return _formatRelativeTime(input, { emptyText: '-', dateFallbackDays: 7, capitalizeJustNow: false })
    }

    /**
     * Format source file display, handling deleted files.
     * @param {Object} plan - Plan data from API
     * @returns {string} Formatted display string
     */
    function formatSourceDisplay(plan) {
        if (plan.file_deleted) {
            return '<span class="plan-file-deleted">[Deleted]</span> ' + escapeHtml(plan.filename)
        }
        return escapeHtml(plan.filename)
    }

    /**
     * Create a status badge element.
     * @param {Object} plan - Plan data from API
     * @returns {string} HTML string for status badge
     */
    function createStatusBadge(plan) {
        const badge = plan.status_badge || { class: 'status-unknown', label: plan.status }
        return '<span class="status-badge ' + escapeHtml(badge.class) + '">' + escapeHtml(badge.label) + '</span>'
    }

    /**
     * Create action buttons for a plan row.
     * Only shows buttons for pending plans.
     * Uses data attributes for event delegation (no inline onclick).
     * @param {Object} plan - Plan data from API
     * @returns {string} HTML string for action buttons
     */
    function createActionButtons(plan) {
        if (plan.status !== 'pending') {
            return '<span class="plan-actions-empty">-</span>'
        }

        var shortId = plan.id_short || plan.id.substring(0, 8)

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
     * Uses tabindex and role for keyboard accessibility.
     * Uses data attributes for event delegation (no inline onclick).
     * @param {Object} plan - Plan data from API
     * @returns {string} HTML string for table row
     */
    function renderPlanRow(plan) {
        const shortId = plan.id_short || plan.id.substring(0, 8)
        const remuxIndicator = plan.requires_remux
            ? ' <span class="plan-remux-indicator" title="Requires container remux">*</span>'
            : ''

        // Make row keyboard-accessible and clickable (navigation to detail view)
        return '<tr class="plan-row plan-row-clickable" ' +
            'data-plan-id="' + escapeHtml(plan.id) + '" ' +
            'tabindex="0" ' +
            'role="row" ' +
            'aria-label="Plan ' + escapeHtml(shortId) + ' for ' + escapeHtml(plan.filename) + ', status ' + escapeHtml(plan.status) + '">' +
            '<td class="plan-id" title="' + escapeHtml(plan.id) + '">' + escapeHtml(shortId) + '</td>' +
            '<td class="plan-file">' + formatSourceDisplay(plan) + '</td>' +
            '<td class="plan-policy">' + escapeHtml(plan.policy_name) + '</td>' +
            '<td class="plan-action-count">' + plan.action_count + remuxIndicator + '</td>' +
            '<td class="plan-status">' + createStatusBadge(plan) + '</td>' +
            '<td class="plan-created">' + formatRelativeTime(plan.created_at) + '</td>' +
            '<td class="plan-actions-cell">' + createActionButtons(plan) + '</td>' +
            '</tr>'
    }

    /**
     * Render the plans table.
     * @param {Array} plans - Array of plan objects
     * @param {boolean} hasFilters - Whether any filters are active
     */
    function renderPlansTable(plans, hasFilters) {
        if (plans.length === 0) {
            tableEl.style.display = 'none'
            emptyEl.style.display = 'block'

            if (hasFilters) {
                emptyTitleEl.textContent = 'No matching plans'
                emptyHintEl.textContent = 'Try adjusting your filters or clear them to see all plans.'
            } else {
                emptyTitleEl.textContent = 'No plans found'
                emptyHintEl.textContent = 'Plans are generated when you evaluate policies against files. Run a scan or apply operation to create plans.'
            }
            return
        }

        tableEl.style.display = 'table'
        emptyEl.style.display = 'none'

        const html = plans.map(renderPlanRow).join('')
        tableBodyEl.innerHTML = html
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
        paginationInfoEl.textContent = 'Showing ' + start + '-' + end + ' of ' + totalPlans + ' plans'

        prevBtnEl.disabled = currentOffset === 0
        nextBtnEl.disabled = currentOffset + pageSize >= totalPlans
    }

    /**
     * Build query string from current filters.
     * @returns {string} Query string (including leading ?)
     */
    function buildQueryString() {
        const params = new URLSearchParams()

        if (currentFilters.status) {
            params.set('status', currentFilters.status)
        }
        if (currentFilters.since) {
            params.set('since', currentFilters.since)
        }

        params.set('limit', pageSize.toString())
        params.set('offset', currentOffset.toString())

        return '?' + params.toString()
    }

    // Toast auto-hide timer (for pause on hover)
    var toastTimer = null
    var toastListenersAdded = false

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
     * Show toast notification with close button and pause on hover.
     * @param {string|HTMLElement|DocumentFragment} message - Message to display (string or DOM node)
     * @param {string} type - Toast type (success, error)
     */
    function showToast(message, type) {
        if (!toastEl) return

        // Clear any existing timer
        if (toastTimer) {
            clearTimeout(toastTimer)
        }

        // Add hover listeners once (prevent memory leak)
        if (!toastListenersAdded) {
            toastEl.addEventListener('mouseenter', function () {
                if (toastTimer) {
                    clearTimeout(toastTimer)
                    toastTimer = null
                }
            })
            toastEl.addEventListener('mouseleave', function () {
                if (toastEl.style.display !== 'none') {
                    toastTimer = setTimeout(hideToast, 2000)
                }
            })
            toastListenersAdded = true
        }

        // Build toast content with close button using DOM APIs
        toastEl.innerHTML = ''
        toastEl.className = 'plans-toast plans-toast--' + type

        var messageSpan = document.createElement('span')
        messageSpan.className = 'toast-message'

        if (typeof message === 'string') {
            // Plain string - escape for safety
            messageSpan.textContent = message
        } else if (message instanceof DocumentFragment || message instanceof HTMLElement) {
            // DOM element or fragment - append directly (already safe)
            messageSpan.appendChild(message)
        }

        toastEl.appendChild(messageSpan)

        var closeBtn = document.createElement('button')
        closeBtn.type = 'button'
        closeBtn.className = 'toast-close'
        closeBtn.setAttribute('aria-label', 'Dismiss notification')
        closeBtn.innerHTML = '&times;'
        closeBtn.addEventListener('click', hideToast)
        toastEl.appendChild(closeBtn)

        toastEl.style.display = 'flex'

        // Auto-hide after 5 seconds (increased from 3s for accessibility)
        toastTimer = setTimeout(hideToast, 5000)
    }

    /**
     * Fetch plans from the API and render them.
     */
    async function fetchPlans() {
        try {
            const response = await fetch('/api/plans' + buildQueryString())

            if (!response.ok) {
                throw new Error('Failed to fetch plans: ' + response.status)
            }

            const data = await response.json()

            totalPlans = data.total
            renderPlansTable(data.plans, data.has_filters)
            updatePagination()

            // Update cache with fetched plans
            updatePlansCache(data.plans)

            // Show content, hide loading
            loadingEl.style.display = 'none'
            contentEl.style.display = 'block'

        } catch (error) {
            console.error('Error fetching plans:', error)
            loadingEl.textContent = 'Error loading plans. Please refresh the page.'
            loadingEl.style.color = 'var(--color-error)'
        }
    }

    // ==========================================================================
    // Polling Support
    // ==========================================================================

    /**
     * Update the plans cache with new data.
     * @param {Array} plans - Array of plan objects
     */
    function updatePlansCache(plans) {
        cachedPlans = {}
        for (var i = 0; i < plans.length; i++) {
            cachedPlans[plans[i].id] = plans[i]
        }
    }

    /**
     * Check if a plan has changed compared to cached data.
     * @param {Object} newPlan - New plan data
     * @returns {boolean} True if plan has changed
     */
    function hasPlanChanged(newPlan) {
        var cached = cachedPlans[newPlan.id]
        if (!cached) {
            return true // New plan
        }

        return cached.status !== newPlan.status ||
               cached.updated_at !== newPlan.updated_at
    }

    /**
     * Fetch plans for polling, preserving filter state.
     * @returns {Promise} Resolves when fetch is complete
     */
    function fetchPlansForPolling() {
        return fetch('/api/plans' + buildQueryString())
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('Failed to fetch plans: ' + response.status)
                }
                return response.json()
            })
            .then(function (data) {
                var totalChanged = totalPlans !== data.total
                totalPlans = data.total

                // Check for changes
                var hasChanges = false
                var newPlanIds = {}

                for (var i = 0; i < data.plans.length; i++) {
                    var plan = data.plans[i]
                    newPlanIds[plan.id] = true

                    if (hasPlanChanged(plan)) {
                        hasChanges = true
                    }
                }

                // Check for removed plans
                for (var cachedId in cachedPlans) {
                    if (!newPlanIds[cachedId]) {
                        hasChanges = true
                    }
                }

                if (hasChanges || totalChanged) {
                    renderPlansTable(data.plans, data.has_filters)
                    updatePlansCache(data.plans)
                    updatePagination()
                }
            })
    }

    /**
     * Initialize polling for plans dashboard.
     */
    function initPolling() {
        if (typeof window.VPOPolling === 'undefined') {
            console.warn('[Plans] VPOPolling not available, polling disabled')
            return
        }

        pollingInstance = window.VPOPolling.create({
            fetchFn: fetchPlansForPolling,
            onStatusChange: function (_status) {
                // Connection status handled by VPOPolling
            }
        })

        pollingInstance.start()

        window.VPOPolling.onCleanup(function () {
            if (pollingInstance) {
                pollingInstance.cleanup()
                pollingInstance = null
            }
        })
    }

    // ==========================================================================
    // Action Handlers
    // ==========================================================================

    /**
     * Set loading state on an action button.
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
     * Handle approve action for a plan.
     * Shows confirmation modal before approving.
     * @param {string} planId - Plan UUID
     * @param {HTMLElement} btn - Button element (optional, for loading state)
     */
    async function handleApprove(planId, btn) {
        // Show confirmation modal - require it to be loaded
        if (typeof window.ConfirmationModal === 'undefined') {
            console.error('[Plans] ConfirmationModal not loaded - cannot approve without confirmation')
            showToast('Unable to show confirmation dialog. Please refresh the page.', 'error')
            return
        }

        var confirmed = await window.ConfirmationModal.show(
            'This will queue a job to apply the planned changes to the file. Continue?',
            {
                title: 'Approve Plan',
                confirmText: 'Approve and Queue',
                cancelText: 'Cancel'
            }
        )
        if (!confirmed) {
            return
        }

        // Prevent double-submit
        if (pendingActions[planId]) {
            return
        }
        pendingActions[planId] = true
        setButtonLoading(btn, true)

        try {
            const response = await fetch('/api/plans/' + planId + '/approve', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': window.VPOUtils.getCsrfToken()
                }
            })

            const data = await response.json()

            if (data.success) {
                // Build success message with job link using DOM APIs (safe from XSS)
                var messageEl = document.createDocumentFragment()
                messageEl.appendChild(document.createTextNode('Plan approved successfully'))

                if (data.job_url) {
                    messageEl.appendChild(document.createTextNode('. '))
                    var link = document.createElement('a')
                    link.href = data.job_url
                    link.textContent = 'View job'
                    messageEl.appendChild(link)
                }

                if (data.warning) {
                    messageEl.appendChild(document.createTextNode(' '))
                    var warningSpan = document.createElement('span')
                    warningSpan.className = 'toast-warning'
                    warningSpan.textContent = 'Warning: ' + data.warning
                    messageEl.appendChild(warningSpan)
                }

                showToast(messageEl, 'success')
                // Refresh to show updated status
                fetchPlans()
            } else {
                showToast(data.error || 'Failed to approve plan', 'error')
                setButtonLoading(btn, false)
            }
        } catch (error) {
            console.error('Error approving plan:', error)
            showToast('Failed to approve plan', 'error')
            setButtonLoading(btn, false)
        } finally {
            delete pendingActions[planId]
        }
    }

    /**
     * Handle reject action for a plan.
     * Shows confirmation modal before rejecting.
     * @param {string} planId - Plan UUID
     * @param {HTMLElement} btn - Button element (optional, for loading state)
     */
    async function handleReject(planId, btn) {
        // Show confirmation modal - require it to be loaded
        if (typeof window.ConfirmationModal === 'undefined') {
            console.error('[Plans] ConfirmationModal not loaded - cannot reject without confirmation')
            showToast('Unable to show confirmation dialog. Please refresh the page.', 'error')
            return
        }

        var confirmed = await window.ConfirmationModal.show(
            'Are you sure you want to reject this plan? This cannot be undone.',
            {
                title: 'Reject Plan',
                confirmText: 'Reject',
                cancelText: 'Cancel',
                focusCancel: true
            }
        )
        if (!confirmed) {
            return
        }

        // Prevent double-submit
        if (pendingActions[planId]) {
            return
        }
        pendingActions[planId] = true
        setButtonLoading(btn, true)

        try {
            const response = await fetch('/api/plans/' + planId + '/reject', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': window.VPOUtils.getCsrfToken()
                }
            })

            const data = await response.json()

            if (data.success) {
                showToast('Plan rejected', 'success')
                // Refresh to show updated status
                fetchPlans()
            } else {
                showToast(data.error || 'Failed to reject plan', 'error')
                setButtonLoading(btn, false)
            }
        } catch (error) {
            console.error('Error rejecting plan:', error)
            showToast('Failed to reject plan', 'error')
            setButtonLoading(btn, false)
        } finally {
            delete pendingActions[planId]
        }
    }

    /**
     * Handle row click (navigation to detail view).
     * @param {string} planId - Plan UUID
     */
    function handleRowClick(planId) {
        // Navigate to plan detail view (placeholder - detail view is separate feature)
        window.location.href = '/plans/' + planId
    }

    // ==========================================================================
    // Event Handlers
    // ==========================================================================

    /**
     * Handle pagination - previous page.
     */
    function handlePrevPage() {
        if (currentOffset >= pageSize) {
            currentOffset -= pageSize
            fetchPlans()
        }
    }

    /**
     * Handle pagination - next page.
     */
    function handleNextPage() {
        if (currentOffset + pageSize < totalPlans) {
            currentOffset += pageSize
            fetchPlans()
        }
    }

    /**
     * Handle status filter change.
     * @param {string} status - New status filter value
     */
    function handleStatusFilter(status) {
        currentFilters.status = status
        currentOffset = 0
        fetchPlans()
    }

    /**
     * Handle time filter change.
     * @param {string} since - New time filter value
     */
    function handleTimeFilter(since) {
        currentFilters.since = since
        currentOffset = 0
        fetchPlans()
    }

    // Event listeners for pagination
    if (prevBtnEl) {
        prevBtnEl.addEventListener('click', handlePrevPage)
    }
    if (nextBtnEl) {
        nextBtnEl.addEventListener('click', handleNextPage)
    }

    // Event listeners for filters
    const statusFilterEl = document.getElementById('filter-status')
    const timeFilterEl = document.getElementById('filter-time')

    if (statusFilterEl) {
        statusFilterEl.addEventListener('change', function (e) {
            handleStatusFilter(e.target.value)
        })
    }
    if (timeFilterEl) {
        timeFilterEl.addEventListener('change', function (e) {
            handleTimeFilter(e.target.value)
        })
    }

    // Event delegation for table body (keyboard navigation and action buttons)
    if (tableBodyEl) {
        // Keyboard navigation for table rows
        tableBodyEl.addEventListener('keydown', function (e) {
            var row = e.target.closest('.plan-row-clickable')
            if (!row) return

            // Don't navigate if focus is on action button
            if (e.target.closest('.plan-action-btn')) return

            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                var planId = row.getAttribute('data-plan-id')
                if (planId) {
                    handleRowClick(planId)
                }
            }
        })

        // Click delegation for row navigation
        tableBodyEl.addEventListener('click', function (e) {
            // Don't navigate if clicking on action buttons
            if (e.target.closest('.plan-action-btn')) return

            var row = e.target.closest('.plan-row-clickable')
            if (row) {
                var planId = row.getAttribute('data-plan-id')
                if (planId) {
                    handleRowClick(planId)
                }
            }
        })

        // Click delegation for action buttons
        tableBodyEl.addEventListener('click', function (e) {
            var btn = e.target.closest('.plan-action-btn')
            if (!btn) return

            e.stopPropagation() // Prevent row click

            var planId = btn.getAttribute('data-plan-id')
            var action = btn.getAttribute('data-action')

            if (!planId || !action) return
            if (btn.disabled) return

            if (action === 'approve') {
                handleApprove(planId, btn)
            } else if (action === 'reject') {
                handleReject(planId, btn)
            }
        })
    }

    // Export functions for backwards compatibility (polling, etc.)
    window.plansDashboard = {
        handleStatusFilter: handleStatusFilter,
        handleTimeFilter: handleTimeFilter,
        handleApprove: handleApprove,
        handleReject: handleReject,
        handleRowClick: handleRowClick
    }

    /**
     * Initialize the plans dashboard.
     */
    function init() {
        // Prevent double initialization
        if (initialized) return
        initialized = true

        // Initial fetch
        fetchPlans()

        // Initialize polling after initial fetch
        setTimeout(function () {
            initPolling()
        }, 100)
    }

    // Initial fetch on page load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init)
    } else {
        init()
    }
})()
