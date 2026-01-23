/**
 * Policies List JavaScript
 *
 * Handles relative time formatting for policy modification timestamps
 * and the Create New Policy dialog.
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
     * Update all relative time elements on the page.
     */
    function formatTimestamps() {
        const elements = document.querySelectorAll('.relative-time[data-timestamp]')
        elements.forEach(function (el) {
            const timestamp = el.getAttribute('data-timestamp')
            if (timestamp) {
                el.textContent = formatRelativeTime(timestamp)
            }
        })
    }

    /**
     * Initialize the Create New Policy dialog functionality.
     */
    function initCreatePolicyDialog() {
        const createBtn = document.getElementById('create-policy-btn')
        const dialog = document.getElementById('create-policy-dialog')
        const form = document.getElementById('create-policy-form')
        const cancelBtn = document.getElementById('cancel-create-btn')
        const submitBtn = document.getElementById('submit-create-btn')
        const errorDiv = document.getElementById('create-policy-error')
        const nameInput = document.getElementById('policy-name')
        const descriptionInput = document.getElementById('policy-description')
        const categoryInput = document.getElementById('policy-category')

        if (!createBtn || !dialog || !form) {
            return
        }

        /**
         * Show the dialog.
         */
        function openDialog() {
            form.reset()
            hideError()
            dialog.showModal()
            nameInput.focus()
        }

        /**
         * Close the dialog.
         */
        function closeDialog() {
            dialog.close()
        }

        /**
         * Show an error message in the dialog.
         * @param {string} message - Error message to display
         */
        function showError(message) {
            errorDiv.textContent = message
            errorDiv.hidden = false
        }

        /**
         * Hide the error message.
         */
        function hideError() {
            errorDiv.hidden = true
            errorDiv.textContent = ''
        }

        /**
         * Set the form to loading/submitting state.
         * @param {boolean} loading - Whether the form is loading
         */
        function setLoading(loading) {
            submitBtn.disabled = loading
            cancelBtn.disabled = loading
            nameInput.disabled = loading
            descriptionInput.disabled = loading
            if (categoryInput) {
                categoryInput.disabled = loading
            }
            submitBtn.textContent = loading ? 'Creating...' : 'Create Policy'
        }

        /**
         * Handle form submission.
         * @param {Event} e - Submit event
         */
        async function handleSubmit(e) {
            e.preventDefault()
            hideError()

            const name = nameInput.value.trim()
            const description = descriptionInput.value.trim()

            // Client-side validation
            if (!name) {
                showError('Policy name is required')
                nameInput.focus()
                return
            }

            if (!/^[a-zA-Z0-9_-]+$/.test(name)) {
                showError('Policy name can only contain letters, numbers, dashes, and underscores')
                nameInput.focus()
                return
            }

            setLoading(true)

            try {
                const category = categoryInput ? categoryInput.value : ''
                const response = await fetch('/api/policies', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        name: name,
                        description: description || undefined,
                        category: category || undefined
                    })
                })

                const data = await response.json()

                if (!response.ok) {
                    // Handle specific error cases
                    if (response.status === 409) {
                        showError(`A policy named "${name}" already exists`)
                    } else if (data.error) {
                        showError(data.error)
                    } else {
                        showError('Failed to create policy')
                    }
                    setLoading(false)
                    return
                }

                // Success - redirect to edit the new policy
                if (data.policy && data.policy.name) {
                    window.location.href = `/policies/${data.policy.name}/edit`
                } else {
                    // Fallback: just reload the page
                    window.location.reload()
                }
            } catch (err) {
                console.error('Create policy error:', err)
                showError('Network error. Please try again.')
                setLoading(false)
            }
        }

        // Event listeners
        createBtn.addEventListener('click', openDialog)
        cancelBtn.addEventListener('click', closeDialog)
        form.addEventListener('submit', handleSubmit)

        // Close on backdrop click (outside dialog content)
        dialog.addEventListener('click', function (e) {
            if (e.target === dialog) {
                closeDialog()
            }
        })

        // Close on Escape key
        dialog.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                closeDialog()
            }
        })
    }

    /**
     * Initialize category filter functionality.
     */
    function initCategoryFilter() {
        const filterSelect = document.getElementById('filter-category')
        const tableBody = document.querySelector('.policies-table tbody')

        if (!filterSelect || !tableBody) {
            return
        }

        // Collect unique categories from table
        const rows = tableBody.querySelectorAll('tr')
        const categories = new Set()

        rows.forEach(function (row) {
            const category = row.getAttribute('data-category')
            if (category) {
                categories.add(category)
            }
        })

        // Populate filter dropdown with sorted categories
        const sortedCategories = Array.from(categories).sort()
        sortedCategories.forEach(function (category) {
            const option = document.createElement('option')
            option.value = category
            option.textContent = category
            filterSelect.appendChild(option)
        })

        // Handle filter change
        filterSelect.addEventListener('change', function () {
            const selectedCategory = filterSelect.value

            rows.forEach(function (row) {
                const rowCategory = row.getAttribute('data-category')
                if (!selectedCategory || rowCategory === selectedCategory) {
                    row.style.display = ''
                } else {
                    row.style.display = 'none'
                }
            })

            // Update count display
            updateVisibleCount()
        })
    }

    /**
     * Update the visible policy count after filtering.
     */
    function updateVisibleCount() {
        const countEl = document.querySelector('.policies-count')
        const tableBody = document.querySelector('.policies-table tbody')

        if (!countEl || !tableBody) {
            return
        }

        const visibleRows = tableBody.querySelectorAll('tr:not([style*="display: none"])')
        const totalRows = tableBody.querySelectorAll('tr')
        const visible = visibleRows.length
        const total = totalRows.length

        if (visible === total) {
            countEl.textContent = 'Showing ' + total + ' polic' + (total === 1 ? 'y' : 'ies')
        } else {
            countEl.textContent = 'Showing ' + visible + ' of ' + total + ' polic' + (total === 1 ? 'y' : 'ies')
        }
    }

    /**
     * Initialize the policies page.
     */
    function init() {
        formatTimestamps()
        initCreatePolicyDialog()
        initCategoryFilter()
    }

    // Run on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init)
    } else {
        init()
    }
})()
