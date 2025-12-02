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
    policies: [],
    selectedDetail: null,
    detailLoading: false
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
        policiesBody: document.getElementById('stats-policies-body'),
        // Detail modal
        detailModal: document.getElementById('stats-detail-modal'),
        detailClose: document.getElementById('stats-detail-close'),
        detailBody: document.getElementById('stats-detail-body')
    }

    // Set up event listeners
    if (elements.timeFilter) {
        elements.timeFilter.addEventListener('change', onTimeFilterChange)
    }
    if (elements.retryBtn) {
        elements.retryBtn.addEventListener('click', loadStats)
    }

    // Modal event listeners
    if (elements.detailClose) {
        elements.detailClose.addEventListener('click', closeDetailModal)
    }
    if (elements.detailModal) {
        // Close on backdrop click
        elements.detailModal.querySelector('.stats-modal-backdrop').addEventListener('click', closeDetailModal)
        // Close on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && elements.detailModal.style.display !== 'none') {
                closeDetailModal()
            }
        })
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
        tbody.innerHTML = '<tr><td colspan="7" class="stats-empty-row">No recent processing history</td></tr>'
        return
    }

    for (const entry of state.recent) {
        const row = document.createElement('tr')
        row.classList.add('stats-row-clickable')
        row.dataset.statsId = entry.stats_id
        row.addEventListener('click', () => showDetailModal(entry.stats_id))
        row.setAttribute('role', 'button')
        row.setAttribute('tabindex', '0')
        row.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                showDetailModal(entry.stats_id)
            }
        })

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

        // Audio tracks removed
        const audioCell = document.createElement('td')
        audioCell.textContent = entry.audio_removed.toString()
        row.appendChild(audioCell)

        // Subtitle tracks removed
        const subCell = document.createElement('td')
        subCell.textContent = entry.subtitle_removed.toString()
        row.appendChild(subCell)

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

// =====================
// Detail modal functions
// =====================

/**
 * Show the detail modal for a stats entry
 */
async function showDetailModal(statsId) {
    if (!elements.detailModal) return

    state.detailLoading = true
    elements.detailModal.style.display = 'flex'
    elements.detailBody.innerHTML = '<div class="stats-detail-loading">Loading details...</div>'

    try {
        const res = await fetch(`/api/stats/${statsId}`)
        if (!res.ok) {
            throw new Error('Failed to load details')
        }

        const detail = await res.json()
        state.selectedDetail = detail
        renderDetailContent(detail)
    } catch (err) {
        console.error('Error loading detail:', err)
        elements.detailBody.innerHTML = `
            <div class="stats-detail-error">
                <p>Failed to load processing details.</p>
                <button type="button" class="stats-retry-btn" onclick="showDetailModal('${statsId}')">Retry</button>
            </div>
        `
    } finally {
        state.detailLoading = false
    }
}

/**
 * Close the detail modal
 */
function closeDetailModal() {
    if (elements.detailModal) {
        elements.detailModal.style.display = 'none'
        state.selectedDetail = null
    }
}

/**
 * Render detail content inside modal
 */
