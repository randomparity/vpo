/**
 * Library Dashboard JavaScript
 *
 * Handles fetching files from the API, rendering the table,
 * filtering, pagination, and display formatting (018-library-list-view).
 */

(function() {
    'use strict';

    // State
    let currentOffset = 0;
    const pageSize = 50;
    let currentFilters = {
        status: ''
    };
    let totalFiles = 0;

    // DOM elements
    const loadingEl = document.getElementById('library-loading');
    const errorEl = document.getElementById('library-error');
    const errorMessageEl = document.getElementById('library-error-message');
    const retryBtnEl = document.getElementById('library-retry-btn');
    const contentEl = document.getElementById('library-content');
    const tableBodyEl = document.getElementById('library-table-body');
    const tableEl = document.getElementById('library-table');
    const emptyEl = document.getElementById('library-empty');
    const emptyTitleEl = document.getElementById('library-empty-title');
    const emptyHintEl = document.getElementById('library-empty-hint');
    const paginationEl = document.getElementById('library-pagination');
    const paginationInfoEl = document.getElementById('library-pagination-info');
    const prevBtnEl = document.getElementById('library-prev-btn');
    const nextBtnEl = document.getElementById('library-next-btn');

    /**
     * Format an ISO timestamp to a relative time string.
     * @param {string} isoString - ISO 8601 timestamp
     * @returns {string} Relative time (e.g., "2 hours ago")
     */
    function formatRelativeTime(isoString) {
        if (!isoString) {
            return '\u2014';
        }

        try {
            const date = new Date(isoString);
            const now = new Date();
            const diffMs = now - date;
            const diffSec = Math.floor(diffMs / 1000);
            const diffMin = Math.floor(diffSec / 60);
            const diffHour = Math.floor(diffMin / 60);
            const diffDay = Math.floor(diffHour / 24);

            if (diffDay > 30) {
                // Fall back to date format for older items
                return date.toLocaleDateString(undefined, {
                    month: 'short',
                    day: 'numeric',
                    year: diffDay > 365 ? 'numeric' : undefined
                });
            }
            if (diffDay > 0) {
                return diffDay + ' day' + (diffDay > 1 ? 's' : '') + ' ago';
            }
            if (diffHour > 0) {
                return diffHour + ' hour' + (diffHour > 1 ? 's' : '') + ' ago';
            }
            if (diffMin > 0) {
                return diffMin + ' minute' + (diffMin > 1 ? 's' : '') + ' ago';
            }
            return 'Just now';
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
            return path || '\u2014';
        }

        // Keep the last part of the path (filename)
        const parts = path.split('/');
        const filename = parts[parts.length - 1];

        if (filename.length >= maxLength - 3) {
            return '...' + filename.substring(filename.length - maxLength + 3);
        }

        const remaining = maxLength - filename.length - 4; // 4 for ".../"
        const prefix = path.substring(0, remaining);

        return prefix + '.../' + filename;
    }

    /**
     * Create a scan status badge element.
     * @param {string} status - Scan status (ok, error)
     * @param {string|null} scanError - Error message if status is error
     * @returns {string} HTML string for status badge
     */
    function createScanStatusBadge(status, scanError) {
        const normalizedStatus = (status || 'ok').toLowerCase();

        if (normalizedStatus === 'error') {
            const title = scanError ? ' title="' + escapeHtml(scanError) + '"' : '';
            return '<span class="status-badge status-badge--failed"' + title + '>' +
                '<span class="scan-error-icon" aria-hidden="true">&#9888;</span> error</span>';
        }

        return '<span class="status-badge status-badge--completed">' + escapeHtml(status || 'ok') + '</span>';
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
     * Render a single file row.
     * @param {Object} file - File data from API
     * @returns {string} HTML string for table row
     */
    function renderFileRow(file) {
        const truncatedFilename = truncatePath(file.filename, 50);
        const hasFullPath = file.path && file.path.length > 50;
        const title = file.title || '\u2014';
        const resolution = file.resolution || '\u2014';
        const audioLanguages = file.audio_languages || '\u2014';
        const scannedAt = formatRelativeTime(file.scanned_at);
        // Policy column: always show em-dash (policy tracking out of scope)
        const policy = '\u2014';

        // Add error class for rows with scan errors
        const rowClass = file.scan_status === 'error' ? ' class="library-row-error"' : '';

        return '<tr' + rowClass + ' data-file-id="' + escapeHtml(String(file.id)) + '">' +
            '<td class="library-filename"' + (hasFullPath ? ' title="' + escapeHtml(file.path) + '"' : '') + '>' +
            escapeHtml(truncatedFilename) +
            (file.scan_status === 'error' ? ' ' + createScanStatusBadge(file.scan_status, file.scan_error) : '') +
            '</td>' +
            '<td class="library-title">' + escapeHtml(title) + '</td>' +
            '<td class="library-resolution">' + escapeHtml(resolution) + '</td>' +
            '<td class="library-audio">' + escapeHtml(audioLanguages) + '</td>' +
            '<td class="library-scanned">' + escapeHtml(scannedAt) + '</td>' +
            '<td class="library-policy">' + escapeHtml(policy) + '</td>' +
            '</tr>';
    }

    /**
     * Render the library table.
     * @param {Array} files - Array of file objects
     * @param {boolean} hasFilters - Whether any filters are active
     */
    function renderLibraryTable(files, hasFilters) {
        if (files.length === 0) {
            tableEl.style.display = 'none';
            emptyEl.style.display = 'block';

            if (hasFilters) {
                emptyTitleEl.textContent = 'No matching files';
                emptyHintEl.innerHTML = 'Try adjusting your filters or clear them to see all files.';
            } else {
                emptyTitleEl.textContent = 'No files in library';
                emptyHintEl.innerHTML = 'Scan a directory to add files to your library using the CLI:<br>' +
                    '<code>vpo scan /path/to/videos</code>';
            }
            return;
        }

        tableEl.style.display = 'table';
        emptyEl.style.display = 'none';

        const html = files.map(renderFileRow).join('');
        tableBodyEl.innerHTML = html;
    }

    /**
     * Update pagination controls.
     */
    function updatePagination() {
        if (totalFiles <= pageSize) {
            paginationEl.style.display = 'none';
            return;
        }

        paginationEl.style.display = 'flex';

        const start = currentOffset + 1;
        const end = Math.min(currentOffset + pageSize, totalFiles);
        paginationInfoEl.textContent = 'Showing ' + start + '-' + end + ' of ' + totalFiles + ' files';

        prevBtnEl.disabled = currentOffset === 0;
        nextBtnEl.disabled = currentOffset + pageSize >= totalFiles;
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

        params.set('limit', pageSize.toString());
        params.set('offset', currentOffset.toString());

        return '?' + params.toString();
    }

    /**
     * Show loading state.
     */
    function showLoading() {
        loadingEl.style.display = 'block';
        errorEl.style.display = 'none';
        contentEl.style.display = 'none';
    }

    /**
     * Show error state.
     * @param {string} message - Error message to display
     */
    function showError(message) {
        loadingEl.style.display = 'none';
        errorEl.style.display = 'block';
        contentEl.style.display = 'none';
        errorMessageEl.textContent = message || 'Failed to load library files.';
    }

    /**
     * Show content state.
     */
    function showContent() {
        loadingEl.style.display = 'none';
        errorEl.style.display = 'none';
        contentEl.style.display = 'block';
    }

    /**
     * Fetch library files from the API and render them.
     */
    async function fetchLibrary() {
        try {
            const response = await fetch('/api/library' + buildQueryString());

            if (!response.ok) {
                throw new Error('Failed to fetch library: ' + response.status);
            }

            const data = await response.json();

            totalFiles = data.total;
            renderLibraryTable(data.files, data.has_filters);
            updatePagination();

            // Show content
            showContent();

        } catch (error) {
            console.error('Error fetching library:', error);
            showError('Error loading library. Please refresh the page or try again.');
        }
    }

    /**
     * Handle pagination - previous page.
     */
    function handlePrevPage() {
        if (currentOffset >= pageSize) {
            currentOffset -= pageSize;
            showLoading();
            fetchLibrary();
        }
    }

    /**
     * Handle pagination - next page.
     */
    function handleNextPage() {
        if (currentOffset + pageSize < totalFiles) {
            currentOffset += pageSize;
            showLoading();
            fetchLibrary();
        }
    }

    /**
     * Handle status filter change.
     * @param {string} status - New status filter value
     */
    function handleStatusFilter(status) {
        currentFilters.status = status;
        currentOffset = 0;
        showLoading();
        fetchLibrary();
    }

    // Event listeners for pagination
    if (prevBtnEl) {
        prevBtnEl.addEventListener('click', handlePrevPage);
    }
    if (nextBtnEl) {
        nextBtnEl.addEventListener('click', handleNextPage);
    }

    // Event listener for retry button
    if (retryBtnEl) {
        retryBtnEl.addEventListener('click', function() {
            showLoading();
            fetchLibrary();
        });
    }

    // Event listeners for filters
    const statusFilterEl = document.getElementById('filter-status');

    if (statusFilterEl) {
        statusFilterEl.addEventListener('change', function(e) {
            handleStatusFilter(e.target.value);
        });
    }

    // Export functions for external access if needed
    window.libraryDashboard = {
        handleStatusFilter: handleStatusFilter,
        refresh: fetchLibrary
    };

    /**
     * Initialize the library dashboard.
     */
    function init() {
        // Initial fetch
        fetchLibrary();
    }

    // Initial fetch on page load
    document.addEventListener('DOMContentLoaded', init);

    // Also fetch immediately if DOM is already ready
    if (document.readyState !== 'loading') {
        init();
    }
})();
