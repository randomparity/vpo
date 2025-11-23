/**
 * Job Detail Page JavaScript
 *
 * Handles relative timestamps and client-side enhancements for the job detail view.
 */

(function() {
    'use strict';

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
     * Initialize the job detail page.
     */
    function init() {
        // Update timestamps to relative format
        updateTimestamps();

        // Format durations
        updateDurations();

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
