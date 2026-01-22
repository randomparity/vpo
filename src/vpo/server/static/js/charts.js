/**
 * Simple SVG charting utilities for VPO stats dashboard.
 *
 * Provides lightweight chart rendering without external dependencies.
 * Charts use CSS custom properties for theming (dark mode support).
 */

// Chart color palette (uses CSS custom properties when available)
const CHART_COLORS = {
    primary: 'var(--color-primary, #3498db)',
    success: '#27ae60',
    warning: '#f39c12',
    error: '#e74c3c',
    info: '#5dade2',
    muted: 'var(--color-text-muted, #666)',
    grid: 'var(--color-border, #e1e4e8)',
    text: 'var(--color-text, #333)',
    background: 'var(--color-content-bg, #fff)'
}

// SVG namespace
const SVG_NS = 'http://www.w3.org/2000/svg'

/**
 * Create an SVG element with attributes
 * @param {string} tag - SVG tag name
 * @param {Object} attrs - Attributes to set
 * @returns {SVGElement}
 */
function createSvgElement(tag, attrs = {}) {
    const el = document.createElementNS(SVG_NS, tag)
    for (const [key, value] of Object.entries(attrs)) {
        el.setAttribute(key, value)
    }
    return el
}

/**
 * Format bytes as human-readable string
 * @param {number} bytes
 * @returns {string}
 */
function formatBytesShort(bytes) {
    if (bytes === 0) return '0'
    const sign = bytes < 0 ? '-' : ''
    const absBytes = Math.abs(bytes)
    const units = ['B', 'KB', 'MB', 'GB', 'TB']
    let unitIndex = 0
    let value = absBytes
    while (value >= 1024 && unitIndex < units.length - 1) {
        value /= 1024
        unitIndex++
    }
    return `${sign}${value.toFixed(value >= 100 ? 0 : 1)}${units[unitIndex]}`
}

/**
 * Format a number with K/M suffix for compact display
 * @param {number} num
 * @returns {string}
 */
function formatNumberShort(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M'
    }
    if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K'
    }
    return num.toString()
}

/**
 * Render a horizontal bar chart.
 *
 * @param {HTMLElement} container - Container element to render into
 * @param {Array<{label: string, value: number, color?: string}>} data - Chart data
 * @param {Object} options - Chart options
 * @param {string} options.title - Chart title (optional)
 * @param {string} options.valueFormat - Format type: 'bytes', 'number', 'percent'
 * @param {number} options.height - Chart height in pixels
 */
function renderBarChart(container, data, options = {}) {
    const {
        title = '',
        valueFormat = 'number',
        height = 200
    } = options

    // Clear container
    container.innerHTML = ''

    if (!data || data.length === 0) {
        container.innerHTML = '<div class="chart-empty">No data available</div>'
        return
    }

    // Calculate dimensions
    const width = container.clientWidth || 400
    const margin = { top: title ? 30 : 10, right: 60, bottom: 20, left: 100 }
    const chartWidth = width - margin.left - margin.right
    const chartHeight = height - margin.top - margin.bottom
    const barHeight = Math.min(25, (chartHeight - (data.length - 1) * 4) / data.length)
    const barGap = 4

    // Find max value for scaling
    const maxValue = Math.max(...data.map(d => Math.abs(d.value)), 1)

    // Create SVG
    const svg = createSvgElement('svg', {
        width: width,
        height: height,
        class: 'chart-bar'
    })

    // Add title if provided
    if (title) {
        const titleEl = createSvgElement('text', {
            x: width / 2,
            y: 18,
            'text-anchor': 'middle',
            class: 'chart-title'
        })
        titleEl.textContent = title
        svg.appendChild(titleEl)
    }

    // Create chart group
    const chartGroup = createSvgElement('g', {
        transform: `translate(${margin.left}, ${margin.top})`
    })

    // Render bars and labels
    data.forEach((item, index) => {
        const y = index * (barHeight + barGap)
        const barWidth = Math.max(0, (Math.abs(item.value) / maxValue) * chartWidth)
        const color = item.color || CHART_COLORS.primary

        // Label
        const label = createSvgElement('text', {
            x: -8,
            y: y + barHeight / 2 + 4,
            'text-anchor': 'end',
            class: 'chart-label'
        })
        label.textContent = item.label.length > 15
            ? item.label.substring(0, 12) + '...'
            : item.label
        chartGroup.appendChild(label)

        // Bar background
        const barBg = createSvgElement('rect', {
            x: 0,
            y: y,
            width: chartWidth,
            height: barHeight,
            class: 'chart-bar-bg'
        })
        chartGroup.appendChild(barBg)

        // Bar fill
        const bar = createSvgElement('rect', {
            x: 0,
            y: y,
            width: barWidth,
            height: barHeight,
            fill: color,
            class: 'chart-bar-fill',
            rx: 2,
            ry: 2
        })
        chartGroup.appendChild(bar)

        // Value label
        let valueText
        switch (valueFormat) {
        case 'bytes':
            valueText = formatBytesShort(item.value)
            break
        case 'percent':
            valueText = item.value.toFixed(1) + '%'
            break
        default:
            valueText = formatNumberShort(item.value)
        }

        const valueLabel = createSvgElement('text', {
            x: chartWidth + 8,
            y: y + barHeight / 2 + 4,
            'text-anchor': 'start',
            class: 'chart-value'
        })
        valueLabel.textContent = valueText
        chartGroup.appendChild(valueLabel)
    })

    svg.appendChild(chartGroup)
    container.appendChild(svg)
}

