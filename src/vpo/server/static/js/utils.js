/**
 * VPO shared utility functions.
 *
 * Usage: var escapeHtml = window.VPOUtils.escapeHtml
 */
;(function () {
    'use strict'

    /**
     * Escape HTML entities using DOM textContent.
     * @param {string} str
     * @returns {string}
     */
    function escapeHtml(str) {
        if (!str && str !== 0) return ''
        var div = document.createElement('div')
        div.textContent = str
        return div.innerHTML
    }

    /**
     * Format an ISO-8601 string or Date as a relative time string.
     *
     * @param {string|Date} input - ISO string or Date object
     * @param {object} [options]
     * @param {string}  [options.emptyText='\u2014'] - text when input is falsy
     * @param {number}  [options.dateFallbackDays=30] - switch to date format after this many days
     * @param {boolean} [options.capitalizeJustNow=true] - capitalize "Just now"
     * @param {boolean} [options.includeYear=true] - include year for dates older than 365 days
     * @returns {string}
     */
    function formatRelativeTime(input, options) {
        var opts = options || {}
        var emptyText = opts.emptyText !== undefined ? opts.emptyText : '\u2014'
        var dateFallbackDays = opts.dateFallbackDays !== undefined ? opts.dateFallbackDays : 30
        var capitalizeJustNow = opts.capitalizeJustNow !== undefined ? opts.capitalizeJustNow : true
        var includeYear = opts.includeYear !== undefined ? opts.includeYear : true

        if (!input) return emptyText

        try {
            var date = input instanceof Date ? input : new Date(input)
            var now = new Date()
            var diffMs = now - date
            var diffSec = Math.floor(diffMs / 1000)
            var diffMin = Math.floor(diffSec / 60)
            var diffHour = Math.floor(diffMin / 60)
            var diffDay = Math.floor(diffHour / 24)

            if (diffDay > dateFallbackDays) {
                var dateOpts = { month: 'short', day: 'numeric' }
                if (includeYear && diffDay > 365) {
                    dateOpts.year = 'numeric'
                }
                return date.toLocaleDateString(undefined, dateOpts)
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
            return capitalizeJustNow ? 'Just now' : 'just now'
        } catch {
            return String(input)
        }
    }

    /**
     * Truncate a filename while preserving the extension.
     *
     * @param {string} filename
     * @param {number} maxLength
     * @returns {string}
     */
    function truncateFilename(filename, maxLength) {
        if (!filename || filename.length <= maxLength) {
            return filename || '\u2014'
        }

        var dotIndex = filename.lastIndexOf('.')
        var base, extension

        if (dotIndex > 0) {
            extension = filename.substring(dotIndex)
            base = filename.substring(0, dotIndex)
        } else {
            extension = ''
            base = filename
        }

        var availableForBase = maxLength - extension.length - 1

        if (availableForBase < 1) {
            return filename.substring(0, maxLength - 1) + '\u2026'
        }

        return base.substring(0, availableForBase) + '\u2026' + extension
    }

    /**
     * Format a duration in seconds as a human-readable string.
     *
     * @param {number} seconds
     * @param {object} [options]
     * @param {boolean} [options.fractionalSeconds=false] - show one decimal place for seconds < 60
     * @returns {string}
     */
    function formatDuration(seconds, options) {
        var opts = options || {}
        var fractionalSeconds = opts.fractionalSeconds || false

        if (seconds === null || seconds === undefined || isNaN(seconds)) {
            return '\u2014'
        }

        if (seconds < 0) return '\u2014'

        if (seconds < 60) {
            return fractionalSeconds ? seconds.toFixed(1) + 's' : Math.floor(seconds) + 's'
        }

        var totalSec = Math.floor(seconds)
        var minutes = Math.floor(totalSec / 60)
        var remainingSec = totalSec % 60

        if (minutes < 60) {
            return minutes + 'm ' + remainingSec + 's'
        }

        var hours = Math.floor(minutes / 60)
        var remainingMin = minutes % 60

        return hours + 'h ' + remainingMin + 'm'
    }

    /**
     * Copy text to clipboard and show brief visual feedback on the button.
     *
     * @param {string} text - Text to copy
     * @param {HTMLElement} [buttonEl] - Button element for visual feedback
     */
    function copyToClipboard(text, buttonEl) {
        if (!navigator.clipboard) return
        navigator.clipboard.writeText(text).then(function () {
            if (!buttonEl) return
            buttonEl.classList.add('btn-copy--copied')
            buttonEl.setAttribute('aria-label', 'Copied!')
            setTimeout(function () {
                buttonEl.classList.remove('btn-copy--copied')
                buttonEl.setAttribute('aria-label', 'Copy job ID to clipboard')
            }, 1500)
        }).catch(function () {
            // Silent failure — clipboard API may be blocked in some contexts
        })
    }

    window.VPOUtils = {
        escapeHtml: escapeHtml,
        formatRelativeTime: formatRelativeTime,
        truncateFilename: truncateFilename,
        formatDuration: formatDuration,
        copyToClipboard: copyToClipboard
    }
})()
