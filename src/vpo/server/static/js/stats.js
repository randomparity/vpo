/**
 * Statistics Dashboard JavaScript
 *
 * Handles loading and displaying processing statistics from the API.
 * Part of 040-processing-stats feature.
 */

// Shared utilities
var escapeHtml = window.VPOUtils.escapeHtml
var _formatDuration = window.VPOUtils.formatDuration
function formatDuration(seconds) {
    return _formatDuration(seconds, { fractionalSeconds: true })
}

// State management
const state = {
    timeFilter: '7d',
    loading: true,
    error: null,
    summary: null,
    recent: [],
    policies: [],
    trends: [],
    libraryTrends: [],
    libraryDistribution: null,
    selectedDetail: null,
    detailLoading: false
}

// Focus management for modal accessibility
let lastFocusedElement = null

// Debounce for time filter
const DEBOUNCE_DELAY = 300
let filterDebounceTimer = null

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
        hardwareEncodes: document.getElementById('stats-hardware-encodes'),
        softwareEncodes: document.getElementById('stats-software-encodes'),
        // Tables
        recentSection: document.getElementById('stats-recent-section'),
        recentBody: document.getElementById('stats-recent-body'),
        policiesSection: document.getElementById('stats-policies-section'),
        policiesBody: document.getElementById('stats-policies-body'),
        // Library overview charts
        librarySection: document.getElementById('stats-library-section'),
        chartLibraryFiles: document.getElementById('stats-chart-library-files'),
        chartLibrarySize: document.getElementById('stats-chart-library-size'),
        // Composition pie charts
        compositionSection: document.getElementById('stats-composition-section'),
        chartContainers: document.getElementById('stats-chart-containers'),
        chartVideoCodecs: document.getElementById('stats-chart-video-codecs'),
        chartAudioCodecs: document.getElementById('stats-chart-audio-codecs'),
        // Charts
        chartsSection: document.getElementById('stats-charts-section'),
        chartTrend: document.getElementById('stats-chart-trend'),
        chartPolicy: document.getElementById('stats-chart-policy'),
        chartGauge: document.getElementById('stats-chart-gauge'),
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
 * Handle time filter change with debouncing
 */
function onTimeFilterChange(event) {
    state.timeFilter = event.target.value

    // Debounce to prevent rapid API calls
    if (filterDebounceTimer) {
        clearTimeout(filterDebounceTimer)
    }
    filterDebounceTimer = setTimeout(() => {
        loadStats()
    }, DEBOUNCE_DELAY)
}

/**
 * Build query string using URLSearchParams
 */
function buildQueryParams(extras = {}) {
    const params = new URLSearchParams()
    if (state.timeFilter) {
        params.set('since', state.timeFilter)
    }
    Object.entries(extras).forEach(([key, value]) => {
        params.set(key, String(value))
    })
    const str = params.toString()
    return str ? `?${str}` : ''
}

/**
 * Load all statistics data
 */
