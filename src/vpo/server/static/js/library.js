/**
 * Library Dashboard JavaScript
 *
 * Handles fetching files from the API, rendering the table,
 * filtering, pagination, and display formatting.
 * Extended with search, resolution, audio language, and subtitle filters
 * (019-library-filters-search).
 */

(function () {
    'use strict'

    // State
    let currentOffset = 0
    const pageSize = 50
    let currentFilters = {
        status: '',
        search: '',
        resolution: '',
        audio_lang: [],
        subtitles: ''
    }
    let totalFiles = 0
    let debounceTimer = null
    const DEBOUNCE_DELAY = 300 // ms

    // DOM elements
    const loadingEl = document.getElementById('library-loading')
    const errorEl = document.getElementById('library-error')
    const errorMessageEl = document.getElementById('library-error-message')
    const retryBtnEl = document.getElementById('library-retry-btn')
    const contentEl = document.getElementById('library-content')
    const tableBodyEl = document.getElementById('library-table-body')
    const tableEl = document.getElementById('library-table')
    const emptyEl = document.getElementById('library-empty')
    const emptyTitleEl = document.getElementById('library-empty-title')
    const emptyHintEl = document.getElementById('library-empty-hint')
    const paginationEl = document.getElementById('library-pagination')
    const paginationInfoEl = document.getElementById('library-pagination-info')
    const prevBtnEl = document.getElementById('library-prev-btn')
    const nextBtnEl = document.getElementById('library-next-btn')

    // Filter elements (019-library-filters-search)
    // Note: These are queried when script loads (after DOM due to script placement at bottom)
    let searchInputEl = null
    let statusFilterEl = null
    let resolutionFilterEl = null
    let audioLangFilterEl = null
    let subtitlesFilterEl = null
    let clearFiltersBtnEl = null

    /**
     * Initialize DOM element references.
     * Called during init() to ensure DOM is ready.
     */
    function initElements() {
        searchInputEl = document.getElementById('filter-search')
        statusFilterEl = document.getElementById('filter-status')
        resolutionFilterEl = document.getElementById('filter-resolution')
        audioLangFilterEl = document.getElementById('filter-audio-lang')
        subtitlesFilterEl = document.getElementById('filter-subtitles')
        clearFiltersBtnEl = document.getElementById('clear-filters-btn')
    }

    /**
     * Format an ISO timestamp to a relative time string.
     * @param {string} isoString - ISO 8601 timestamp
     * @returns {string} Relative time (e.g., "2 hours ago")
     */
    function formatRelativeTime(isoString) {
        if (!isoString) {
            return '\u2014'
        }

        try {
            const date = new Date(isoString)
            const now = new Date()
            const diffMs = now - date
            const diffSec = Math.floor(diffMs / 1000)
            const diffMin = Math.floor(diffSec / 60)
            const diffHour = Math.floor(diffMin / 60)
            const diffDay = Math.floor(diffHour / 24)

            if (diffDay > 30) {
                // Fall back to date format for older items
                return date.toLocaleDateString(undefined, {
                    month: 'short',
                    day: 'numeric',
                    year: diffDay > 365 ? 'numeric' : undefined
                })
            }
            if (diffDay > 0) {
                return diffDay + ' day' + (diffDay > 1 ? 's' : '') + ' ago'
            }
            if (diffHour > 0) {
                return diffHour + ' hour' + (diffHour > 1 ? 's' : '') + ' ago'
            }
            if (diffMin > 0) {
                return diffMin + ' minute' + (diffMin > 1 ? 's' : '') + ' ago'
            }
            return 'Just now'
        } catch {
            return isoString
        }
    }

    /**
     * Truncate a path for display.
     * @param {string} path - Full file path
     * @param {number} maxLength - Maximum display length
     * @returns {string} Truncated path (ellipsis at end if too long)
     */
    function truncatePath(path, maxLength) {
        if (!path || path.length <= maxLength) {
            return path || '\u2014'
        }

        // Truncate at the end with ellipsis
        return path.substring(0, maxLength - 3) + '...'
    }

    /**
     * Create a scan status badge element.
     * @param {string} status - Scan status (ok, error)
     * @param {string|null} scanError - Error message if status is error
     * @returns {string} HTML string for status badge
     */
    function createScanStatusBadge(status, scanError) {
        const normalizedStatus = (status || 'ok').toLowerCase()

        if (normalizedStatus === 'error') {
            const title = scanError ? ' title="' + escapeHtml(scanError) + '"' : ''
            return '<span class="status-badge status-badge--failed"' + title + '>' +
                '<span class="scan-error-icon" aria-hidden="true">&#9888;</span> error</span>'
        }

        return '<span class="status-badge status-badge--completed">' + escapeHtml(status || 'ok') + '</span>'
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
     * Render a single file row.
     * @param {Object} file - File data from API
     * @returns {string} HTML string for table row
     */
    function renderFileRow(file) {
        const truncatedFilename = truncatePath(file.filename, 50)
        const hasFullPath = file.path && file.path.length > 50
        const title = file.title || '\u2014'
        const resolution = file.resolution || '\u2014'
        const audioLanguages = file.audio_languages || '\u2014'
        const scannedAt = formatRelativeTime(file.scanned_at)
        // Policy column: always show em-dash (policy tracking out of scope)
        const policy = '\u2014'

        // Add error class for rows with scan errors
        const rowClass = file.scan_status === 'error' ? ' class="library-row-error"' : ''

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
            '</tr>'
    }

    /**
     * Render the library table.
     * @param {Array} files - Array of file objects
     * @param {boolean} hasFilters - Whether any filters are active
     */
    function renderLibraryTable(files, hasFilters) {
        if (files.length === 0) {
            tableEl.style.display = 'none'
            emptyEl.style.display = 'block'

            if (hasFilters) {
                emptyTitleEl.textContent = 'No matching files'
                emptyHintEl.innerHTML = 'Try adjusting your filters or <a href="#" id="clear-filters-link">clear all filters</a> to see all files.'
                // Add click handler for the clear link
                const clearLink = document.getElementById('clear-filters-link')
                if (clearLink) {
                    clearLink.addEventListener('click', function (e) {
                        e.preventDefault()
                        clearAllFilters()
                    })
                }
            } else {
                emptyTitleEl.textContent = 'No files in library'
                emptyHintEl.innerHTML = 'Scan a directory to add files to your library using the CLI:<br>' +
                    '<code>vpo scan /path/to/videos</code>'
            }
            return
        }

        tableEl.style.display = 'table'
        emptyEl.style.display = 'none'

        const html = files.map(renderFileRow).join('')
        tableBodyEl.innerHTML = html

        // Add click handlers to rows for navigation (020-file-detail-view)
        setupRowClickHandlers()
    }

    /**
     * Setup click and keyboard handlers on table rows for navigation to file detail.
     * (020-file-detail-view)
     */
    function setupRowClickHandlers() {
        const rows = tableBodyEl.querySelectorAll('tr[data-file-id]')
        rows.forEach(function (row) {
            row.style.cursor = 'pointer'
            row.setAttribute('tabindex', '0')
            row.setAttribute('role', 'link')
            row.addEventListener('click', function (e) {
                // Don't navigate if clicking on a link or button
                if (e.target.tagName === 'A' || e.target.tagName === 'BUTTON') {
                    return
                }
                const fileId = row.getAttribute('data-file-id')
                if (fileId) {
                    window.location.href = '/library/' + fileId
                }
            })
            row.addEventListener('keydown', function (e) {
                // Allow Enter and Space to activate the row
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    const fileId = row.getAttribute('data-file-id')
                    if (fileId) {
                        window.location.href = '/library/' + fileId
                    }
                }
            })
        })
    }

    /**
     * Update pagination controls.
     */
    function updatePagination() {
        if (totalFiles <= pageSize) {
            paginationEl.style.display = 'none'
            return
        }

        paginationEl.style.display = 'flex'

        const start = currentOffset + 1
        const end = Math.min(currentOffset + pageSize, totalFiles)
        paginationInfoEl.textContent = 'Showing ' + start + '-' + end + ' of ' + totalFiles + ' files'

        prevBtnEl.disabled = currentOffset === 0
        nextBtnEl.disabled = currentOffset + pageSize >= totalFiles
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
        if (currentFilters.search) {
            params.set('search', currentFilters.search)
        }
        if (currentFilters.resolution) {
            params.set('resolution', currentFilters.resolution)
        }
        if (currentFilters.audio_lang && currentFilters.audio_lang.length > 0) {
            currentFilters.audio_lang.forEach(function (lang) {
                params.append('audio_lang', lang)
            })
        }
        if (currentFilters.subtitles) {
            params.set('subtitles', currentFilters.subtitles)
        }

        params.set('limit', pageSize.toString())
        params.set('offset', currentOffset.toString())

        return '?' + params.toString()
    }

    /**
     * Update the browser URL with current filter state.
     * Uses replaceState to avoid polluting history.
     */
    function updateUrl() {
        const params = new URLSearchParams()

        if (currentFilters.status) {
            params.set('status', currentFilters.status)
        }
        if (currentFilters.search) {
            params.set('search', currentFilters.search)
        }
        if (currentFilters.resolution) {
            params.set('resolution', currentFilters.resolution)
        }
        if (currentFilters.audio_lang && currentFilters.audio_lang.length > 0) {
            currentFilters.audio_lang.forEach(function (lang) {
                params.append('audio_lang', lang)
            })
        }
        if (currentFilters.subtitles) {
            params.set('subtitles', currentFilters.subtitles)
        }

        const queryString = params.toString()
        const newUrl = window.location.pathname + (queryString ? '?' + queryString : '')
        history.replaceState(null, '', newUrl)
    }

    /**
     * Parse URL query params and initialize filters.
     */
    function initFiltersFromUrl() {
        const params = new URLSearchParams(window.location.search)

        currentFilters.status = params.get('status') || ''
        currentFilters.search = params.get('search') || ''
        currentFilters.resolution = params.get('resolution') || ''
        currentFilters.audio_lang = params.getAll('audio_lang')
        currentFilters.subtitles = params.get('subtitles') || ''

        // Update form controls to match
        if (statusFilterEl) {
            statusFilterEl.value = currentFilters.status
        }
        if (searchInputEl) {
            searchInputEl.value = currentFilters.search
        }
        if (resolutionFilterEl) {
            resolutionFilterEl.value = currentFilters.resolution
        }
        if (subtitlesFilterEl) {
            subtitlesFilterEl.value = currentFilters.subtitles
        }
        // Audio lang handled after languages are fetched
    }

    /**
     * Check if any filters are currently active.
     * @returns {boolean} True if any filter is active
     */
    function hasActiveFilters() {
        return Boolean(
            currentFilters.status ||
            currentFilters.search ||
            currentFilters.resolution ||
            (currentFilters.audio_lang && currentFilters.audio_lang.length > 0) ||
            currentFilters.subtitles
        )
    }

    /**
     * Update the visibility and state of the clear filters button.
     */
    function updateClearFiltersButton() {
        if (clearFiltersBtnEl) {
            if (hasActiveFilters()) {
                clearFiltersBtnEl.style.display = 'inline-block'
            } else {
                clearFiltersBtnEl.style.display = 'none'
            }
        }
    }

    /**
     * Update visual indicators for active filters.
     */
    function updateFilterVisuals() {
        // Add 'active' class to filters with non-default values
        if (searchInputEl) {
            searchInputEl.classList.toggle('filter-active', Boolean(currentFilters.search))
        }
        if (statusFilterEl) {
            statusFilterEl.classList.toggle('filter-active', Boolean(currentFilters.status))
        }
        if (resolutionFilterEl) {
            resolutionFilterEl.classList.toggle('filter-active', Boolean(currentFilters.resolution))
        }
        if (audioLangFilterEl) {
            audioLangFilterEl.classList.toggle('filter-active',
                currentFilters.audio_lang && currentFilters.audio_lang.length > 0)
        }
        if (subtitlesFilterEl) {
            subtitlesFilterEl.classList.toggle('filter-active', Boolean(currentFilters.subtitles))
        }

        updateClearFiltersButton()
    }

    /**
     * Clear all filters and reset to default state.
     */
    function clearAllFilters() {
        currentFilters = {
            status: '',
            search: '',
            resolution: '',
            audio_lang: [],
            subtitles: ''
        }
        currentOffset = 0

        // Reset form controls
        if (searchInputEl) searchInputEl.value = ''
        if (statusFilterEl) statusFilterEl.value = ''
        if (resolutionFilterEl) resolutionFilterEl.value = ''
        if (audioLangFilterEl) audioLangFilterEl.value = ''
        if (subtitlesFilterEl) subtitlesFilterEl.value = ''

        updateFilterVisuals()
        updateUrl()
        showLoading()
        fetchLibrary()
    }

    /**
     * Show loading state.
     */
    function showLoading() {
        loadingEl.style.display = 'block'
        errorEl.style.display = 'none'
        contentEl.style.display = 'none'
    }

    /**
     * Show error state.
     * @param {string} message - Error message to display
     */
    function showError(message) {
        loadingEl.style.display = 'none'
        errorEl.style.display = 'block'
        contentEl.style.display = 'none'
        errorMessageEl.textContent = message || 'Failed to load library files.'
    }

    /**
     * Show content state.
     */
    function showContent() {
        loadingEl.style.display = 'none'
        errorEl.style.display = 'none'
        contentEl.style.display = 'block'
    }

    /**
     * Fetch library files from the API and render them.
     */
    async function fetchLibrary() {
        try {
            const response = await fetch('/api/library' + buildQueryString())

            if (!response.ok) {
                throw new Error('Failed to fetch library: ' + response.status)
            }

            const data = await response.json()

            totalFiles = data.total
            renderLibraryTable(data.files, data.has_filters)
            updatePagination()
            updateFilterVisuals()

            // Show content
            showContent()

        } catch (error) {
            console.error('Error fetching library:', error)
            showError('Error loading library. Please refresh the page or try again.')
        }
    }

    /**
     * Fetch available audio languages and populate dropdown.
     */
    async function fetchLanguages() {
        if (!audioLangFilterEl) return

        try {
            const response = await fetch('/api/library/languages')
            if (!response.ok) {
                console.warn('Failed to fetch languages:', response.status)
                return
            }

            const data = await response.json()

            // Clear existing options
            audioLangFilterEl.innerHTML = ''

            // Add "All languages" option
            const allOption = document.createElement('option')
            allOption.value = ''
            allOption.textContent = 'All languages'
            audioLangFilterEl.appendChild(allOption)

            // Add language options
            if (data.languages && data.languages.length > 0) {
                data.languages.forEach(function (lang) {
                    const option = document.createElement('option')
                    option.value = lang.code
                    option.textContent = lang.label
                    audioLangFilterEl.appendChild(option)
                })
            }

            // Restore selected value from URL params (single select - use first value)
            if (currentFilters.audio_lang && currentFilters.audio_lang.length > 0) {
                audioLangFilterEl.value = currentFilters.audio_lang[0]
            }

            updateFilterVisuals()

        } catch (error) {
            console.error('Error fetching languages:', error)
        }
    }

    /**
     * Handle pagination - previous page.
     */
    function handlePrevPage() {
        if (currentOffset >= pageSize) {
            currentOffset -= pageSize
            showLoading()
            fetchLibrary()
        }
    }

    /**
     * Handle pagination - next page.
     */
    function handleNextPage() {
        if (currentOffset + pageSize < totalFiles) {
            currentOffset += pageSize
            showLoading()
            fetchLibrary()
        }
    }

    /**
     * Handle filter change (generic).
     * Resets pagination and triggers fetch.
     */
    function handleFilterChange() {
        currentOffset = 0
        updateUrl()
        updateFilterVisuals()
        showLoading()
        fetchLibrary()
    }

    /**
     * Debounce function for search input.
     * @param {Function} fn - Function to debounce
     * @param {number} delay - Delay in ms
     * @returns {Function} Debounced function
     */
    function debounce(fn, delay) {
        return function () {
            const args = arguments
            if (debounceTimer) {
                clearTimeout(debounceTimer)
            }
            debounceTimer = setTimeout(function () {
                fn.apply(null, args)
            }, delay)
        }
    }

    // Event listeners for pagination
    if (prevBtnEl) {
        prevBtnEl.addEventListener('click', handlePrevPage)
    }
    if (nextBtnEl) {
        nextBtnEl.addEventListener('click', handleNextPage)
    }

    // Event listener for retry button
    if (retryBtnEl) {
        retryBtnEl.addEventListener('click', function () {
            showLoading()
            fetchLibrary()
        })
    }

    // Export functions for external access if needed
    window.libraryDashboard = {
        refresh: fetchLibrary,
        clearFilters: clearAllFilters
    }

    /**
     * Setup event listeners for filter controls.
     * Called after elements are initialized.
     */
    function setupFilterListeners() {
        if (searchInputEl) {
            const debouncedSearch = debounce(function () {
                currentFilters.search = searchInputEl.value.trim()
                handleFilterChange()
            }, DEBOUNCE_DELAY)

            searchInputEl.addEventListener('input', debouncedSearch)

            // Also handle Enter key for immediate search
            searchInputEl.addEventListener('keypress', function (e) {
                if (e.key === 'Enter') {
                    if (debounceTimer) {
                        clearTimeout(debounceTimer)
                    }
                    currentFilters.search = searchInputEl.value.trim()
                    handleFilterChange()
                }
            })
        }

        if (statusFilterEl) {
            statusFilterEl.addEventListener('change', function (e) {
                currentFilters.status = e.target.value
                handleFilterChange()
            })
        }

        if (resolutionFilterEl) {
            resolutionFilterEl.addEventListener('change', function (e) {
                currentFilters.resolution = e.target.value
                handleFilterChange()
            })
        }

        if (audioLangFilterEl) {
            audioLangFilterEl.addEventListener('change', function (e) {
                // Single select - wrap in array for backend compatibility
                var value = e.target.value
                currentFilters.audio_lang = value ? [value] : []
                handleFilterChange()
            })
        }

        if (subtitlesFilterEl) {
            subtitlesFilterEl.addEventListener('change', function (e) {
                currentFilters.subtitles = e.target.value
                handleFilterChange()
            })
        }

        if (clearFiltersBtnEl) {
            clearFiltersBtnEl.addEventListener('click', clearAllFilters)
        }
    }

    /**
     * Initialize the library dashboard.
     */
    async function init() {
        // Initialize DOM element references first
        initElements()

        // Setup event listeners for filter controls
        setupFilterListeners()

        // Parse URL params first
        initFiltersFromUrl()

        // Fetch languages for dropdown
        await fetchLanguages()

        // Update visual state
        updateFilterVisuals()

        // Initial fetch
        fetchLibrary()
    }

    // Initial fetch on page load
    document.addEventListener('DOMContentLoaded', init)

    // Also fetch immediately if DOM is already ready
    if (document.readyState !== 'loading') {
        init()
    }
})()
