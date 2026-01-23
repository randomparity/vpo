/**
 * Policy JSON Schema Validator (256-policy-editor-enhancements T033)
 *
 * Provides client-side JSON Schema validation using Ajv library.
 * Fetches schema from /api/policies/schema endpoint and validates policy data.
 */

let cachedSchema = null
let cachedValidator = null

/**
 * Fetch the JSON Schema from the server
 * @returns {Promise<{schemaVersion: number, jsonSchema: object}>}
 */
export async function loadSchema() {
    if (cachedSchema) {
        return cachedSchema
    }

    try {
        const response = await fetch('/api/policies/schema')
        if (!response.ok) {
            throw new Error(`Failed to load schema: ${response.status}`)
        }
        const data = await response.json()
        cachedSchema = {
            schemaVersion: data.schema_version,
            jsonSchema: data.json_schema,
        }
        return cachedSchema
    } catch (error) {
        console.error('Failed to load policy schema:', error)
        return null
    }
}

/**
 * Create a validator function from the schema
 * Uses the global Ajv object loaded from CDN
 * @param {object} schema - JSON Schema object
 * @returns {function|null} Compiled validator function or null if Ajv not available
 */
export function createValidator(schema) {
    // Check if Ajv is available (loaded from CDN)
    if (typeof Ajv === 'undefined') {
        console.warn('Ajv library not loaded, client-side validation disabled')
        return null
    }

    try {
        const ajv = new Ajv({
            allErrors: true,      // Collect all errors, not just first
            verbose: true,        // Include schema and data in errors
            strict: false,        // Allow additional properties not in schema
            validateFormats: false, // Don't validate string formats
        })
        return ajv.compile(schema)
    } catch (error) {
        console.error('Failed to compile JSON Schema:', error)
        return null
    }
}

/**
 * Get or create the cached validator
 * @returns {Promise<function|null>} Validator function or null
 */
export async function getValidator() {
    if (cachedValidator) {
        return cachedValidator
    }

    const schemaData = await loadSchema()
    if (!schemaData) {
        return null
    }

    cachedValidator = createValidator(schemaData.jsonSchema)
    return cachedValidator
}

/**
 * Validate policy data against the JSON Schema
 * @param {function} validator - Compiled Ajv validator function
 * @param {object} policyData - Policy data to validate
 * @returns {{valid: boolean, errors: Array<{field: string, message: string, code: string}>}}
 */
export function validatePolicy(validator, policyData) {
    if (!validator) {
        // No validator available, assume valid (server will validate)
        return { valid: true, errors: [] }
    }

    const valid = validator(policyData)

    if (valid) {
        return { valid: true, errors: [] }
    }

    // Convert Ajv errors to our error format
    const errors = (validator.errors || []).map(err => {
        // Build field path from instancePath (e.g., "/phases/0/name" -> "phases[0].name")
        let field = err.instancePath
            .replace(/^\//, '')           // Remove leading slash
            .replace(/\//g, '.')           // Replace slashes with dots
            .replace(/\.(\d+)\./g, '[$1].') // Convert array indices
            .replace(/\.(\d+)$/, '[$1]')    // Handle trailing array index

        // For root-level errors, use the field from params
        if (!field && err.params && err.params.missingProperty) {
            field = err.params.missingProperty
        }

        // Build human-readable message
        let message = err.message || 'Invalid value'

        // Enhance message based on keyword
        if (err.keyword === 'required') {
            message = `Missing required field: ${err.params?.missingProperty || 'unknown'}`
        } else if (err.keyword === 'type') {
            message = `Expected ${err.params?.type || 'different type'}`
        } else if (err.keyword === 'enum') {
            const allowed = err.params?.allowedValues?.join(', ') || 'specific values'
            message = `Must be one of: ${allowed}`
        } else if (err.keyword === 'minItems') {
            message = `Must have at least ${err.params?.limit || 1} item(s)`
        } else if (err.keyword === 'pattern') {
            message = 'Invalid format'
        }

        return {
            field: field || 'root',
            message: message,
            code: err.keyword || 'validation_error'
        }
    })

    // Deduplicate errors by field+message
    const seen = new Set()
    const uniqueErrors = errors.filter(err => {
        const key = `${err.field}:${err.message}`
        if (seen.has(key)) {
            return false
        }
        seen.add(key)
        return true
    })

    return { valid: false, errors: uniqueErrors }
}

/**
 * Convenience function to validate policy data
 * Loads schema and creates validator if needed
 * @param {object} policyData - Policy data to validate
 * @returns {Promise<{valid: boolean, errors: Array}>}
 */
export async function validatePolicyData(policyData) {
    const validator = await getValidator()
    return validatePolicy(validator, policyData)
}
