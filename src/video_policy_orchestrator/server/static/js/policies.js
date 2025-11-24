/**
 * Policies List JavaScript
 *
 * Handles relative time formatting for policy modification timestamps.
 */

(function() {
    'use strict';

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
     * Update all relative time elements on the page.
     */
    function formatTimestamps() {
        const elements = document.querySelectorAll('.relative-time[data-timestamp]');
        elements.forEach(function(el) {
            const timestamp = el.getAttribute('data-timestamp');
            if (timestamp) {
                el.textContent = formatRelativeTime(timestamp);
            }
        });
    }

    /**
     * Initialize the policies page.
     */
    function init() {
        formatTimestamps();
    }

    // Run on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
