/**
 * Workflow Section Module for Policy Editor (036-v9-policy-editor)
 *
 * Handles workflow configuration UI.
 * Features:
 * - Processing phases selection (analyze, apply, transcode)
 * - Auto process toggle
 * - On error handling (skip, continue, fail)
 *
 * Works with existing HTML structure in policy_editor.html template.
 */

/**
 * Initialize the workflow section
 * @param {Object} policyData - Current policy data
 * @param {Function} onUpdate - Callback when workflow config changes
 * @returns {Object} Controller with methods to get/set state
 */
export function initWorkflowSection(policyData, onUpdate) {
    const phaseAnalyze = document.getElementById('phase-analyze')
    const phaseApply = document.getElementById('phase-apply')
    const phaseTranscode = document.getElementById('phase-transcode')
    const autoProcessSelect = document.getElementById('workflow-auto-process')
    const onErrorSelect = document.getElementById('workflow-on-error')

    if (!phaseAnalyze || !phaseApply || !phaseTranscode) {
        console.warn('Workflow section elements not found')
        return null
    }

    // Internal state
    let workflowConfig = policyData.workflow ? { ...policyData.workflow } : null

    function notifyUpdate() {
        onUpdate(getConfig())
    }

    function getConfig() {
        // Collect selected phases
        const phases = []
        if (phaseAnalyze.checked) phases.push('analyze')
        if (phaseApply.checked) phases.push('apply')
        if (phaseTranscode.checked) phases.push('transcode')

        // If no phases selected, return null (no workflow config)
        if (phases.length === 0) {
            return null
        }

        const config = {
            phases: phases
        }

        // Add auto_process if enabled
        if (autoProcessSelect && autoProcessSelect.value === 'true') {
            config.auto_process = true
        }

        // Add on_error if not default (continue)
        if (onErrorSelect && onErrorSelect.value !== 'continue') {
            config.on_error = onErrorSelect.value
        }

        return config
    }

    function setInitialValues() {
        // Set phase checkboxes
        if (workflowConfig?.phases) {
            const phases = Array.isArray(workflowConfig.phases)
                ? workflowConfig.phases
                : []
            phaseAnalyze.checked = phases.includes('analyze')
            phaseApply.checked = phases.includes('apply')
            phaseTranscode.checked = phases.includes('transcode')
        } else {
            // Default: analyze and apply are checked
            phaseAnalyze.checked = true
            phaseApply.checked = true
            phaseTranscode.checked = false
        }

        // Set auto_process
        if (autoProcessSelect) {
            autoProcessSelect.value = workflowConfig?.auto_process ? 'true' : 'false'
        }

        // Set on_error
        if (onErrorSelect) {
            onErrorSelect.value = workflowConfig?.on_error || 'continue'
        }
    }

    // Attach event listeners
    phaseAnalyze.addEventListener('change', notifyUpdate)
    phaseApply.addEventListener('change', notifyUpdate)
    phaseTranscode.addEventListener('change', notifyUpdate)

    if (autoProcessSelect) {
        autoProcessSelect.addEventListener('change', notifyUpdate)
    }

    if (onErrorSelect) {
        onErrorSelect.addEventListener('change', notifyUpdate)
    }

    // Set initial values
    setInitialValues()

    // Return controller
    return {
        /**
         * Get current workflow configuration
         * @returns {Object|null} Workflow config or null if not configured
         */
        getConfig() {
            return getConfig()
        },

        /**
         * Set workflow configuration
         * @param {Object|null} config - Workflow config
         */
        setConfig(config) {
            workflowConfig = config || null
            setInitialValues()
        },

        /**
         * Refresh the UI with current policy data
         * @param {Object} policyData - Policy data
         */
        refresh(policyData) {
            workflowConfig = policyData.workflow || null
            setInitialValues()
        }
    }
}
