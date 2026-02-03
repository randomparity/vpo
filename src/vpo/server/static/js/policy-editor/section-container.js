/**
 * Container Section Module for Policy Editor (036-v9-policy-editor)
 *
 * Handles container format configuration UI.
 * Features:
 * - Target container dropdown (mkv, mp4)
 * - On incompatible codec dropdown (error, skip, transcode)
 *
 * Works with existing HTML structure in policy_editor.html template.
 */

/**
 * Initialize the container section
 * @param {Object} policyData - Current policy data
 * @param {Function} onUpdate - Callback when container config changes
 * @returns {Object} Controller with methods to get/set state
 */
export function initContainerSection(policyData, onUpdate) {
    const targetSelect = document.getElementById('container-target')
    const optionsDiv = document.getElementById('container-options')
    const onIncompatibleSelect = document.getElementById('container-on-incompatible')

    if (!targetSelect) {
        console.warn('Container section elements not found')
        return null
    }

    // Internal state
    let containerConfig = policyData.container ? { ...policyData.container } : null

    function notifyUpdate() {
        onUpdate(getConfig())
    }

    // preserve_metadata checkbox
    const preserveMetadataCheckbox = document.getElementById('container-preserve-metadata')

    function getConfig() {
        if (!targetSelect.value) {
            return null
        }

        const config = {
            target: targetSelect.value
        }

        if (onIncompatibleSelect && onIncompatibleSelect.value && onIncompatibleSelect.value !== 'error') {
            config.on_incompatible_codec = onIncompatibleSelect.value
        }

        if (preserveMetadataCheckbox && !preserveMetadataCheckbox.checked) {
            config.preserve_metadata = false
        }

        return config
    }

    function updateVisibility() {
        if (optionsDiv) {
            optionsDiv.style.display = targetSelect.value ? 'block' : 'none'
        }
    }

    function setInitialValues() {
        // Set initial values from policy data
        if (containerConfig?.target) {
            targetSelect.value = containerConfig.target
        } else {
            targetSelect.value = ''
        }

        if (containerConfig?.on_incompatible_codec && onIncompatibleSelect) {
            onIncompatibleSelect.value = containerConfig.on_incompatible_codec
        } else if (onIncompatibleSelect) {
            onIncompatibleSelect.value = 'error'
        }

        if (preserveMetadataCheckbox) {
            preserveMetadataCheckbox.checked = containerConfig?.preserve_metadata !== false
        }

        updateVisibility()
    }

    // Attach event listeners
    targetSelect.addEventListener('change', () => {
        updateVisibility()
        notifyUpdate()
    })

    if (onIncompatibleSelect) {
        onIncompatibleSelect.addEventListener('change', notifyUpdate)
    }

    if (preserveMetadataCheckbox) {
        preserveMetadataCheckbox.addEventListener('change', notifyUpdate)
    }

    // Set initial values
    setInitialValues()

    // Return controller
    return {
        /**
         * Get current container configuration
         * @returns {Object|null} Container config or null if not configured
         */
        getConfig() {
            return getConfig()
        },

        /**
         * Set container configuration
         * @param {Object|null} config - Container config
         */
        setConfig(config) {
            containerConfig = config || null
            setInitialValues()
        },

        /**
         * Refresh the UI with current policy data
         * @param {Object} policyData - Policy data
         */
        refresh(policyData) {
            containerConfig = policyData.container || null
            setInitialValues()
        }
    }
}
