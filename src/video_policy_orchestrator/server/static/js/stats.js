/**
 * Statistics Dashboard JavaScript
 *
 * Handles loading and displaying processing statistics from the API.
 * Part of 040-processing-stats feature.
 */

// State management
const state = {
    timeFilter: '7d',
    loading: true,
    error: null,
    summary: null,
    recent: [],
    policies: []
}

// DOM Elements
let elements = {}

/**
 * Initialize the stats dashboard
 */
function init() {
    elements = {
        loading: document.getElementById('stats-loading'),
        error: document.getElementById('stats-error'),
        errorMessage: document.getElementById('stats-error-message'),
        retryBtn: document.getElementById('stats-retry-btn'),
        content: document.getElementById('stats-content'),
        empty: document.getElementById('stats-empty'),
        timeFilter: document.getElementById('stats-time-filter'),
        // Summary cards
        filesProcessed: document.getElementById('stats-files-processed'),
        successCount: document.getElementById('stats-success-count'),
        failCount: document.getElementById('stats-fail-count'),
        spaceSaved: document.getElementById('stats-space-saved'),
        avgSavings: document.getElementById('stats-avg-savings'),
        tracksRemoved: document.getElementById('stats-tracks-removed'),
        audioRemoved: document.getElementById('stats-audio-removed'),
        subtitleRemoved: document.getElementById('stats-subtitle-removed'),
        videosTranscoded: document.getElementById('stats-videos-transcoded'),
        videosSkipped: document.getElementById('stats-videos-skipped'),
        // Tables
        recentSection: document.getElementById('stats-recent-section'),
        recentBody: document.getElementById('stats-recent-body'),
        policiesSection: document.getElementById('stats-policies-section'),
        policiesBody: document.getElementById('stats-policies-body')
    }

    // Set up event listeners
    if (elements.timeFilter) {
        elements.timeFilter.addEventListener('change', onTimeFilterChange)
    }
    if (elements.retryBtn) {
        elements.retryBtn.addEventListener('click', loadStats)
    }

    // Initial load
    loadStats()
}

/**
 * Handle time filter change
 */
function onTimeFilterChange(event) {
    state.timeFilter = event.target.value
    loadStats()
}

/**
 * Load all statistics data
 */
async function loadStats() {
    showLoading()

    try {
        const params = state.timeFilter ? `?since=${state.timeFilter}` : ''

        // Fetch all data in parallel
        const [summaryRes, recentRes, policiesRes] = await Promise.all([
            fetch(`/api/stats/summary${params}`),
            fetch(`/api/stats/recent${params}&limit=20`),
            fetch(`/api/stats/policies${params}`)
        ])

        if (!summaryRes.ok || !recentRes.ok || !policiesRes.ok) {
            throw new Error('Failed to load statistics')
        }

        state.summary = await summaryRes.json()
        state.recent = await recentRes.json()
        state.policies = await policiesRes.json()
        state.error = null

        renderStats()
    } catch (err) {
        console.error('Error loading stats:', err)
        state.error = err.message
        showError(err.message)
    }
}

/**
 * Show loading state
 */
function showLoading() {
    state.loading = true
    elements.loading.style.display = 'block'
    elements.error.style.display = 'none'
    elements.content.style.display = 'none'
}

/**
 * Show error state
 */
function showError(message) {
    state.loading = false
    elements.loading.style.display = 'none'
    elements.error.style.display = 'block'
    elements.content.style.display = 'none'
    elements.errorMessage.textContent = message || 'Failed to load statistics.'
}

/**
 * Render all statistics
 */
function renderStats() {
    state.loading = false
    elements.loading.style.display = 'none'
    elements.error.style.display = 'none'
    elements.content.style.display = 'block'

    const summary = state.summary

    // Check if there's any data
    if (!summary || summary.total_files_processed === 0) {
        showEmpty()
        return
    }

    elements.empty.style.display = 'none'
    elements.recentSection.style.display = 'block'
    elements.policiesSection.style.display = 'block'

    // Render summary cards
    elements.filesProcessed.textContent = formatNumber(summary.total_files_processed)
    elements.successCount.textContent = formatNumber(summary.total_successful)
    elements.failCount.textContent = formatNumber(summary.total_failed)
    elements.spaceSaved.textContent = formatBytes(summary.total_size_saved)
    elements.avgSavings.textContent = formatPercent(summary.avg_savings_percent)

    const totalTracks = summary.total_audio_removed + summary.total_subtitles_removed + summary.total_attachments_removed
    elements.tracksRemoved.textContent = formatNumber(totalTracks)
    elements.audioRemoved.textContent = formatNumber(summary.total_audio_removed)
    elements.subtitleRemoved.textContent = formatNumber(summary.total_subtitles_removed)

    elements.videosTranscoded.textContent = formatNumber(summary.total_videos_transcoded)
    elements.videosSkipped.textContent = formatNumber(summary.total_videos_skipped)

    // Render tables
    renderRecentTable()
    renderPoliciesTable()
}

/**
 * Show empty state
 */
function showEmpty() {
    elements.empty.style.display = 'block'
    elements.recentSection.style.display = 'none'
    elements.policiesSection.style.display = 'none'
}

