/**
 * Jobs Dashboard JavaScript
 *
 * Handles fetching jobs from the API, rendering the table,
 * filtering, pagination, and live polling updates (017-live-job-polling).
 */

(function () {
    'use strict'

    // State
    let currentOffset = 0
    const pageSize = 50
    let currentFilters = {
        status: '',
        type: '',
        since: ''
    }
    let totalJobs = 0

    // Cached job data for comparison (T013)
    var cachedJobs = {}

    // Polling instance (T014)
    var pollingInstance = null

    // DOM elements
    const loadingEl = document.getElementById('jobs-loading')
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

    /**
     * Format a duration in seconds to a human-readable string.
     * @param {number|null} seconds - Duration in seconds
     * @returns {string} Formatted duration
     */
    function formatDuration(seconds) {
        if (seconds === null || seconds === undefined) {
            return '-'
        }

        if (seconds < 60) {
            return seconds + 's'
        }

        const minutes = Math.floor(seconds / 60)
        const remainingSeconds = seconds % 60

        if (minutes < 60) {
            return minutes + 'm ' + remainingSeconds + 's'
        }

        const hours = Math.floor(minutes / 60)
        const remainingMinutes = minutes % 60

        return hours + 'h ' + remainingMinutes + 'm'
    }

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
        var parts = path.split('/')
        return parts[parts.length - 1] || ''
    }

    /**
     * Truncate a filename for display, preserving start and extension.
     * If truncation is needed, shows: beginning…extension
     * Uses single ellipsis character (U+2026).
     * @param {string} filename - Filename to truncate
     * @param {number} maxLength - Maximum display length
     * @returns {string} Truncated filename
     */
    function truncateFilename(filename, maxLength) {
        if (!filename || filename.length <= maxLength) {
            return filename || '-'
        }

        // Find extension (last dot)
        var dotIndex = filename.lastIndexOf('.')
        var base, extension

        if (dotIndex > 0) {
            extension = filename.substring(dotIndex)  // includes the dot
            base = filename.substring(0, dotIndex)
        } else {
            extension = ''
            base = filename
        }

        // Calculate space for base (1 char for ellipsis)
        var availableForBase = maxLength - extension.length - 1

        // Edge case: extension too long, just truncate everything
        if (availableForBase < 1) {
            return filename.substring(0, maxLength - 1) + '\u2026'
        }

        return base.substring(0, availableForBase) + '\u2026' + extension
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
        var status = job.status
        var percent = job.progress_percent

        // For completed/failed/cancelled jobs, show 100% or appropriate state
        if (status === 'completed') {
            return '<div class="job-progress">' +
                '<div class="job-progress-track">' +
                '<div class="job-progress-bar job-progress-bar--completed" style="width: 100%"></div>' +
                '</div>' +
                '<span class="job-progress-text">100%</span>' +
                '</div>'
        }

        if (status === 'failed' || status === 'cancelled') {
            var barClass = status === 'failed' ? 'job-progress-bar--failed' : ''
            var displayPercent = percent !== null && percent !== undefined ? percent : 0
            return '<div class="job-progress">' +
                '<div class="job-progress-track">' +
                '<div class="job-progress-bar ' + barClass + '" style="width: ' + displayPercent + '%"></div>' +
                '</div>' +
                '<span class="job-progress-text">' + displayPercent + '%</span>' +
                '</div>'
        }

        // For queued jobs, show empty progress
        if (status === 'queued') {
            return '<div class="job-progress">' +
                '<div class="job-progress-track">' +
                '<div class="job-progress-bar" style="width: 0%"></div>' +
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
            '<div class="job-progress-bar" style="width: ' + percent + '%"></div>' +
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
        return '<tr class="job-row-clickable" data-job-id="' + escapeHtml(job.id) + '" onclick="window.location.href=\'/jobs/' + escapeHtml(job.id) + '\'" style="cursor: pointer;">' +
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
     * Escape HTML to prevent XSS.
     * @param {string} str - String to escape
     * @returns {string} Escaped string
     */
    function escapeHtml(str) {
        if (!str) return ''
        const div = document.createElement('div')
        div.textContent = str
        return div.innerHTML
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
     * Build query string from current filters.
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
            loadingEl.style.display = 'none'
            contentEl.style.display = 'block'

        } catch (error) {
            console.error('Error fetching jobs:', error)
            // Use textContent to prevent XSS in error display
            loadingEl.textContent = 'Error loading jobs. Please refresh the page.'
            loadingEl.style.color = 'var(--color-error)'
        }
    }

    // ==========================================================================
    // Polling Support (017-live-job-polling)
    // ==========================================================================

    /**
     * Update the jobs cache with new data (T013).
     * @param {Array} jobs - Array of job objects
     */
    function updateJobsCache(jobs) {
        cachedJobs = {}
        for (var i = 0; i < jobs.length; i++) {
            cachedJobs[jobs[i].id] = jobs[i]
        }
    }

    /**
     * Check if a job has changed compared to cached data (T013).
     * @param {Object} newJob - New job data
     * @returns {boolean} True if job has changed
     */
    function hasJobChanged(newJob) {
        var cached = cachedJobs[newJob.id]
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
        var row = tableBodyEl.querySelector('tr[data-job-id="' + jobId + '"]')
        if (!row) {
            return false // Row not found
        }

        // Calculate duration for running jobs
        var duration = newData.duration_seconds
        if (newData.status === 'running' && newData.created_at && duration === null) {
            var created = new Date(newData.created_at)
            var now = new Date()
            duration = Math.floor((now - created) / 1000)
        }

        // Update status cell
        var statusCell = row.querySelector('.job-status')
        if (statusCell) {
            statusCell.innerHTML = createStatusBadge(newData.status)
        }

        // Update progress cell (T025)
        var progressCell = row.querySelector('.job-progress-cell')
        if (progressCell) {
            progressCell.innerHTML = createProgressBar(newData)
        }

        // Update duration cell
        var durationCell = row.querySelector('.job-duration')
        if (durationCell) {
            durationCell.textContent = formatDuration(duration)
        }

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
                var totalChanged = totalJobs !== data.total
                totalJobs = data.total

                // Check for changes and update (T012)
                var _hasChanges = false
                var newJobIds = {}

                for (var i = 0; i < data.jobs.length; i++) {
                    var job = data.jobs[i]
                    newJobIds[job.id] = true

                    if (hasJobChanged(job)) {
                        _hasChanges = true
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
                for (var cachedId in cachedJobs) {
                    if (!newJobIds[cachedId]) {
                        // Job was removed - do full re-render
                        _hasChanges = true
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
     * Initialize polling for jobs dashboard (T014, T017).
     */
    function initPolling() {
        // Check if VPOPolling is available
        if (typeof window.VPOPolling === 'undefined') {
            console.warn('[Jobs] VPOPolling not available, polling disabled')
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

    // Export functions for filter handlers (kept for backwards compatibility)
    window.jobsDashboard = {
        handleStatusFilter: handleStatusFilter,
        handleTypeFilter: handleTypeFilter,
        handleTimeFilter: handleTimeFilter
    }

    /**
     * Initialize the jobs dashboard.
     */
    function init() {
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
