/**
 * Job Detail Page JavaScript
 *
 * Handles relative timestamps, logs fetching/display, client-side enhancements,
 * and live polling updates (017-live-job-polling).
 */

(function () {
    'use strict'

    // Logs state
    let currentLogsOffset = 0
    let totalLogLines = 0
    let hasMoreLogs = false
    const logsPageSize = 500

    // Polling state (017-live-job-polling)
    var jobPollingInstance = null
    var logPollingInstance = null
    var cachedJobData = null
    var isTerminalState = false

    // Terminal states where polling should stop (T020)
    var TERMINAL_STATES = ['completed', 'failed', 'cancelled']

    // Shared utilities
    var escapeHtml = window.VPOUtils.escapeHtml
    var formatDuration = window.VPOUtils.formatDuration
    var _formatRelativeTime = window.VPOUtils.formatRelativeTime
    function formatRelativeTime(input) {
        return _formatRelativeTime(input, { emptyText: '-', dateFallbackDays: 7, capitalizeJustNow: false })
    }

    /**
     * Update all timestamp elements to show relative time.
     */
    function updateTimestamps() {
        const timeElements = document.querySelectorAll('time[data-timestamp]')

        timeElements.forEach(function (el) {
            const timestamp = el.getAttribute('data-timestamp')
            if (!timestamp) return

            try {
                const date = new Date(timestamp)
                if (isNaN(date.getTime())) return

                // Set relative time as text
                el.textContent = formatRelativeTime(date)

                // Set full timestamp as title for hover
                el.setAttribute('title', date.toLocaleString())
            } catch {
                // Keep original text on error
            }
        })
    }

    /**
     * Update duration elements to show formatted duration.
     */
    function updateDurations() {
        const durationElements = document.querySelectorAll('[data-duration]')

        durationElements.forEach(function (el) {
            const duration = parseInt(el.getAttribute('data-duration'), 10)
            if (!isNaN(duration)) {
                el.textContent = formatDuration(duration)
            }
        })
    }

    /**
     * Fetch logs from the API.
     * @param {string} jobId - Job UUID
     * @param {number} offset - Line offset
     * @param {boolean} append - Whether to append to existing logs
     */
    async function fetchLogs(jobId, offset, append) {
        const container = document.getElementById('logs-container')
        const pagination = document.getElementById('logs-pagination')
        const logsInfo = document.getElementById('logs-info')
        const loadMoreBtn = document.getElementById('load-more-logs')

        if (!container) return

        try {
            const response = await fetch('/api/jobs/' + jobId + '/logs?lines=' + logsPageSize + '&offset=' + offset)

            if (!response.ok) {
                throw new Error('Failed to fetch logs: ' + response.status)
            }

            const data = await response.json()

            totalLogLines = data.total_lines
            hasMoreLogs = data.has_more
            currentLogsOffset = offset + data.lines.length

            // Render logs
            if (data.lines.length === 0) {
                container.textContent = ''
                const emptyDiv = document.createElement('div')
                emptyDiv.className = 'logs-empty'
                emptyDiv.textContent = 'No logs available'
                container.appendChild(emptyDiv)
                if (pagination) pagination.style.display = 'none'
                return
            }

            // Build log content safely using textContent (defense-in-depth)
            const logContent = data.lines.join('\n')

            if (append && offset > 0) {
                // Append to existing content
                container.textContent += '\n' + logContent
            } else {
                // Replace content using textContent for safety
                container.textContent = logContent
            }

            // Update pagination
            if (pagination && totalLogLines > 0) {
                const showing = Math.min(currentLogsOffset, totalLogLines)
                logsInfo.textContent = 'Showing ' + showing + ' of ' + totalLogLines + ' lines'
                pagination.style.display = hasMoreLogs ? 'flex' : 'none'

                if (loadMoreBtn) {
                    loadMoreBtn.disabled = !hasMoreLogs
                }
            }

        } catch (error) {
            console.error('Error fetching logs:', error)
            container.textContent = ''
            const errorDiv = document.createElement('div')
            errorDiv.className = 'logs-error'
            errorDiv.textContent = 'Unable to load logs'
            container.appendChild(errorDiv)
        }
    }

    /**
     * Handle "Load More" button click.
     */
    function handleLoadMore() {
        const section = document.getElementById('job-logs-section')
        if (!section) return

        const jobId = section.getAttribute('data-job-id')
        if (!jobId) return

        fetchLogs(jobId, currentLogsOffset, true)
    }

    /**
     * Initialize logs section.
     */
    function initLogs() {
        const section = document.getElementById('job-logs-section')
        if (!section) return

        const jobId = section.getAttribute('data-job-id')
        if (!jobId) return

        // Initial fetch
        fetchLogs(jobId, 0, false)

        // Bind load more button
        const loadMoreBtn = document.getElementById('load-more-logs')
        if (loadMoreBtn) {
            loadMoreBtn.addEventListener('click', handleLoadMore)
        }
    }

    /**
     * Fetch scan errors from the API.
     * @param {string} jobId - Job UUID
     */
    async function fetchScanErrors(jobId) {
        const container = document.getElementById('errors-container')
        if (!container) return

        try {
            const response = await fetch('/api/jobs/' + jobId + '/errors')

            if (!response.ok) {
                throw new Error('Failed to fetch errors: ' + response.status)
            }

            const data = await response.json()

            // Clear loading state
            container.textContent = ''

            if (data.errors.length === 0) {
                const emptyDiv = document.createElement('div')
                emptyDiv.className = 'errors-empty'
                emptyDiv.textContent = 'No errors found'
                container.appendChild(emptyDiv)
                return
            }

            // Render error list
            const errorList = document.createElement('div')
            errorList.className = 'errors-list'

            data.errors.forEach(function (error) {
                const errorItem = document.createElement('div')
                errorItem.className = 'error-item'

                const errorFilename = document.createElement('div')
                errorFilename.className = 'error-filename'
                errorFilename.textContent = error.filename
                errorFilename.setAttribute('title', error.path)

                const errorMessage = document.createElement('div')
                errorMessage.className = 'error-message'
                errorMessage.textContent = error.error

                errorItem.appendChild(errorFilename)
                errorItem.appendChild(errorMessage)
                errorList.appendChild(errorItem)
            })

            container.appendChild(errorList)

        } catch (error) {
            console.error('Error fetching scan errors:', error)
            container.textContent = ''
            const errorDiv = document.createElement('div')
            errorDiv.className = 'errors-error'
            errorDiv.textContent = 'Unable to load error details'
            container.appendChild(errorDiv)
        }
    }

    /**
     * Initialize scan errors section.
     */
    function initScanErrors() {
        const section = document.getElementById('job-errors-section')
        if (!section) return

        const jobId = section.getAttribute('data-job-id')
        if (!jobId) return

        // Fetch errors
        fetchScanErrors(jobId)
    }

    // ==========================================================================
    // Polling Support (017-live-job-polling)
    // ==========================================================================

    /**
     * Get the job ID from the page.
     * @returns {string|null} Job UUID or null if not found
     */
    function getJobId() {
        // Try to get from logs section data attribute
        var logsSection = document.getElementById('job-logs-section')
        if (logsSection) {
            return logsSection.getAttribute('data-job-id')
        }

        // Try to get from errors section
        var errorsSection = document.getElementById('job-errors-section')
        if (errorsSection) {
            return errorsSection.getAttribute('data-job-id')
        }

        // Try to extract from URL
        var match = window.location.pathname.match(/\/jobs\/([a-f0-9-]+)/)
        if (match) {
            return match[1]
        }

        return null
    }

    /**
     * Check if job is in a terminal state (T020).
     * @param {string} status - Job status
     * @returns {boolean} True if terminal
     */
    function isTerminal(status) {
        return TERMINAL_STATES.indexOf(status) !== -1
    }

    /**
     * Create status badge HTML.
     * @param {string} status - Job status
     * @returns {string} HTML for status badge
     */
    function createStatusBadge(status) {
        var knownStatuses = ['queued', 'running', 'completed', 'failed', 'cancelled']
        var normalizedStatus = (status || 'unknown').toLowerCase()
        var statusClass = knownStatuses.indexOf(normalizedStatus) !== -1
            ? 'status-badge--' + normalizedStatus
            : 'status-badge--queued'
        var displayStatus = status || 'unknown'
        return '<span class="status-badge ' + statusClass + '">' + escapeHtml(displayStatus) + '</span>'
    }

    /**
     * Update job detail fields with new data (T019).
     * @param {Object} data - Job data from API
     */
    function updateJobDetailFields(data) {
        // Update status badge
        var statusContainer = document.querySelector('.job-detail-header .status-badge')
        if (statusContainer) {
            var parent = statusContainer.parentNode
            if (parent) {
                var newBadge = document.createElement('span')
                newBadge.innerHTML = createStatusBadge(data.status)
                parent.replaceChild(newBadge.firstChild, statusContainer)
            }
        }

        // Update progress bar if present
        var progressBar = document.querySelector('.job-detail-progress-bar')
        var progressText = document.querySelector('.job-detail-progress-text')
        if (progressBar && data.progress_percent !== null && data.progress_percent !== undefined) {
            progressBar.style.width = data.progress_percent + '%'
            if (progressText) {
                progressText.textContent = data.progress_percent + '%'
            }
        }

        // Update duration
        var durationEl = document.querySelector('[data-duration]')
        if (durationEl) {
            var duration = data.duration_seconds
            if (data.status === 'running' && data.created_at && duration === null) {
                var created = new Date(data.created_at)
                var now = new Date()
                duration = Math.floor((now - created) / 1000)
            }
            if (duration !== null) {
                durationEl.textContent = formatDuration(duration)
                durationEl.setAttribute('data-duration', duration)
            }
        }

        // Update completed_at timestamp if it changed
        if (data.completed_at && data.status !== 'running') {
            var completedEl = document.querySelector('time[data-field="completed_at"]')
            if (completedEl) {
                completedEl.setAttribute('data-timestamp', data.completed_at)
                var completedDate = new Date(data.completed_at)
                completedEl.textContent = formatRelativeTime(completedDate)
                completedEl.setAttribute('title', completedDate.toLocaleString())
            }
        }
    }

    /**
     * Fetch job detail for polling (T018).
     * @returns {Promise} Resolves when fetch is complete
     */
    function fetchJobDetailForPolling() {
        var jobId = getJobId()
        if (!jobId) {
            return Promise.reject(new Error('No job ID found'))
        }

        return fetch('/api/jobs/' + jobId)
            .then(function (response) {
                // Handle 404 gracefully (T024)
                if (response.status === 404) {
                    console.warn('[JobDetail] Job not found (may have been deleted)')
                    stopAllPolling()
                    showJobDeletedMessage()
                    return null
                }

                if (!response.ok) {
                    throw new Error('Failed to fetch job: ' + response.status)
                }
                return response.json()
            })
            .then(function (data) {
                if (!data) return

                // Check for changes
                if (hasJobDetailChanged(data)) {
                    updateJobDetailFields(data)
                    cachedJobData = data
                }

                // Check if job reached terminal state (T020)
                if (isTerminal(data.status) && !isTerminalState) {
                    isTerminalState = true
                    // eslint-disable-next-line no-console
                    console.log('[JobDetail] Job reached terminal state:', data.status)
                    // Stop polling after a short delay to catch final updates
                    setTimeout(function () {
                        stopAllPolling()
                    }, 2000)
                }
            })
    }

    /**
     * Check if job detail data has changed.
     * @param {Object} newData - New job data
     * @returns {boolean} True if changed
     */
    function hasJobDetailChanged(newData) {
        if (!cachedJobData) {
            return true
        }

        return cachedJobData.status !== newData.status ||
               cachedJobData.progress_percent !== newData.progress_percent ||
               cachedJobData.duration_seconds !== newData.duration_seconds ||
               cachedJobData.completed_at !== newData.completed_at ||
               cachedJobData.error_message !== newData.error_message
    }

    /**
     * Show message when job was deleted (T024).
     */
    function showJobDeletedMessage() {
        var header = document.querySelector('.job-detail-header')
        if (header) {
            var msg = document.createElement('div')
            msg.className = 'job-detail-deleted-notice'
            msg.style.cssText = 'background: #fee2e2; color: #991b1b; padding: 1rem; border-radius: 4px; margin-top: 1rem;'
            msg.textContent = 'This job no longer exists. It may have been deleted.'
            header.parentNode.insertBefore(msg, header.nextSibling)
        }
    }

    /**
     * Append new log lines incrementally (T023).
     * @param {Array} lines - New log lines
     */
    function appendNewLogLines(lines) {
        var container = document.getElementById('logs-container')
        if (!container || lines.length === 0) return

        // Check if container is showing empty message
        var emptyMsg = container.querySelector('.logs-empty')
        if (emptyMsg) {
            container.textContent = ''
        }

        // Append new lines
        var currentContent = container.textContent
        if (currentContent) {
            container.textContent = currentContent + '\n' + lines.join('\n')
        } else {
            container.textContent = lines.join('\n')
        }

        // Auto-scroll to bottom
        container.scrollTop = container.scrollHeight

        // Update logs info
        var logsInfo = document.getElementById('logs-info')
        if (logsInfo) {
            currentLogsOffset += lines.length
            totalLogLines += lines.length
            logsInfo.textContent = 'Showing ' + currentLogsOffset + ' of ' + totalLogLines + ' lines'
        }
    }

    /**
     * Fetch logs for polling (T022).
     * @returns {Promise} Resolves when fetch is complete
     */
    function fetchLogsForPolling() {
        var jobId = getJobId()
        if (!jobId) {
            return Promise.reject(new Error('No job ID found'))
        }

        // Only fetch new logs (from current offset)
        return fetch('/api/jobs/' + jobId + '/logs?lines=' + logsPageSize + '&offset=' + currentLogsOffset)
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('Failed to fetch logs: ' + response.status)
                }
                return response.json()
            })
            .then(function (data) {
                if (data.lines.length > 0) {
                    appendNewLogLines(data.lines)
                }
                totalLogLines = data.total_lines
                hasMoreLogs = data.has_more
            })
    }

    /**
     * Stop all polling instances.
     */
    function stopAllPolling() {
        if (jobPollingInstance) {
            jobPollingInstance.stop()
        }
        if (logPollingInstance) {
            logPollingInstance.stop()
        }
    }

    /**
     * Initialize polling for job detail page (T021).
     */
    function initPolling() {
        // Check if VPOPolling is available
        if (typeof window.VPOPolling === 'undefined') {
            console.warn('[JobDetail] VPOPolling not available, polling disabled')
            return
        }

        var jobId = getJobId()
        if (!jobId) {
            console.warn('[JobDetail] No job ID found, polling disabled')
            return
        }

        // Get config
        var config = window.VPOPolling.loadConfig()

        // Initialize cached data from page (get initial status)
        var initialStatus = document.querySelector('.job-detail-header .status-badge')
        if (initialStatus) {
            var statusText = initialStatus.textContent.trim().toLowerCase()
            if (isTerminal(statusText)) {
                isTerminalState = true
                // eslint-disable-next-line no-console
                console.log('[JobDetail] Job already in terminal state, polling not started')
                return
            }
        }

        // Create job status polling instance
        jobPollingInstance = window.VPOPolling.create({
            fetchFn: fetchJobDetailForPolling,
            interval: config.interval
        })

        // Create log polling instance with longer interval (T022)
        logPollingInstance = window.VPOPolling.create({
            fetchFn: fetchLogsForPolling,
            interval: config.logInterval
        })

        // Start polling
        jobPollingInstance.start()
        logPollingInstance.start()

        // Register cleanup
        window.VPOPolling.onCleanup(function () {
            stopAllPolling()
            jobPollingInstance = null
            logPollingInstance = null
        })
    }

    /**
     * Initialize the job detail page.
     */
    function init() {
        // Set initial progress bar width from data attribute (CSP disallows inline styles)
        var progressBar = document.querySelector('.job-detail-progress-bar[data-progress]')
        if (progressBar) {
            progressBar.style.width = progressBar.getAttribute('data-progress') + '%'
        }

        // Update timestamps to relative format
        updateTimestamps()

        // Format durations
        updateDurations()

        // Initialize logs section
        initLogs()

        // Initialize scan errors section
        initScanErrors()

        // Copy job ID button
        var copyBtn = document.getElementById('copy-job-id')
        if (copyBtn) {
            copyBtn.addEventListener('click', function () {
                var value = copyBtn.getAttribute('data-copy-value')
                window.VPOUtils.copyToClipboard(value, copyBtn)
            })
        }

        // Update timestamps periodically (every minute)
        setInterval(updateTimestamps, 60000)

        // Initialize polling after initial content load
        setTimeout(function () {
            initPolling()
        }, 100)
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init)
    } else {
        init()
    }
})()