/**
 * Render the recent processing table
 */
function renderRecentTable() {
    const tbody = elements.recentBody
    tbody.innerHTML = ''

    if (!state.recent || state.recent.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="stats-empty-row">No recent processing history</td></tr>'
        return
    }

    for (const entry of state.recent) {
        const row = document.createElement('tr')

        // Date
        const dateCell = document.createElement('td')
        dateCell.textContent = formatDate(entry.processed_at)
        row.appendChild(dateCell)

        // Policy
        const policyCell = document.createElement('td')
        policyCell.textContent = entry.policy_name || '-'
        policyCell.classList.add('stats-policy-cell')
        row.appendChild(policyCell)

        // Space saved
        const savedCell = document.createElement('td')
        savedCell.textContent = formatBytes(entry.size_change)
        if (entry.size_change > 0) {
            savedCell.classList.add('stats-positive')
        } else if (entry.size_change < 0) {
            savedCell.classList.add('stats-negative')
        }
        row.appendChild(savedCell)

        // Tracks removed
        const tracksCell = document.createElement('td')
        const totalRemoved = entry.audio_removed + entry.subtitle_removed + entry.attachments_removed
        tracksCell.textContent = totalRemoved.toString()
        row.appendChild(tracksCell)

        // Duration
        const durationCell = document.createElement('td')
        durationCell.textContent = formatDuration(entry.duration_seconds)
        row.appendChild(durationCell)

        // Status
        const statusCell = document.createElement('td')
        const statusBadge = document.createElement('span')
        statusBadge.classList.add('stats-status-badge')
        if (entry.success) {
            statusBadge.classList.add('stats-status-success')
            statusBadge.textContent = 'OK'
        } else {
            statusBadge.classList.add('stats-status-error')
            statusBadge.textContent = 'FAIL'
            statusBadge.title = entry.error_message || 'Unknown error'
        }
        statusCell.appendChild(statusBadge)
        row.appendChild(statusCell)

        tbody.appendChild(row)
    }
}

/**
 * Render the policies comparison table
 */
function renderPoliciesTable() {
    const tbody = elements.policiesBody
    tbody.innerHTML = ''

    if (!state.policies || state.policies.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="stats-empty-row">No policy statistics available</td></tr>'
        return
    }

    for (const policy of state.policies) {
        const row = document.createElement('tr')

        // Policy name
        const nameCell = document.createElement('td')
        nameCell.textContent = policy.policy_name || '-'
        nameCell.classList.add('stats-policy-cell')
        row.appendChild(nameCell)

        // Files
        const filesCell = document.createElement('td')
        filesCell.textContent = formatNumber(policy.files_processed)
        row.appendChild(filesCell)

        // Success rate
        const successCell = document.createElement('td')
        successCell.textContent = formatPercent(policy.success_rate * 100)
        row.appendChild(successCell)

        // Space saved
        const savedCell = document.createElement('td')
        savedCell.textContent = formatBytes(policy.total_size_saved)
        row.appendChild(savedCell)

        // Avg savings
        const avgCell = document.createElement('td')
        avgCell.textContent = formatPercent(policy.avg_savings_percent)
        row.appendChild(avgCell)

        // Last used
        const lastCell = document.createElement('td')
        lastCell.textContent = formatDate(policy.last_used)
        row.appendChild(lastCell)

        tbody.appendChild(row)
    }
}

// =====================
// Formatting utilities
// =====================

/**
 * Format a number with thousand separators
 */
function formatNumber(num) {
    if (num === null || num === undefined) return '0'
    return num.toLocaleString()
}

/**
 * Format bytes as human-readable string
 */
function formatBytes(bytes) {
    if (bytes === null || bytes === undefined || bytes === 0) return '0 B'

    const sign = bytes < 0 ? '-' : ''
    const absBytes = Math.abs(bytes)

    const units = ['B', 'KB', 'MB', 'GB', 'TB']
    let unitIndex = 0
    let value = absBytes

    while (value >= 1024 && unitIndex < units.length - 1) {
        value /= 1024
        unitIndex++
    }

    return `${sign}${value.toFixed(1)} ${units[unitIndex]}`
}

/**
 * Format a percentage value
 */
function formatPercent(value) {
    if (value === null || value === undefined) return '0%'
    return `${value.toFixed(1)}%`
}

/**
 * Format duration in seconds as human-readable string
 */
function formatDuration(seconds) {
    if (seconds === null || seconds === undefined || seconds < 0) return '-'

    if (seconds < 60) {
        return `${seconds.toFixed(1)}s`
    } else if (seconds < 3600) {
        const minutes = Math.floor(seconds / 60)
        const secs = Math.floor(seconds % 60)
        return `${minutes}m ${secs}s`
    } else {
        const hours = Math.floor(seconds / 3600)
        const minutes = Math.floor((seconds % 3600) / 60)
        return `${hours}h ${minutes}m`
    }
}

/**
 * Format ISO date string as readable date
 */
function formatDate(isoString) {
    if (!isoString) return '-'

    try {
        const date = new Date(isoString)
        return date.toLocaleDateString(undefined, {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        })
    } catch {
        return isoString.slice(0, 16).replace('T', ' ')
    }
}

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init)
} else {
    init()
}