async function loadStats() {
    showLoading()

    try {
        // Determine group_by based on time filter for trends
        let groupBy = 'day'
        if (state.timeFilter === '90d' || state.timeFilter === '') {
            groupBy = 'week'
        }

        // Fetch all data in parallel
        const [summaryRes, recentRes, policiesRes, trendsRes, libraryRes, distributionRes] = await Promise.all([
            fetch(`/api/stats/summary${buildQueryParams()}`),
            fetch(`/api/stats/recent${buildQueryParams({ limit: 20 })}`),
            fetch(`/api/stats/policies${buildQueryParams()}`),
            fetch(`/api/stats/trends${buildQueryParams({ group_by: groupBy })}`),
            fetch(`/api/stats/library-trends${buildQueryParams()}`),
            fetch('/api/stats/library-distribution')
        ])

        if (!summaryRes.ok || !recentRes.ok || !policiesRes.ok || !trendsRes.ok) {
            throw new Error('Failed to load statistics')
        }

        state.summary = await summaryRes.json()
        state.recent = await recentRes.json()
        state.policies = await policiesRes.json()
        state.trends = await trendsRes.json()
        state.libraryTrends = libraryRes.ok ? await libraryRes.json() : []
        state.libraryDistribution = distributionRes.ok ? await distributionRes.json() : null
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

    // Hardware encoder stats (Issue #264)
    if (elements.hardwareEncodes) {
        elements.hardwareEncodes.textContent = formatNumber(summary.hardware_encodes || 0)
    }
    if (elements.softwareEncodes) {
        elements.softwareEncodes.textContent = formatNumber(summary.software_encodes || 0)
    }

    // Render charts
    renderLibraryCharts()
    renderCompositionCharts()
    renderCharts()

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
    if (elements.chartsSection) {
        elements.chartsSection.style.display = 'none'
    }
    // Library charts are independent of processing stats
    renderLibraryCharts()
    renderCompositionCharts()
}

/**
 * Render library overview charts (file count + size over time)
 */
function renderLibraryCharts() {
    if (typeof window.VPOCharts === 'undefined') {
        return
    }

    const { renderLineChart } = window.VPOCharts
    const data = state.libraryTrends

    if (elements.librarySection) {
        elements.librarySection.style.display = data && data.length > 0 ? 'block' : 'none'
    }

    if (!data || data.length === 0) {
        return
    }

    // File count chart (total + missing as two series)
    if (elements.chartLibraryFiles) {
        const fileData = data.map(s => ({
            date: s.snapshot_at.slice(0, 10),
            value: s.total_files,
            label: s.snapshot_at.slice(0, 10)
        }))
        renderLineChart(elements.chartLibraryFiles, fileData, {
            title: '',
            valueFormat: 'number',
            height: 200,
            showArea: true
        })
    }

    // Size chart
    if (elements.chartLibrarySize) {
        const sizeData = data.map(s => ({
            date: s.snapshot_at.slice(0, 10),
            value: s.total_size_bytes,
            label: s.snapshot_at.slice(0, 10)
        }))
        renderLineChart(elements.chartLibrarySize, sizeData, {
            title: '',
            valueFormat: 'bytes',
            height: 200,
            showArea: true
        })
    }
}

/**
 * Render library composition pie charts (container, video codec, audio codec)
 */
function renderCompositionCharts() {
    if (typeof window.VPOCharts === 'undefined') {
        return
    }

    const { renderPieChart } = window.VPOCharts
    const data = state.libraryDistribution

    if (elements.compositionSection) {
        elements.compositionSection.style.display = data ? 'block' : 'none'
    }

    if (!data) {
        return
    }

    if (elements.chartContainers) {
        renderPieChart(elements.chartContainers, data.containers, { size: 180 })
    }
    if (elements.chartVideoCodecs) {
        renderPieChart(elements.chartVideoCodecs, data.video_codecs, { size: 180 })
    }
    if (elements.chartAudioCodecs) {
        renderPieChart(elements.chartAudioCodecs, data.audio_codecs, { size: 180 })
    }
}

/**
 * Render charts using VPOCharts utilities
 */
function renderCharts() {
    // Check if charts module is available
    if (typeof window.VPOCharts === 'undefined') {
        console.warn('VPOCharts module not loaded, skipping chart rendering')
        return
    }

    const { renderLineChart, renderBarChart, renderGauge } = window.VPOCharts

    // Show charts section
    if (elements.chartsSection) {
        elements.chartsSection.style.display = 'block'
    }

    // Render processing trend line chart
    if (elements.chartTrend && state.trends && state.trends.length > 0) {
        const trendData = state.trends.map(t => ({
            date: t.date,
            value: t.files_processed,
            label: t.date
        }))

        renderLineChart(elements.chartTrend, trendData, {
            title: '',
            valueFormat: 'number',
            height: 200,
            showArea: true
        })
    } else if (elements.chartTrend) {
        elements.chartTrend.innerHTML = '<div class="chart-empty">No trend data available</div>'
    }

    // Render policy savings bar chart
    if (elements.chartPolicy && state.policies && state.policies.length > 0) {
        // Sort policies by size saved and take top 5
        const policyData = [...state.policies]
            .sort((a, b) => b.total_size_saved - a.total_size_saved)
            .slice(0, 5)
            .map(p => ({
                label: p.policy_name || 'Unknown',
                value: p.total_size_saved,
                color: p.total_size_saved > 0 ? window.VPOCharts.CHART_COLORS.success : window.VPOCharts.CHART_COLORS.muted
            }))

        renderBarChart(elements.chartPolicy, policyData, {
            title: '',
            valueFormat: 'bytes',
            height: 200
        })
    } else if (elements.chartPolicy) {
        elements.chartPolicy.innerHTML = '<div class="chart-empty">No policy data available</div>'
    }

    // Render compression gauge
    if (elements.chartGauge && state.summary) {
        // avg_savings_percent is already a percentage (e.g., 25.5 for 25.5%)
        const savingsPercent = state.summary.avg_savings_percent || 0
        // For the gauge, we show 100 - savings (so 0% savings = 100% gauge, 30% savings = 70% gauge)
        // But the gauge shows savings directly
        renderGauge(elements.chartGauge, 100 - savingsPercent, {
            title: 'Avg Savings',
            size: 140
        })
    } else if (elements.chartGauge) {
        elements.chartGauge.innerHTML = '<div class="chart-empty">No data</div>'
    }
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
 * Trap focus within the modal for accessibility
 */
function trapFocusInModal(e) {
    if (e.key !== 'Tab') return

    const focusableElements = elements.detailModal.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    )
    if (focusableElements.length === 0) return

    const first = focusableElements[0]
    const last = focusableElements[focusableElements.length - 1]

    if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last.focus()
    } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
    }
}

/**
 * Show the detail modal for a stats entry
 */
async function showDetailModal(statsId) {
    if (!elements.detailModal) return

    // Save the currently focused element for restoration
    lastFocusedElement = document.activeElement

    state.detailLoading = true
    elements.detailModal.style.display = 'flex'
    elements.detailBody.innerHTML = `
        <div class="stats-detail-loading">
            <div class="stats-loading-spinner"></div>
            <span>Loading details...</span>
        </div>
    `

    // Add focus trap listener
    document.addEventListener('keydown', trapFocusInModal)

    // Move focus to close button
    if (elements.detailClose) {
        elements.detailClose.focus()
    }

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
                <button type="button" class="stats-retry-btn" id="detail-retry-btn">Retry</button>
            </div>
        `
        // Attach event listener properly instead of inline onclick
        const retryBtn = document.getElementById('detail-retry-btn')
        if (retryBtn) {
            retryBtn.addEventListener('click', () => showDetailModal(statsId))
        }
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

        // Remove focus trap listener
        document.removeEventListener('keydown', trapFocusInModal)

        // Restore focus to the element that triggered the modal
        if (lastFocusedElement && typeof lastFocusedElement.focus === 'function') {
            lastFocusedElement.focus()
        }
        lastFocusedElement = null
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

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init)
} else {
    init()
}
