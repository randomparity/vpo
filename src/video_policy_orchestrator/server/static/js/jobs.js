/**
 * Jobs Dashboard JavaScript
 *
 * Handles fetching jobs from the API, rendering the table,
 * filtering, and pagination.
 */

(function() {
    'use strict';

    // State
    let currentOffset = 0;
    const pageSize = 50;
    let currentFilters = {
        status: '',
        type: '',
        since: ''
    };
    let totalJobs = 0;

    // DOM elements
    const loadingEl = document.getElementById('jobs-loading');
    const contentEl = document.getElementById('jobs-content');
    const tableBodyEl = document.getElementById('jobs-table-body');
    const tableEl = document.getElementById('jobs-table');
    const emptyEl = document.getElementById('jobs-empty');
    const emptyTitleEl = document.getElementById('jobs-empty-title');
    const emptyHintEl = document.getElementById('jobs-empty-hint');
    const paginationEl = document.getElementById('jobs-pagination');
    const paginationInfoEl = document.getElementById('jobs-pagination-info');
    const prevBtnEl = document.getElementById('jobs-prev-btn');
    const nextBtnEl = document.getElementById('jobs-next-btn');

    /**
     * Format a duration in seconds to a human-readable string.
     * @param {number|null} seconds - Duration in seconds
     * @returns {string} Formatted duration
     */
    function formatDuration(seconds) {
        if (seconds === null || seconds === undefined) {
            return '-';
        }

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
     * Format an ISO timestamp to a localized date/time string.
     * @param {string} isoString - ISO 8601 timestamp
     * @returns {string} Formatted date/time
     */
    function formatDateTime(isoString) {
        if (!isoString) {
            return '-';
        }

        try {
            const date = new Date(isoString);
            return date.toLocaleString(undefined, {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch (e) {
            return isoString;
        }
    }

    /**
     * Truncate a path for display, keeping the filename visible.
     * @param {string} path - Full file path
     * @param {number} maxLength - Maximum display length
     * @returns {string} Truncated path
     */
    function truncatePath(path, maxLength) {
        if (!path || path.length <= maxLength) {
            return path || '-';
        }

        // Keep the last part of the path (filename)
        const parts = path.split('/');
        const filename = parts[parts.length - 1];

        if (filename.length >= maxLength - 3) {
            return '...' + filename.substring(filename.length - maxLength + 3);
        }

        const remaining = maxLength - filename.length - 4; // 4 for ".../""
        const prefix = path.substring(0, remaining);

        return prefix + '.../' + filename;
    }

    /**
     * Create a status badge element.
     * @param {string} status - Job status
     * @returns {string} HTML string for status badge
     */
    function createStatusBadge(status) {
        const statusClass = 'status-badge--' + status;
        return '<span class="status-badge ' + statusClass + '">' + status + '</span>';
    }

    /**
     * Create a type badge element.
     * @param {string} type - Job type
     * @returns {string} HTML string for type badge
     */
    function createTypeBadge(type) {
        return '<span class="type-badge">' + type + '</span>';
    }

    /**
     * Render a single job row.
     * @param {Object} job - Job data from API
     * @returns {string} HTML string for table row
     */
    function renderJobRow(job) {
        const shortId = job.id.substring(0, 8);
        const truncatedPath = truncatePath(job.file_path, 50);
        const hasFullPath = job.file_path && job.file_path.length > 50;

        // Calculate duration for running jobs
        let duration = job.duration_seconds;
        if (job.status === 'running' && job.created_at && duration === null) {
            const created = new Date(job.created_at);
            const now = new Date();
            duration = Math.floor((now - created) / 1000);
        }

        return '<tr>' +
            '<td class="job-id" title="' + job.id + '">' + shortId + '</td>' +
            '<td>' + createTypeBadge(job.job_type) + '</td>' +
            '<td>' + createStatusBadge(job.status) + '</td>' +
            '<td class="job-path"' + (hasFullPath ? ' title="' + escapeHtml(job.file_path) + '"' : '') + '>' + escapeHtml(truncatedPath) + '</td>' +
            '<td>' + formatDateTime(job.created_at) + '</td>' +
            '<td>' + formatDuration(duration) + '</td>' +
            '</tr>';
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
     * Render the jobs table.
     * @param {Array} jobs - Array of job objects
     * @param {boolean} hasFilters - Whether any filters are active
     */
    function renderJobsTable(jobs, hasFilters) {
        if (jobs.length === 0) {
            tableEl.style.display = 'none';
            emptyEl.style.display = 'block';

            if (hasFilters) {
                emptyTitleEl.textContent = 'No matching jobs';
                emptyHintEl.textContent = 'Try adjusting your filters or clear them to see all jobs.';
            } else {
                emptyTitleEl.textContent = 'No jobs found';
                emptyHintEl.textContent = 'Jobs will appear here when you run scan, apply, or transcode operations.';
            }
            return;
        }

        tableEl.style.display = 'table';
        emptyEl.style.display = 'none';

        const html = jobs.map(renderJobRow).join('');
        tableBodyEl.innerHTML = html;
    }

    /**
     * Update pagination controls.
     */
    function updatePagination() {
        if (totalJobs <= pageSize) {
            paginationEl.style.display = 'none';
            return;
        }

        paginationEl.style.display = 'flex';

        const start = currentOffset + 1;
        const end = Math.min(currentOffset + pageSize, totalJobs);
        paginationInfoEl.textContent = 'Showing ' + start + '-' + end + ' of ' + totalJobs + ' jobs';

        prevBtnEl.disabled = currentOffset === 0;
        nextBtnEl.disabled = currentOffset + pageSize >= totalJobs;
    }

    /**
     * Build query string from current filters.
     * @returns {string} Query string (including leading ?)
     */
    function buildQueryString() {
        const params = new URLSearchParams();

        if (currentFilters.status) {
            params.set('status', currentFilters.status);
        }
        if (currentFilters.type) {
            params.set('type', currentFilters.type);
        }
        if (currentFilters.since) {
            params.set('since', currentFilters.since);
        }

        params.set('limit', pageSize.toString());
        params.set('offset', currentOffset.toString());

        return '?' + params.toString();
    }

    /**
     * Fetch jobs from the API and render them.
     */
    async function fetchJobs() {
        try {
            const response = await fetch('/api/jobs' + buildQueryString());

            if (!response.ok) {
                throw new Error('Failed to fetch jobs: ' + response.status);
            }

            const data = await response.json();

            totalJobs = data.total;
            renderJobsTable(data.jobs, data.has_filters);
            updatePagination();

            // Show content, hide loading
            loadingEl.style.display = 'none';
            contentEl.style.display = 'block';

        } catch (error) {
            console.error('Error fetching jobs:', error);
            loadingEl.innerHTML = '<p style="color: var(--color-error);">Error loading jobs. Please refresh the page.</p>';
        }
    }

    /**
     * Handle pagination - previous page.
     */
    function handlePrevPage() {
        if (currentOffset >= pageSize) {
            currentOffset -= pageSize;
            fetchJobs();
        }
    }

    /**
     * Handle pagination - next page.
     */
    function handleNextPage() {
        if (currentOffset + pageSize < totalJobs) {
            currentOffset += pageSize;
            fetchJobs();
        }
    }

    /**
     * Handle status filter change.
     * @param {string} status - New status filter value
     */
    function handleStatusFilter(status) {
        currentFilters.status = status;
        currentOffset = 0;
        fetchJobs();
    }

    /**
     * Handle type filter change.
     * @param {string} type - New type filter value
     */
    function handleTypeFilter(type) {
        currentFilters.type = type;
        currentOffset = 0;
        fetchJobs();
    }

    /**
     * Handle time filter change.
     * @param {string} since - New time filter value
     */
    function handleTimeFilter(since) {
        currentFilters.since = since;
        currentOffset = 0;
        fetchJobs();
    }

    // Event listeners
    if (prevBtnEl) {
        prevBtnEl.addEventListener('click', handlePrevPage);
    }
    if (nextBtnEl) {
        nextBtnEl.addEventListener('click', handleNextPage);
    }

    // Export functions for filter handlers
    window.jobsDashboard = {
        handleStatusFilter: handleStatusFilter,
        handleTypeFilter: handleTypeFilter,
        handleTimeFilter: handleTimeFilter
    };

    // Initial fetch on page load
    document.addEventListener('DOMContentLoaded', function() {
        fetchJobs();
    });

    // Also fetch immediately if DOM is already ready
    if (document.readyState !== 'loading') {
        fetchJobs();
    }
})();