function renderDetailContent(detail) {
    const savingsPercent = detail.size_before > 0
        ? ((detail.size_change / detail.size_before) * 100).toFixed(1)
        : '0.0'

    let html = `
        <div class="stats-detail-section">
            <h4>File Information</h4>
            <dl class="stats-detail-list">
                <dt>File</dt>
                <dd>${escapeHtml(detail.filename || 'N/A')}</dd>
                ${detail.file_path ? `<dt>Path</dt><dd>${escapeHtml(detail.file_path)}</dd>` : ''}
                <dt>Processed</dt>
                <dd>${formatDate(detail.processed_at)}</dd>
                <dt>Policy</dt>
                <dd>${escapeHtml(detail.policy_name)}</dd>
                <dt>Status</dt>
                <dd class="${detail.success ? 'stats-positive' : 'stats-negative'}">${detail.success ? 'Success' : 'Failed'}</dd>
                ${detail.error_message ? `<dt>Error</dt><dd class="stats-negative">${escapeHtml(detail.error_message)}</dd>` : ''}
            </dl>
        </div>

        <div class="stats-detail-section">
            <h4>Size Changes</h4>
            <dl class="stats-detail-list">
                <dt>Before</dt>
                <dd>${formatBytes(detail.size_before)}</dd>
                <dt>After</dt>
                <dd>${formatBytes(detail.size_after)}</dd>
                <dt>${detail.size_change >= 0 ? 'Saved' : 'Added'}</dt>
                <dd class="${detail.size_change >= 0 ? 'stats-positive' : 'stats-negative'}">${formatBytes(Math.abs(detail.size_change))} (${savingsPercent}%)</dd>
            </dl>
        </div>

        <div class="stats-detail-section">
            <h4>Track Changes</h4>
            <table class="stats-detail-table">
                <thead>
                    <tr>
                        <th>Type</th>
                        <th>Before</th>
                        <th>After</th>
                        <th>Removed</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Audio</td>
                        <td>${detail.audio_tracks_before}</td>
                        <td>${detail.audio_tracks_after}</td>
                        <td class="${detail.audio_tracks_removed > 0 ? 'stats-positive' : ''}">${detail.audio_tracks_removed}</td>
                    </tr>
                    <tr>
                        <td>Subtitle</td>
                        <td>${detail.subtitle_tracks_before}</td>
                        <td>${detail.subtitle_tracks_after}</td>
                        <td class="${detail.subtitle_tracks_removed > 0 ? 'stats-positive' : ''}">${detail.subtitle_tracks_removed}</td>
                    </tr>
                    <tr>
                        <td>Attachments</td>
                        <td>${detail.attachments_before}</td>
                        <td>${detail.attachments_after}</td>
                        <td class="${detail.attachments_removed > 0 ? 'stats-positive' : ''}">${detail.attachments_removed}</td>
                    </tr>
                </tbody>
            </table>
        </div>
    `

    // Transcode info
    if (detail.video_source_codec || detail.video_target_codec) {
        html += `
            <div class="stats-detail-section">
                <h4>Transcode Information</h4>
                <dl class="stats-detail-list">
                    ${detail.video_source_codec ? `<dt>Source Codec</dt><dd>${escapeHtml(detail.video_source_codec)}</dd>` : ''}
                    ${detail.video_target_codec ? `<dt>Target Codec</dt><dd>${escapeHtml(detail.video_target_codec)}</dd>` : ''}
                    <dt>Skipped</dt>
                    <dd>${detail.video_transcode_skipped ? `Yes (${escapeHtml(detail.video_skip_reason || 'N/A')})` : 'No'}</dd>
                    <dt>Audio Transcoded</dt>
                    <dd>${detail.audio_tracks_transcoded}</dd>
                    <dt>Audio Preserved</dt>
                    <dd>${detail.audio_tracks_preserved}</dd>
                </dl>
            </div>
        `
    }

    // Processing info
    html += `
        <div class="stats-detail-section">
            <h4>Processing Info</h4>
            <dl class="stats-detail-list">
                <dt>Duration</dt>
                <dd>${formatDuration(detail.duration_seconds)}</dd>
                <dt>Phases</dt>
                <dd>${detail.phases_completed}/${detail.phases_total}</dd>
                <dt>Total Changes</dt>
                <dd>${detail.total_changes}</dd>
            </dl>
        </div>
    `

    // Actions
    if (detail.actions && detail.actions.length > 0) {
        html += `
            <div class="stats-detail-section">
                <h4>Actions Performed</h4>
                <ul class="stats-action-list">
        `
        for (const action of detail.actions) {
            const trackInfo = action.track_type
                ? ` (${escapeHtml(action.track_type)}${action.track_index !== null ? ` #${action.track_index}` : ''})`
                : ''
            const statusClass = action.success ? 'stats-action-success' : 'stats-action-error'
            html += `
                <li class="${statusClass}">
                    <span class="stats-action-type">${escapeHtml(action.action_type)}</span>${trackInfo}
                    ${action.message ? `<span class="stats-action-message">${escapeHtml(action.message)}</span>` : ''}
                </li>
            `
        }
        html += `
                </ul>
            </div>
        `
    }

    elements.detailBody.innerHTML = html
}

/**
 * Escape HTML special characters
 */
function escapeHtml(text) {
    if (text === null || text === undefined) return ''
    const div = document.createElement('div')
    div.textContent = text
    return div.innerHTML
}

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init)
} else {
    init()
}
