/**
 * Transcription Detail View JavaScript
 * 022-transcription-detail
 *
 * Handles timestamp formatting for the transcription detail page.
 */

(function () {
  'use strict';

  /**
   * Format ISO timestamp to relative time string.
   * @param {string} isoTimestamp - ISO 8601 timestamp string
   * @returns {string} Relative time string (e.g., "2 hours ago")
   */
  function formatRelativeTime(isoTimestamp) {
    if (!isoTimestamp) return '';

    const date = new Date(isoTimestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);

    if (diffSec < 60) {
      return 'just now';
    } else if (diffMin < 60) {
      return `${diffMin} minute${diffMin !== 1 ? 's' : ''} ago`;
    } else if (diffHour < 24) {
      return `${diffHour} hour${diffHour !== 1 ? 's' : ''} ago`;
    } else if (diffDay < 7) {
      return `${diffDay} day${diffDay !== 1 ? 's' : ''} ago`;
    } else {
      // Fall back to locale date string for older dates
      return date.toLocaleDateString();
    }
  }

  /**
   * Format all timestamp elements on the page.
   */
  function formatTimestamps() {
    const timeElements = document.querySelectorAll('time[data-timestamp]');
    timeElements.forEach(function (el) {
      const timestamp = el.getAttribute('data-timestamp');
      if (timestamp) {
        const relative = formatRelativeTime(timestamp);
        el.textContent = relative;
        // Keep the full timestamp in the title attribute for hover
        el.setAttribute('title', new Date(timestamp).toLocaleString());
      }
    });
  }

  // Initialize on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', formatTimestamps);
  } else {
    formatTimestamps();
  }
})();
