/**
 * Jobs Dashboard JavaScript
 *
 * Handles fetching jobs from the API, rendering the table,
 * filtering, pagination, and live polling updates (017-live-job-polling).
 */

(function () {
    'use strict'

    // Double-init guard
    let initialized = false

    // State
    let currentOffset = 0
    const pageSize = 50
    let currentFilters = {
        status: '',
        type: '',
        since: '',
        search: ''
    }
    let currentSort = {
        column: 'created_at',
        order: 'desc'
    }
    let totalJobs = 0

    // Debounce timer for search
    let debounceTimer = null
    const DEBOUNCE_DELAY = 300 // ms

    // Cached job data for comparison (T013)
    let cachedJobs = {}

    // Polling instance (T014)
    let pollingInstance = null

    // DOM elements
    const loadingEl = document.getElementById('jobs-loading')
    const errorEl = document.getElementById('jobs-error')
    const errorMessageEl = document.getElementById('jobs-error-message')
    const retryBtnEl = document.getElementById('jobs-retry-btn')
    const contentEl = document.getElementById('jobs-content')
    const tableBodyEl = document.getElementById('jobs-table-body')
    const tableEl = document.getElementById('jobs-table')
    const emptyEl = document.getElementById('jobs-empty')
    const emptyTitleEl = document.getElementById('jobs-empty-title')
    const emptyHintEl = document.getElementById('jobs-empty-hint')
    const paginationEl = document.getElementById('jobs-pagination')
    const paginationInfoEl = document.getElementById('jobs-pagination-info')
    const prevBtnEl = document.getElementById('jobs-prev-btn')
    const nextBtnEl = document.getElementById('jobs-next-btn')

    // Shared utilities
    const escapeHtml = window.VPOUtils.escapeHtml
    const truncateFilename = window.VPOUtils.truncateFilename
    const formatDuration = window.VPOUtils.formatDuration

    /**
     * Format an ISO timestamp to a localized date/time string.
     * @param {string} isoString - ISO 8601 timestamp
     * @returns {string} Formatted date/time
     */
    function formatDateTime(isoString) {
        if (!isoString) {
            return '-'
        }

        try {
            const date = new Date(isoString)
            return date.toLocaleString(undefined, {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            })
        } catch {
            return isoString
        }
    }

    /**
     * Extract the filename from a path.
     * @param {string} path - Full file path
     * @returns {string} Filename only
     */
    function getFilename(path) {
        if (!path) return ''
        const parts = path.split('/')
        return parts[parts.length - 1] || ''
    }

    /**
     * Create a status badge element.
     * Handles unknown status values gracefully.
     * @param {string} status - Job status
     * @returns {string} HTML string for status badge
     */
    function createStatusBadge(status) {
        // Known statuses have specific styling
        const knownStatuses = ['queued', 'running', 'completed', 'failed', 'cancelled']
        const normalizedStatus = (status || 'unknown').toLowerCase()
        const statusClass = knownStatuses.includes(normalizedStatus)
            ? 'status-badge--' + normalizedStatus
            : 'status-badge--queued'  // Default to neutral gray styling
        const displayStatus = status || 'unknown'
        return '<span class="status-badge ' + statusClass + '">' + escapeHtml(displayStatus) + '</span>'
    }

    /**
     * Create a type badge element.
     * @param {string} type - Job type
     * @returns {string} HTML string for type badge
     */
    function createTypeBadge(type) {
        return '<span class="type-badge">' + escapeHtml(type) + '</span>'
    }

    /**
     * Create a progress bar element (T025, T026, T028).
     * @param {Object} job - Job data from API
     * @returns {string} HTML string for progress bar
     */
    function createProgressBar(job) {
        const status = job.status
        const percent = job.progress_percent

        // For completed/failed/cancelled jobs, show 100% or appropriate state
        if (status === 'completed') {
            return '<div class="job-progress">' +
                '<div class="job-progress-track">' +
                '<div class="job-progress-bar job-progress-bar--completed job-progress-bar--w100"></div>' +
                '</div>' +
                '<span class="job-progress-text">100%</span>' +
                '</div>'
        }

        if (status === 'failed' || status === 'cancelled') {
            const barClass = status === 'failed' ? 'job-progress-bar--failed' : ''
            const displayPercent = percent !== null && percent !== undefined ? percent : 0
            return '<div class="job-progress">' +
                '<div class="job-progress-track">' +
                '<div class="job-progress-bar ' + barClass + '" data-width="' + displayPercent + '"></div>' +
                '</div>' +
                '<span class="job-progress-text">' + displayPercent + '%</span>' +
                '</div>'
        }

        // For queued jobs, show empty progress
        if (status === 'queued') {
            return '<div class="job-progress">' +
                '<div class="job-progress-track">' +
                '<div class="job-progress-bar job-progress-bar--w0"></div>' +
                '</div>' +
                '<span class="job-progress-text">—</span>' +
                '</div>'
        }

        // For running jobs with no progress data, show indeterminate (T028)
        if (percent === null || percent === undefined) {
            return '<div class="job-progress">' +
                '<div class="job-progress-track">' +
                '<div class="job-progress-bar job-progress-bar--indeterminate"></div>' +
                '</div>' +
                '<span class="job-progress-text">...</span>' +
                '</div>'
        }

        // For running jobs with progress data
        return '<div class="job-progress">' +
            '<div class="job-progress-track">' +
            '<div class="job-progress-bar" data-width="' + percent + '"></div>' +
            '</div>' +
            '<span class="job-progress-text">' + percent + '%</span>' +
            '</div>'
    }

    /**
     * Render a single job row.
     * @param {Object} job - Job data from API
     * @returns {string} HTML string for table row
     */
    function renderJobRow(job) {
        const shortId = job.id.substring(0, 8)
        const filename = getFilename(job.file_path)
        const truncatedFilename = truncateFilename(filename, 50)
        const hasFullPath = job.file_path && job.file_path.length > 50

        // Calculate duration for running jobs
        let duration = job.duration_seconds
        if (job.status === 'running' && job.created_at && duration === null) {
            const created = new Date(job.created_at)
            const now = new Date()
            duration = Math.floor((now - created) / 1000)
        }

        // Make row clickable - link to job detail view (016-job-detail-view)
        return '<tr class="job-row-clickable" data-job-id="' + escapeHtml(job.id) + '" tabindex="0" role="link" aria-label="View job ' + escapeHtml(shortId) + '">' +
            '<td class="job-id" title="' + escapeHtml(job.id) + '">' + escapeHtml(shortId) + '</td>' +
            '<td class="job-type">' + createTypeBadge(job.job_type) + '</td>' +
            '<td class="job-status">' + createStatusBadge(job.status) + '</td>' +
            '<td class="job-progress-cell">' + createProgressBar(job) + '</td>' +
            '<td class="job-path"' + (hasFullPath ? ' title="' + escapeHtml(job.file_path) + '"' : '') + '>' + escapeHtml(truncatedFilename) + '</td>' +
            '<td class="job-created">' + formatDateTime(job.created_at) + '</td>' +
            '<td class="job-duration">' + formatDuration(duration) + '</td>' +
            '</tr>'
    }

    /**
     * Render the jobs table.
     * @param {Array} jobs - Array of job objects
     * @param {boolean} hasFilters - Whether any filters are active
     */
    function renderJobsTable(jobs, hasFilters) {
        if (jobs.length === 0) {
            tableEl.style.display = 'none'
            emptyEl.style.display = 'block'

            if (hasFilters) {
                emptyTitleEl.textContent = 'No matching jobs'
                emptyHintEl.textContent = 'Try adjusting your filters or clear them to see all jobs.'
            } else {
                emptyTitleEl.textContent = 'No jobs found'
                emptyHintEl.textContent = 'Jobs will appear here when you run scan, apply, or transcode operations.'
            }
            return
        }

        tableEl.style.display = 'table'
        emptyEl.style.display = 'none'

        const html = jobs.map(renderJobRow).join('')
        tableBodyEl.innerHTML = html
        applyDataWidths(tableBodyEl)
    }

    /**
     * Apply data-width attributes as inline style.width via CSSOM (CSP-safe).
     */
    function applyDataWidths(container) {
        var bars = container.querySelectorAll('.job-progress-bar[data-width]')
        for (var i = 0; i < bars.length; i++) {
            bars[i].style.width = bars[i].getAttribute('data-width') + '%'
        }
    }

    /**
     * Update pagination controls.
     */
    function updatePagination() {
        if (totalJobs <= pageSize) {
            paginationEl.style.display = 'none'
            return
        }

        paginationEl.style.display = 'flex'

        const start = currentOffset + 1
        const end = Math.min(currentOffset + pageSize, totalJobs)
        paginationInfoEl.textContent = 'Showing ' + start + '-' + end + ' of ' + totalJobs + ' jobs'

        prevBtnEl.disabled = currentOffset === 0
        nextBtnEl.disabled = currentOffset + pageSize >= totalJobs
    }

    /**
     * Build query string from current filters and sort.
     * @returns {string} Query string (including leading ?)
     */
    function buildQueryString() {
        const params = new URLSearchParams()

        if (currentFilters.status) {
            params.set('status', currentFilters.status)
        }
        if (currentFilters.type) {
            params.set('type', currentFilters.type)
        }
        if (currentFilters.since) {
            params.set('since', currentFilters.since)
        }
        if (currentFilters.search) {
            params.set('search', currentFilters.search)
        }

        // Include sort params
        if (currentSort.column) {
            params.set('sort', currentSort.column)
        }
        if (currentSort.order) {
            params.set('order', currentSort.order)
        }

        params.set('limit', pageSize.toString())
        params.set('offset', currentOffset.toString())

        return '?' + params.toString()
    }

    /**
     * Fetch jobs from the API and render them.
     */
    async function fetchJobs() {
        try {
            const response = await fetch('/api/jobs' + buildQueryString())

            if (!response.ok) {
                throw new Error('Failed to fetch jobs: ' + response.status)
            }

            const data = await response.json()

            totalJobs = data.total
            renderJobsTable(data.jobs, data.has_filters)
            updatePagination()

            // Update cache with fetched jobs (T013)
            updateJobsCache(data.jobs)

            // Show content, hide loading
            showContent()

        } catch (error) {
            console.error('Error fetching jobs:', error)
            showError(error.message || 'Failed to load jobs. Please try again.')
        }
    }

    // ==========================================================================
    // Real-Time Updates Support (SSE with polling fallback)
    // ==========================================================================

    // SSE client instance
    let sseClient = null

    /**
     * Update the jobs cache with new data (T013).
     * @param {Array} jobs - Array of job objects
     */
    function updateJobsCache(jobs) {
        cachedJobs = {}
        for (let i = 0; i < jobs.length; i++) {
            cachedJobs[jobs[i].id] = jobs[i]
        }
    }

    /**
     * Check if a job has changed compared to cached data (T013).
     * @param {Object} newJob - New job data
     * @returns {boolean} True if job has changed
     */
    function hasJobChanged(newJob) {
        const cached = cachedJobs[newJob.id]
        if (!cached) {
            return true // New job
        }

        // Compare key fields
        return cached.status !== newJob.status ||
               cached.progress_percent !== newJob.progress_percent ||
               cached.duration_seconds !== newJob.duration_seconds ||
               cached.completed_at !== newJob.completed_at
    }

    /**
     * Update a single job row without re-rendering the entire table (T015).
     * @param {string} jobId - Job UUID
     * @param {Object} newData - New job data
     */
    function updateJobRow(jobId, newData) {
        const row = tableBodyEl.querySelector('tr[data-job-id="' + jobId + '"]')
        if (!row) {
            return false // Row not found
        }

        // Calculate duration for running jobs
        let duration = newData.duration_seconds
        if (newData.status === 'running' && newData.created_at && duration === null) {
            const created = new Date(newData.created_at)
            const now = new Date()
            duration = Math.floor((now - created) / 1000)
        }

        // Update status cell
        const statusCell = row.querySelector('.job-status')
        if (statusCell) {
            statusCell.innerHTML = createStatusBadge(newData.status)
        }

        // Update progress cell (T025)
        const progressCell = row.querySelector('.job-progress-cell')
        if (progressCell) {
            progressCell.innerHTML = createProgressBar(newData)
            applyDataWidths(progressCell)
        }

        // Update duration cell
        const durationCell = row.querySelector('.job-duration')
        if (durationCell) {
            durationCell.textContent = formatDuration(duration)
        }

        // Add visual feedback animation for the update
        row.classList.remove('job-row-updated')
        // Force reflow to restart animation
        void row.offsetWidth
        row.classList.add('job-row-updated')

        return true
    }

    /**
     * Fetch jobs for polling, preserving filter state (T011).
     * Returns a promise that resolves when fetch is complete.
     * @returns {Promise} Resolves when fetch is complete
     */
    function fetchJobsForPolling() {
        return fetch('/api/jobs' + buildQueryString())
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('Failed to fetch jobs: ' + response.status)
                }
                return response.json()
            })
            .then(function (data) {
                // Update total and pagination
                const totalChanged = totalJobs !== data.total
                totalJobs = data.total

                // Check for changes and update (T012)
                const newJobIds = {}

                for (let i = 0; i < data.jobs.length; i++) {
                    const job = data.jobs[i]
                    newJobIds[job.id] = true

                    if (hasJobChanged(job)) {
                        // Try to update existing row
                        if (!updateJobRow(job.id, job)) {
                            // Job not in current view - could be new
                            // For simplicity, do a full re-render if we have new jobs
                            renderJobsTable(data.jobs, data.has_filters)
                            updateJobsCache(data.jobs)
                            updatePagination()
                            return
                        }
                    }
                }

                // Check for removed jobs (jobs in cache but not in new data)
                for (const cachedId in cachedJobs) {
                    if (!newJobIds[cachedId]) {
                        // Job was removed - do full re-render
                        renderJobsTable(data.jobs, data.has_filters)
                        updateJobsCache(data.jobs)
                        updatePagination()
                        return
                    }
                }

                // Update cache with new data
                updateJobsCache(data.jobs)

                // Update pagination if total changed
                if (totalChanged) {
                    updatePagination()
                }
            })
    }

    /**
     * Handle SSE/polling update data.
     * @param {Object} data - Update data with jobs array
     */
    function handleRealtimeUpdate(data) {
        if (!data || !data.jobs) {
            return
        }

        // Update total and pagination
        const totalChanged = totalJobs !== data.total
        totalJobs = data.total || 0

        // Check for changes and update
        const newJobIds = {}

        for (let i = 0; i < data.jobs.length; i++) {
            const job = data.jobs[i]
            newJobIds[job.id] = true

            if (hasJobChanged(job)) {
                // Try to update existing row
                if (!updateJobRow(job.id, job)) {
                    // Job not in current view - do full re-render
                    renderJobsTable(data.jobs, data.has_filters || false)
                    updateJobsCache(data.jobs)
                    updatePagination()
                    return
                }
            }
        }

        // Check for removed jobs
        for (const cachedId in cachedJobs) {
            if (!newJobIds[cachedId]) {
                renderJobsTable(data.jobs, data.has_filters || false)
                updateJobsCache(data.jobs)
                updatePagination()
                return
            }
        }

        // Update cache
        updateJobsCache(data.jobs)

        // Update pagination if total changed
        if (totalChanged) {
            updatePagination()
        }
    }

    /**
     * Initialize real-time updates (SSE with polling fallback).
     */
    function initPolling() {
        // Try SSE first if available
        if (typeof window.VPOSSE !== 'undefined') {
            // eslint-disable-next-line no-console
            console.log('[Jobs] Using SSE for real-time updates')

            sseClient = window.VPOSSE.createJobsSSE({
                onUpdate: function (data) {
                    handleRealtimeUpdate(data)
                },
                onStatusChange: function (status) {
                    if (typeof window.VPOPolling !== 'undefined') {
                        window.VPOPolling.setConnectionStatus(status)
                    }
                },
                fallbackFetchFn: function () {
                    return fetch('/api/jobs' + buildQueryString())
                        .then(function (response) {
                            if (!response.ok) {
                                throw new Error('Failed to fetch jobs: ' + response.status)
                            }
                            return response.json()
                        })
                }
            })

            sseClient.start()

            // Register cleanup
            if (typeof window.VPOPolling !== 'undefined') {
                window.VPOPolling.onCleanup(function () {
                    if (sseClient) {
                        sseClient.cleanup()
                        sseClient = null
                    }
                })
            }

            return
        }

        // Fall back to polling if SSE not available
        // eslint-disable-next-line no-console
        console.log('[Jobs] SSE not available, using polling')

        if (typeof window.VPOPolling === 'undefined') {
            console.warn('[Jobs] VPOPolling not available, live updates disabled')
            return
        }

        // Create polling instance
        pollingInstance = window.VPOPolling.create({
            fetchFn: fetchJobsForPolling,
            onStatusChange: function (_status) {
                // Connection status is handled by VPOPolling
            }
        })

        // Start polling
        pollingInstance.start()

        // Register cleanup
        window.VPOPolling.onCleanup(function () {
            if (pollingInstance) {
                pollingInstance.cleanup()
                pollingInstance = null
            }
        })
    }

    /**
     * Handle pagination - previous page.
     */
    function handlePrevPage() {
        if (currentOffset >= pageSize) {
            currentOffset -= pageSize
            fetchJobs()
        }
    }

    /**
     * Handle pagination - next page.
     */
    function handleNextPage() {
        if (currentOffset + pageSize < totalJobs) {
            currentOffset += pageSize
            fetchJobs()
        }
    }

    /**
     * Handle status filter change.
     * @param {string} status - New status filter value
     */
    function handleStatusFilter(status) {
        currentFilters.status = status
        currentOffset = 0
        fetchJobs()
    }

    /**
     * Handle type filter change.
     * @param {string} type - New type filter value
     */
    function handleTypeFilter(type) {
        currentFilters.type = type
        currentOffset = 0
        fetchJobs()
    }

    /**
     * Handle time filter change.
     * @param {string} since - New time filter value
     */
    function handleTimeFilter(since) {
        currentFilters.since = since
        currentOffset = 0
        fetchJobs()
    }

    /**
     * Handle search input change (debounced).
     * @param {string} value - Search input value
     */
    function handleSearchInput(value) {
        currentFilters.search = value.trim()
        currentOffset = 0
        updateSearchVisuals()
        fetchJobs()
    }

    /**
     * Debounce wrapper for search input.
     * @param {string} value - Search input value
     */
    function debouncedSearch(value) {
        if (debounceTimer) {
            clearTimeout(debounceTimer)
        }
        debounceTimer = setTimeout(function () {
            handleSearchInput(value)
        }, DEBOUNCE_DELAY)
    }

    /**
     * Handle sort column click.
     * @param {string} column - Column to sort by
     */
    function handleSortClick(column) {
        if (currentSort.column === column) {
            // Toggle direction
            currentSort.order = currentSort.order === 'asc' ? 'desc' : 'asc'
        } else {
            // New column, default to descending
            currentSort.column = column
            currentSort.order = 'desc'
        }
        currentOffset = 0
        updateSortIndicators()
        fetchJobs()
    }

    /**
     * Update visual feedback for search input.
     * Toggles filter-active class based on search state.
     */
    function updateSearchVisuals() {
        const searchInput = document.getElementById('filter-search')
        if (searchInput) {
            searchInput.classList.toggle('filter-active', Boolean(currentFilters.search))
        }
    }

    /**
     * Update sort indicators in table headers.
     */
    function updateSortIndicators() {
        const headers = document.querySelectorAll('.jobs-table th.sortable')
        headers.forEach(function (th) {
            const sortKey = th.getAttribute('data-sort-key')
            const indicator = th.querySelector('.sort-indicator')

            if (sortKey === currentSort.column) {
                th.classList.add('sorted')
                th.setAttribute('aria-sort', currentSort.order === 'asc' ? 'ascending' : 'descending')
                if (indicator) {
                    indicator.textContent = currentSort.order === 'asc' ? '\u25B2' : '\u25BC'
                }
            } else {
                th.classList.remove('sorted')
                th.setAttribute('aria-sort', 'none')
                if (indicator) {
                    indicator.textContent = ''
                }
            }
        })

        // Announce sort change to screen readers
        const sortStatus = document.getElementById('sort-status')
        if (sortStatus) {
            const columnHeader = document.querySelector('.jobs-table th[data-sort-key="' + currentSort.column + '"]')
            const columnName = columnHeader ? columnHeader.textContent.replace(/[\u25B2\u25BC]/g, '').trim() : currentSort.column
            sortStatus.textContent = 'Sorted by ' + columnName + ', ' + (currentSort.order === 'asc' ? 'ascending' : 'descending')
        }
    }

    /**
     * Setup event listeners for sortable column headers.
     */
    function setupSortListeners() {
        const headers = document.querySelectorAll('.jobs-table th.sortable')
        headers.forEach(function (th) {
            const sortKey = th.getAttribute('data-sort-key')

            // Click handler
            th.addEventListener('click', function () {
                handleSortClick(sortKey)
            })

            // Keyboard handler (Enter and Space)
            th.addEventListener('keydown', function (e) {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    handleSortClick(sortKey)
                }
            })
        })
    }

    // Event listeners for pagination
    if (prevBtnEl) {
        prevBtnEl.addEventListener('click', handlePrevPage)
    }
    if (nextBtnEl) {
        nextBtnEl.addEventListener('click', handleNextPage)
    }

    // Event listeners for filters (attached via JS instead of inline handlers)
    const statusFilterEl = document.getElementById('filter-status')
    const typeFilterEl = document.getElementById('filter-type')
    const timeFilterEl = document.getElementById('filter-time')
    const searchInputEl = document.getElementById('filter-search')

    if (statusFilterEl) {
        statusFilterEl.addEventListener('change', function (e) {
            handleStatusFilter(e.target.value)
        })
    }
    if (typeFilterEl) {
        typeFilterEl.addEventListener('change', function (e) {
            handleTypeFilter(e.target.value)
        })
    }
    if (timeFilterEl) {
        timeFilterEl.addEventListener('change', function (e) {
            handleTimeFilter(e.target.value)
        })
    }
    if (searchInputEl) {
        // Debounced input handler
        searchInputEl.addEventListener('input', function (e) {
            debouncedSearch(e.target.value)
        })

        // Immediate search on Enter key
        searchInputEl.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') {
                if (debounceTimer) {
                    clearTimeout(debounceTimer)
                }
                handleSearchInput(searchInputEl.value)
            }
        })
    }

    // Export functions for filter handlers (kept for backwards compatibility)
    window.jobsDashboard = {
        handleStatusFilter: handleStatusFilter,
        handleTypeFilter: handleTypeFilter,
        handleTimeFilter: handleTimeFilter,
        handleSearchInput: handleSearchInput,
        handleSortClick: handleSortClick
    }

    /**
     * Initialize the jobs dashboard.
     */
    /**
     * Show the loading state and hide other states.
     */
    function showLoading() {
        loadingEl.style.display = ''
        if (errorEl) errorEl.style.display = 'none'
        contentEl.style.display = 'none'
    }

    /**
     * Show the error state with a message.
     * @param {string} message - Error message to display
     */
    function showError(message) {
        loadingEl.style.display = 'none'
        if (errorEl) {
            errorEl.style.display = ''
            if (errorMessageEl) errorMessageEl.textContent = message || 'Failed to load jobs.'
        }
        contentEl.style.display = 'none'
    }

    /**
     * Show the main content and hide other states.
     */
    function showContent() {
        loadingEl.style.display = 'none'
        if (errorEl) errorEl.style.display = 'none'
        contentEl.style.display = ''
    }

    /**
     * Setup event delegation for clickable job rows.
     */
    function setupRowDelegation() {
        if (!tableBodyEl) return

        tableBodyEl.addEventListener('click', function (e) {
            const row = e.target.closest('.job-row-clickable')
            if (!row) return
            const jobId = row.getAttribute('data-job-id')
            if (jobId) {
                window.location.href = '/jobs/' + jobId
            }
        })

        tableBodyEl.addEventListener('keydown', function (e) {
            if (e.key !== 'Enter' && e.key !== ' ') return
            const row = e.target.closest('.job-row-clickable')
            if (!row) return
            e.preventDefault()
            const jobId = row.getAttribute('data-job-id')
            if (jobId) {
                window.location.href = '/jobs/' + jobId
            }
        })
    }

    function init() {
        // Prevent double initialization
        if (initialized) return
        initialized = true

        // Setup event delegation for clickable rows
        setupRowDelegation()

        // Setup retry button
        if (retryBtnEl) {
            retryBtnEl.addEventListener('click', function () {
                showLoading()
                fetchJobs()
            })
        }

        // Setup sortable column listeners
        setupSortListeners()

        // Initialize sort indicators (default: created_at desc)
        updateSortIndicators()

        // Initialize search visual state
        updateSearchVisuals()

        // Initial fetch
        fetchJobs()

        // Initialize polling after initial fetch
        setTimeout(function () {
            initPolling()
        }, 100)
    }

    // Initial fetch on page load
    document.addEventListener('DOMContentLoaded', init)

    // Also fetch immediately if DOM is already ready
    if (document.readyState !== 'loading') {
        init()
    }
})()
