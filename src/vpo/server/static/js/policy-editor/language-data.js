/**
 * Language Data Module (256-policy-editor-enhancements T022)
 *
 * Fetches and caches ISO 639-2 language codes for autocomplete suggestions.
 */

let cachedLanguages = null
let loadPromise = null

/**
 * Get the list of ISO 639-2 languages
 * Fetches from server on first call, caches for subsequent calls
 * @returns {Promise<Array<{code: string, name: string}>>}
 */
export async function getLanguages() {
    // Return cached data if available
    if (cachedLanguages) {
        return cachedLanguages
    }

    // If already loading, wait for existing request
    if (loadPromise) {
        return loadPromise
    }

    // Start new fetch request
    loadPromise = fetchLanguages()
    return loadPromise
}

/**
 * Fetch languages from the server
 * @returns {Promise<Array<{code: string, name: string}>>}
 */
async function fetchLanguages() {
    try {
        const response = await fetch('/static/data/iso-639-2.json')
        if (!response.ok) {
            throw new Error(`Failed to load language data: ${response.status}`)
        }
        const data = await response.json()
        cachedLanguages = data.languages || []
        return cachedLanguages
    } catch (error) {
        console.error('Failed to load ISO 639-2 language data:', error)
        // Return common languages as fallback
        cachedLanguages = getDefaultLanguages()
        return cachedLanguages
    } finally {
        loadPromise = null
    }
}

/**
 * Get default language list as fallback
 * @returns {Array<{code: string, name: string}>}
 */
function getDefaultLanguages() {
    return [
        { code: 'eng', name: 'English' },
        { code: 'jpn', name: 'Japanese' },
        { code: 'spa', name: 'Spanish' },
        { code: 'fra', name: 'French' },
        { code: 'deu', name: 'German' },
        { code: 'ita', name: 'Italian' },
        { code: 'por', name: 'Portuguese' },
        { code: 'rus', name: 'Russian' },
        { code: 'zho', name: 'Chinese' },
        { code: 'kor', name: 'Korean' },
        { code: 'und', name: 'Undefined' },
    ]
}

/**
 * Search languages by code or name
 * @param {string} query - Search query (matches code or name prefix)
 * @param {number} limit - Maximum results to return (default: 10)
 * @returns {Promise<Array<{code: string, name: string}>>}
 */
export async function searchLanguages(query, limit = 10) {
    const languages = await getLanguages()
    const normalizedQuery = query.toLowerCase().trim()

    if (!normalizedQuery) {
        // Return first N languages when no query
        return languages.slice(0, limit)
    }

    // Filter by code or name match
    const matches = languages.filter(lang =>
        lang.code.toLowerCase().startsWith(normalizedQuery) ||
        lang.name.toLowerCase().startsWith(normalizedQuery) ||
        lang.name.toLowerCase().includes(normalizedQuery)
    )

    // Sort: exact code matches first, then code prefix, then name matches
    matches.sort((a, b) => {
        const aCodeExact = a.code.toLowerCase() === normalizedQuery
        const bCodeExact = b.code.toLowerCase() === normalizedQuery
        if (aCodeExact && !bCodeExact) return -1
        if (bCodeExact && !aCodeExact) return 1

        const aCodePrefix = a.code.toLowerCase().startsWith(normalizedQuery)
        const bCodePrefix = b.code.toLowerCase().startsWith(normalizedQuery)
        if (aCodePrefix && !bCodePrefix) return -1
        if (bCodePrefix && !aCodePrefix) return 1

        return a.name.localeCompare(b.name)
    })

    return matches.slice(0, limit)
}

/**
 * Get language name by code
 * @param {string} code - ISO 639-2 language code
 * @returns {Promise<string|null>} Language name or null if not found
 */
export async function getLanguageName(code) {
    const languages = await getLanguages()
    const lang = languages.find(l => l.code.toLowerCase() === code.toLowerCase())
    return lang ? lang.name : null
}

/**
 * Check if a language code is valid
 * @param {string} code - Language code to check
 * @returns {Promise<boolean>} True if code exists in the language list
 */
export async function isValidLanguageCode(code) {
    const languages = await getLanguages()
    return languages.some(l => l.code.toLowerCase() === code.toLowerCase())
}
