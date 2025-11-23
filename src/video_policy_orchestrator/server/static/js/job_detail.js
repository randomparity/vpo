/**
 * Job Detail Page JavaScript
 *
 * Handles relative timestamps, logs fetching/display, and client-side enhancements.
 */

(function() {
    'use strict';

    // Logs state
    let currentLogsOffset = 0;
    let totalLogLines = 0;
    let hasMoreLogs = false;
    const logsPageSize = 500;

    /**
     * Format a duration in seconds to a human-readable string.
     * @param {number} seconds - Duration in seconds
     * @returns {string} Formatted duration
     */
    function formatDuration(seconds) {
        if (seconds === null || seconds === undefined || isNaN(seconds)) {
            return '—';
        }

        seconds = Math.floor(seconds);

        if (seconds < 60) {
            return seconds + 's';
        }

        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;

        if (minutes < 60) {
            return minutes + 'm ' + remainingSeconds + 's';
        }

        const hours = Math.floor(minutes / 60);
        const remainingMinutes = minutes % 60;

        return hours + 'h ' + remainingMinutes + 'm';
    }

    /**
     * Format a timestamp as relative time (e.g., "2 hours ago").
     * @param {Date} date - Date to format
     * @returns {string} Relative time string
     */
    function formatRelativeTime(date) {
        const now = new Date();
        const diffMs = now - date;
        const diffSec = Math.floor(diffMs / 1000);
        const diffMin = Math.floor(diffSec / 60);
        const diffHour = Math.floor(diffMin / 60);
        const diffDay = Math.floor(diffHour / 24);

        if (diffSec < 60) {
            return 'just now';
        } else if (diffMin < 60) {
            return diffMin + ' minute' + (diffMin !== 1 ? 's' : '') + ' ago';
        } else if (diffHour < 24) {
            return diffHour + ' hour' + (diffHour !== 1 ? 's' : '') + ' ago';
        } else if (diffDay < 7) {
            return diffDay + ' day' + (diffDay !== 1 ? 's' : '') + ' ago';
        } else {
            // Fall back to localized date for older timestamps
            return date.toLocaleString(undefined, {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        }
    }

    /**
     * Update all timestamp elements to show relative time.
     */
    function updateTimestamps() {
        const timeElements = document.querySelectorAll('time[data-timestamp]');

        timeElements.forEach(function(el) {
            const timestamp = el.getAttribute('data-timestamp');
            if (!timestamp) return;

            try {
                const date = new Date(timestamp);
                if (isNaN(date.getTime())) return;

                // Set relative time as text
                el.textContent = formatRelativeTime(date);

                // Set full timestamp as title for hover
                el.setAttribute('title', date.toLocaleString());
            } catch (e) {
                // Keep original text on error
            }
        });
    }

    /**
     * Update duration elements to show formatted duration.
     */
    function updateDurations() {
        const durationElements = document.querySelectorAll('[data-duration]');

        durationElements.forEach(function(el) {
            const duration = parseInt(el.getAttribute('data-duration'), 10);
            if (!isNaN(duration)) {
                el.textContent = formatDuration(duration);
            }
        });
    }

    /**
     * Escape HTML to prevent XSS.
     * @param {string} str - String to escape
     * @returns {string} Escaped string
     */
    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    /**
     * Fetch logs from the API.
     * @param {string} jobId - Job UUID
     * @param {number} offset - Line offset
     * @param {boolean} append - Whether to append to existing logs
     */
    async function fetchLogs(jobId, offset, append) {
        const container = document.getElementById('logs-container');
        const pagination = document.getElementById('logs-pagination');
        const logsInfo = document.getElementById('logs-info');
        const loadMoreBtn = document.getElementById('load-more-logs');

        if (!container) return;

        try {
            const response = await fetch('/api/jobs/' + jobId + '/logs?lines=' + logsPageSize + '&offset=' + offset);

            if (!response.ok) {
                throw new Error('Failed to fetch logs: ' + response.status);
            }

            const data = await response.json();

            totalLogLines = data.total_lines;
            hasMoreLogs = data.has_more;
            currentLogsOffset = offset + data.lines.length;

            // Render logs
            if (data.lines.length === 0) {
                container.textContent = '';
                const emptyDiv = document.createElement('div');
                emptyDiv.className = 'logs-empty';
                emptyDiv.textContent = 'No logs available';
                container.appendChild(emptyDiv);
                if (pagination) pagination.style.display = 'none';
                return;
            }

            // Build log content safely using textContent (defense-in-depth)
            const logContent = data.lines.join('\n');

            if (append && offset > 0) {
                // Append to existing content
                container.textContent += '\n' + logContent;
            } else {
                // Replace content using textContent for safety
                container.textContent = logContent;
            }

            // Update pagination
            if (pagination && totalLogLines > 0) {
                const showing = Math.min(currentLogsOffset, totalLogLines);
                logsInfo.textContent = 'Showing ' + showing + ' of ' + totalLogLines + ' lines';
                pagination.style.display = hasMoreLogs ? 'flex' : 'none';

                if (loadMoreBtn) {
                    loadMoreBtn.disabled = !hasMoreLogs;
                }
            }

        } catch (error) {
            console.error('Error fetching logs:', error);
            container.textContent = '';
            const errorDiv = document.createElement('div');
            errorDiv.className = 'logs-error';
            errorDiv.textContent = 'Unable to load logs';
            container.appendChild(errorDiv);
        }
    }

    /**
     * Handle "Load More" button click.
     */
    function handleLoadMore() {
        const section = document.getElementById('job-logs-section');
        if (!section) return;

        const jobId = section.getAttribute('data-job-id');
        if (!jobId) return;

        fetchLogs(jobId, currentLogsOffset, true);
    }

    /**
     * Initialize logs section.
     */
    function initLogs() {
        const section = document.getElementById('job-logs-section');
        if (!section) return;

        const jobId = section.getAttribute('data-job-id');
        if (!jobId) return;

        // Initial fetch
        fetchLogs(jobId, 0, false);

        // Bind load more button
        const loadMoreBtn = document.getElementById('load-more-logs');
        if (loadMoreBtn) {
            loadMoreBtn.addEventListener('click', handleLoadMore);
        }
    }

    /**
     * Initialize the job detail page.
     */
    function init() {
        // Update timestamps to relative format
        updateTimestamps();

        // Format durations
        updateDurations();

        // Initialize logs section
        initLogs();

        // Update timestamps periodically (every minute)
        setInterval(updateTimestamps, 60000);
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
