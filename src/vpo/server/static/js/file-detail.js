/**
 * File Detail Page JavaScript
 *
 * Handles collapsible track sections and timestamp formatting.
 * (020-file-detail-view)
 */

(function () {
    'use strict'

    // Shared utilities
    var formatRelativeTime = window.VPOUtils.formatRelativeTime

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

            // Initial ARIA state and cursor are set in the template HTML/CSS
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
