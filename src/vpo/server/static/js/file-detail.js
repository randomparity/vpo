/**
 * File Detail Page JavaScript
 *
 * Handles collapsible track sections and timestamp formatting.
 * (020-file-detail-view)
 */

(function () {
    'use strict'

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
     * Format all timestamps on the page.
     */
    function formatTimestamps() {
        const timeElements = document.querySelectorAll('time[data-timestamp]')
        timeElements.forEach(function (el) {
            const timestamp = el.getAttribute('data-timestamp')
            if (timestamp) {
                el.textContent = formatRelativeTime(timestamp)
                // Keep the full timestamp in title for hover
                el.setAttribute('title', timestamp)
            }
        })
    }

    /**
     * Setup collapsible sections for files with many tracks.
     */
    function setupCollapsibleSections() {
        const collapsibleHeaders = document.querySelectorAll('.collapsible-header')

        collapsibleHeaders.forEach(function (header) {
            header.addEventListener('click', function () {
                const section = header.closest('.collapsible')
                if (!section) return

                const content = section.querySelector('.collapsible-content')
                const icon = header.querySelector('.collapse-icon')

                if (content) {
                    const isExpanded = !content.classList.contains('collapsed')

                    if (isExpanded) {
                        content.classList.add('collapsed')
                        if (icon) icon.textContent = '▶'
                        header.setAttribute('aria-expanded', 'false')
                    } else {
                        content.classList.remove('collapsed')
                        if (icon) icon.textContent = '▼'
                        header.setAttribute('aria-expanded', 'true')
                    }
                }
            })

            // Set initial ARIA state
            header.setAttribute('aria-expanded', 'true')
            header.style.cursor = 'pointer'
        })
    }

    /**
     * Initialize the file detail page.
     */
    function init() {
        formatTimestamps()
        setupCollapsibleSections()
    }

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init)
    } else {
        init()
    }
})()