/**
 * Render a line chart for time series data.
 *
 * @param {HTMLElement} container - Container element to render into
 * @param {Array<{date: string, value: number, label?: string}>} data - Chart data (date is ISO string)
 * @param {Object} options - Chart options
 * @param {string} options.title - Chart title (optional)
 * @param {string} options.valueFormat - Format type: 'bytes', 'number', 'percent'
 * @param {number} options.height - Chart height in pixels
 * @param {string} options.color - Line color
 * @param {boolean} options.showArea - Fill area under line
 */
function renderLineChart(container, data, options = {}) {
    const {
        title = '',
        valueFormat = 'number',
        height = 200,
        color = CHART_COLORS.primary,
        showArea = true
    } = options

    // Clear container
    container.innerHTML = ''

    if (!data || data.length === 0) {
        container.innerHTML = '<div class="chart-empty">No data available</div>'
        return
    }

    // Sort data by date
    const sortedData = [...data].sort((a, b) =>
        new Date(a.date).getTime() - new Date(b.date).getTime()
    )

    // Calculate dimensions
    const width = container.clientWidth || 400
    const margin = { top: title ? 30 : 10, right: 20, bottom: 40, left: 60 }
    const chartWidth = width - margin.left - margin.right
    const chartHeight = height - margin.top - margin.bottom

    // Find value range
    const values = sortedData.map(d => d.value)
    const minValue = Math.min(0, ...values) // Include 0 as minimum
    const maxValue = Math.max(...values, 1)
    const valueRange = maxValue - minValue || 1

    // Create date scale
    const dates = sortedData.map(d => new Date(d.date).getTime())
    const minDate = dates[0]
    const maxDate = dates[dates.length - 1]
    const dateRange = maxDate - minDate || 1

    // Scale functions
    const scaleX = (date) => {
        const t = (new Date(date).getTime() - minDate) / dateRange
        return t * chartWidth
    }

    const scaleY = (value) => {
        const t = (value - minValue) / valueRange
        return chartHeight - t * chartHeight
    }

    // Create SVG
    const svg = createSvgElement('svg', {
        width: width,
        height: height,
        class: 'chart-line'
    })

    // Add title if provided
    if (title) {
        const titleEl = createSvgElement('text', {
            x: width / 2,
            y: 18,
            'text-anchor': 'middle',
            class: 'chart-title'
        })
        titleEl.textContent = title
        svg.appendChild(titleEl)
    }

    // Create chart group
    const chartGroup = createSvgElement('g', {
        transform: `translate(${margin.left}, ${margin.top})`
    })

    // Grid lines (horizontal)
    const gridCount = 4
    for (let i = 0; i <= gridCount; i++) {
        const y = (chartHeight / gridCount) * i
        const gridLine = createSvgElement('line', {
            x1: 0,
            y1: y,
            x2: chartWidth,
            y2: y,
            class: 'chart-grid'
        })
        chartGroup.appendChild(gridLine)

        // Y-axis labels
        const value = maxValue - (i / gridCount) * valueRange
        let labelText
        switch (valueFormat) {
        case 'bytes':
            labelText = formatBytesShort(value)
            break
        case 'percent':
            labelText = value.toFixed(0) + '%'
            break
        default:
            labelText = formatNumberShort(value)
        }

        const yLabel = createSvgElement('text', {
            x: -8,
            y: y + 4,
            'text-anchor': 'end',
            class: 'chart-axis-label'
        })
        yLabel.textContent = labelText
        chartGroup.appendChild(yLabel)
    }

    // Build path data
    let pathData = ''
    let areaData = ''

    sortedData.forEach((item, index) => {
        const x = scaleX(item.date)
        const y = scaleY(item.value)

        if (index === 0) {
            pathData = `M ${x} ${y}`
            areaData = `M ${x} ${chartHeight} L ${x} ${y}`
        } else {
            pathData += ` L ${x} ${y}`
            areaData += ` L ${x} ${y}`
        }
    })

    // Close area path
    areaData += ` L ${scaleX(sortedData[sortedData.length - 1].date)} ${chartHeight} Z`

    // Draw area fill
    if (showArea) {
        const area = createSvgElement('path', {
            d: areaData,
            class: 'chart-area',
            fill: color,
            opacity: 0.15
        })
        chartGroup.appendChild(area)
    }

    // Draw line
    const line = createSvgElement('path', {
        d: pathData,
        fill: 'none',
        stroke: color,
        'stroke-width': 2,
        class: 'chart-line-path'
    })
    chartGroup.appendChild(line)

    // Draw data points
    sortedData.forEach((item) => {
        const x = scaleX(item.date)
        const y = scaleY(item.value)

        const point = createSvgElement('circle', {
            cx: x,
            cy: y,
            r: 4,
            fill: color,
            class: 'chart-point'
        })
        chartGroup.appendChild(point)
    })

    // X-axis labels (show first, middle, last)
    const xLabelIndices = sortedData.length <= 3
        ? sortedData.map((_, i) => i)
        : [0, Math.floor(sortedData.length / 2), sortedData.length - 1]

    xLabelIndices.forEach(index => {
        if (index >= sortedData.length) return
        const item = sortedData[index]
        const x = scaleX(item.date)

        const xLabel = createSvgElement('text', {
            x: x,
            y: chartHeight + 20,
            'text-anchor': 'middle',
            class: 'chart-axis-label'
        })

        // Format date based on range
        const date = new Date(item.date)
        if (dateRange > 86400000 * 7) { // More than 7 days
            xLabel.textContent = date.toLocaleDateString(undefined, {
                month: 'short',
                day: 'numeric'
            })
        } else {
            xLabel.textContent = date.toLocaleDateString(undefined, {
                weekday: 'short',
                day: 'numeric'
            })
        }

        chartGroup.appendChild(xLabel)
    })

    svg.appendChild(chartGroup)
    container.appendChild(svg)
}

