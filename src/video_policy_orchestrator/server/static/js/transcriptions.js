/**
 * Transcriptions Dashboard JavaScript
 *
 * Handles fetching files with transcription data from the API,
 * rendering the table, filtering, pagination, and navigation.
 * (021-transcriptions-list)
 */

(function() {
    'use strict';

    // State
    let currentOffset = 0;
    const pageSize = 50;
    let currentFilters = {
        showAll: false
    };
    let totalFiles = 0;

    // DOM elements
    const loadingEl = document.getElementById('transcriptions-loading');
    const errorEl = document.getElementById('transcriptions-error');
    const errorMessageEl = document.getElementById('transcriptions-error-message');
    const retryBtnEl = document.getElementById('transcriptions-retry-btn');
    const contentEl = document.getElementById('transcriptions-content');
    const tableBodyEl = document.getElementById('transcriptions-table-body');
    const tableEl = document.getElementById('transcriptions-table');
    const emptyEl = document.getElementById('transcriptions-empty');
    const emptyTitleEl = document.getElementById('transcriptions-empty-title');
    const emptyHintEl = document.getElementById('transcriptions-empty-hint');
    const paginationEl = document.getElementById('transcriptions-pagination');
    const paginationInfoEl = document.getElementById('transcriptions-pagination-info');
    const prevBtnEl = document.getElementById('transcriptions-prev-btn');
    const nextBtnEl = document.getElementById('transcriptions-next-btn');

    // Filter elements
    let showAllToggleEl = null;

    /**
     * Initialize DOM element references.
     * Called during init() to ensure DOM is ready.
     */
    function initElements() {
        showAllToggleEl = document.getElementById('filter-show-all');
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
     * Create language tags HTML.
     * @param {Array} languages - Array of language codes
     * @returns {string} HTML string for language tags
     */
    function createLanguageTags(languages) {
        if (!languages || languages.length === 0) {
            return '<span class="not-analyzed">Not analyzed</span>';
        }

        return languages.map(function(lang) {
            return '<span class="language-tag">' + escapeHtml(lang) + '</span>';
        }).join('');
    }

    /**
     * Create confidence badge HTML.
     * @param {string|null} level - Confidence level (high, medium, low, or null)
     * @param {number|null} avgScore - Average confidence score for tooltip
     * @returns {string} HTML string for confidence badge
     */
    function createConfidenceBadge(level, avgScore) {
        if (!level) {
            return '<span class="confidence-badge confidence-badge--none">N/A</span>';
        }

        const levelClass = 'confidence-badge--' + level;
        const title = avgScore !== null ? ' title="' + Math.round(avgScore * 100) + '% average"' : '';
        return '<span class="confidence-badge ' + levelClass + '"' + title + '>' + escapeHtml(level) + '</span>';
    }

    /**
     * Create status indicator HTML.
     * @param {string} status - Scan status (ok, error)
     * @param {boolean} hasTranscription - Whether file has transcription data
     * @returns {string} HTML string for status indicator
     */
    function createStatusIndicator(status, hasTranscription) {
        if (status === 'error') {
            return '<span class="status-indicator status-indicator--error">Error</span>';
        }

        if (!hasTranscription) {
            return '<span class="status-indicator status-indicator--none">Not analyzed</span>';
        }

        return '<span class="status-indicator status-indicator--ok">OK</span>';
    }

    /**
     * Render a single file row.
     * @param {Object} file - File data from API
     * @returns {string} HTML string for table row
     */
    function renderFileRow(file) {
        const hasFullPath = file.path && file.path.length > 50;
        const languagesHtml = createLanguageTags(file.detected_languages);
        const confidenceHtml = createConfidenceBadge(file.confidence_level, file.confidence_avg);
        const tracksText = file.transcription_count > 0 ? file.transcription_count.toString() : '\u2014';
        const statusHtml = createStatusIndicator(file.scan_status, file.has_transcription);

        return '<tr data-file-id="' + escapeHtml(String(file.id)) + '">' +
            '<td class="transcriptions-filename"' + (hasFullPath ? ' title="' + escapeHtml(file.path) + '"' : '') + '>' +
            escapeHtml(file.filename) +
            '</td>' +
            '<td class="transcriptions-languages">' + languagesHtml + '</td>' +
            '<td class="transcriptions-confidence">' + confidenceHtml + '</td>' +
            '<td class="transcriptions-tracks">' + escapeHtml(tracksText) + '</td>' +
            '<td class="transcriptions-status">' + statusHtml + '</td>' +
            '</tr>';
    }

    /**
     * Setup click handlers on table rows for navigation to file detail.
     */
    function setupRowClickHandlers() {
        const rows = tableBodyEl.querySelectorAll('tr[data-file-id]');
        rows.forEach(function(row) {
            row.addEventListener('click', function(e) {
                // Don't navigate if clicking on a link or button
                if (e.target.tagName === 'A' || e.target.tagName === 'BUTTON') {
                    return;
                }
                const fileId = row.getAttribute('data-file-id');
                if (fileId) {
                    window.location.href = '/library/' + fileId;
                }
            });
        });
    }

    /**
     * Render the transcriptions table.
     * @param {Array} files - Array of file objects
     */
    function renderTable(files) {
        if (files.length === 0) {
            tableEl.style.display = 'none';
            emptyEl.style.display = 'block';

            if (currentFilters.showAll) {
                emptyTitleEl.textContent = 'No files in library';
                emptyHintEl.textContent = 'Scan a directory to add files to your library.';
            } else {
                emptyTitleEl.textContent = 'No transcription data available';
                emptyHintEl.textContent = 'Run language detection on your library to populate this view.';
            }
            return;
        }

        tableEl.style.display = 'table';
        emptyEl.style.display = 'none';

        const html = files.map(renderFileRow).join('');
        tableBodyEl.innerHTML = html;

        // Add click handlers to rows for navigation
        setupRowClickHandlers();
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

        if (currentFilters.showAll) {
            params.set('show_all', 'true');
        }

        params.set('limit', pageSize.toString());
        params.set('offset', currentOffset.toString());

        return '?' + params.toString();
    }

    /**
     * Update the browser URL with current filter state.
     * Uses replaceState to avoid polluting history.
     */
    function updateUrl() {
        const params = new URLSearchParams();

        if (currentFilters.showAll) {
            params.set('show_all', 'true');
        }

        const queryString = params.toString();
        const newUrl = window.location.pathname + (queryString ? '?' + queryString : '');
        history.replaceState(null, '', newUrl);
    }

    /**
     * Parse URL query params and initialize filters.
     */
    function initFiltersFromUrl() {
        const params = new URLSearchParams(window.location.search);

        currentFilters.showAll = params.get('show_all') === 'true';

        // Update form controls to match
        if (showAllToggleEl) {
            showAllToggleEl.checked = currentFilters.showAll;
        }
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
        errorMessageEl.textContent = message || 'Failed to load transcription data.';
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
     * Fetch transcriptions data from the API and render.
     */
    async function fetchTranscriptions() {
        try {
            const response = await fetch('/api/transcriptions' + buildQueryString());

            if (!response.ok) {
                throw new Error('Failed to fetch transcriptions: ' + response.status);
            }

            const data = await response.json();

            totalFiles = data.total;
            renderTable(data.files);
            updatePagination();

            // Show content
            showContent();

        } catch (error) {
            console.error('Error fetching transcriptions:', error);
            showError('Error loading transcriptions. Please refresh the page or try again.');
        }
    }

    /**
     * Handle pagination - previous page.
     */
    function handlePrevPage() {
        if (currentOffset >= pageSize) {
            currentOffset -= pageSize;
            showLoading();
            fetchTranscriptions();
        }
    }

    /**
     * Handle pagination - next page.
     */
    function handleNextPage() {
        if (currentOffset + pageSize < totalFiles) {
            currentOffset += pageSize;
            showLoading();
            fetchTranscriptions();
        }
    }

    /**
     * Handle filter change.
     * Resets pagination and triggers fetch.
     */
    function handleFilterChange() {
        currentOffset = 0;
        updateUrl();
        showLoading();
        fetchTranscriptions();
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
            fetchTranscriptions();
        });
    }

    // Export functions for external access if needed
    window.transcriptionsDashboard = {
        refresh: fetchTranscriptions
    };

    /**
     * Setup event listeners for filter controls.
     * Called after elements are initialized.
     */
    function setupFilterListeners() {
        if (showAllToggleEl) {
            showAllToggleEl.addEventListener('change', function(e) {
                currentFilters.showAll = e.target.checked;
                handleFilterChange();
            });
        }
    }

    /**
     * Initialize the transcriptions dashboard.
     */
    function init() {
        // Initialize DOM element references first
        initElements();

        // Setup event listeners for filter controls
        setupFilterListeners();

        // Parse URL params first
        initFiltersFromUrl();

        // Initial fetch
        fetchTranscriptions();
    }

    // Initial fetch on page load
    document.addEventListener('DOMContentLoaded', init);

    // Also fetch immediately if DOM is already ready
    if (document.readyState !== 'loading') {
        init();
    }
})();