/**
 * Render a compression ratio gauge.
 *
 * @param {HTMLElement} container - Container element to render into
 * @param {number} ratio - Compression ratio (0-100, where 100 = no compression)
 * @param {Object} options - Chart options
 * @param {string} options.title - Chart title
 * @param {number} options.size - Gauge size in pixels
 */
function renderGauge(container, ratio, options = {}) {
    const {
        title = 'Compression Ratio',
        size = 150
    } = options

    // Clear container
    container.innerHTML = ''

    // Clamp ratio to 0-100
    const displayRatio = Math.max(0, Math.min(100, ratio))
    const savings = 100 - displayRatio

    // Determine color based on savings
    let color = CHART_COLORS.muted
    if (savings > 30) color = CHART_COLORS.success
    else if (savings > 15) color = CHART_COLORS.primary
    else if (savings > 5) color = CHART_COLORS.warning

    // Create SVG
    const svg = createSvgElement('svg', {
        width: size,
        height: size,
        class: 'chart-gauge'
    })

    const centerX = size / 2
    const centerY = size / 2
    const radius = size / 2 - 20
    const strokeWidth = 12

    // Background arc
    const bgCircle = createSvgElement('circle', {
        cx: centerX,
        cy: centerY,
        r: radius,
        fill: 'none',
        stroke: CHART_COLORS.grid,
        'stroke-width': strokeWidth,
        class: 'chart-gauge-bg'
    })
    svg.appendChild(bgCircle)

    // Value arc (show savings percentage)
    const circumference = 2 * Math.PI * radius
    const dashOffset = circumference * (1 - savings / 100)

    const valueArc = createSvgElement('circle', {
        cx: centerX,
        cy: centerY,
        r: radius,
        fill: 'none',
        stroke: color,
        'stroke-width': strokeWidth,
        'stroke-dasharray': circumference,
        'stroke-dashoffset': dashOffset,
        'stroke-linecap': 'round',
        transform: `rotate(-90 ${centerX} ${centerY})`,
        class: 'chart-gauge-value'
    })
    svg.appendChild(valueArc)

    // Center text (savings percentage)
    const valueText = createSvgElement('text', {
        x: centerX,
        y: centerY + 8,
        'text-anchor': 'middle',
        class: 'chart-gauge-text'
    })
    valueText.textContent = savings.toFixed(1) + '%'
    svg.appendChild(valueText)

    // Title below gauge
    if (title) {
        const titleEl = createSvgElement('text', {
            x: centerX,
            y: size - 4,
            'text-anchor': 'middle',
            class: 'chart-gauge-title'
        })
        titleEl.textContent = title
        svg.appendChild(titleEl)
    }

    container.appendChild(svg)
}

// Export functions for use in stats.js
window.VPOCharts = {
    renderBarChart,
    renderLineChart,
    renderGauge,
    formatBytesShort,
    formatNumberShort,
    CHART_COLORS
}
