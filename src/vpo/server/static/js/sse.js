/**
 * VPO Server-Sent Events (SSE) Module
 *
 * Provides real-time updates via SSE with automatic fallback to polling.
 * Integrates with VPOPolling for connection status management.
 */

(function () {
    'use strict'

    // ==========================================================================
    // Configuration
    // ==========================================================================

    var CONFIG = {
        /** Default SSE endpoint for jobs */
        JOBS_ENDPOINT: '/api/events/jobs',

        /** Reconnect delay after SSE error (ms) */
        RECONNECT_DELAY: 5000,

        /** Maximum reconnect attempts before falling back to polling */
        MAX_RECONNECT_ATTEMPTS: 3,

        /** Heartbeat timeout - consider disconnected if no message for this long (ms) */
        HEARTBEAT_TIMEOUT: 30000
    }

    // ==========================================================================
    // Debug Logging
    // ==========================================================================

    var DEBUG = false

    /**
     * Log debug messages if DEBUG is enabled.
     * @param {...*} args - Arguments to log
     */
    function log() {
        if (DEBUG) {
            var args = Array.prototype.slice.call(arguments)
            args.unshift('[SSE]')
            // eslint-disable-next-line no-console
            console.log.apply(console, args)
        }
    }

    // ==========================================================================
    // SSE Client Class
    // ==========================================================================

    /**
     * SSE client with automatic reconnection and polling fallback.
     * @constructor
     * @param {Object} options - Configuration options
     * @param {string} options.endpoint - SSE endpoint URL
     * @param {Function} options.onUpdate - Callback for data updates
     * @param {Function} [options.onStatusChange] - Callback for connection status changes
     * @param {Function} [options.fallbackFetchFn] - Polling fetch function for fallback
     */
    function SSEClient(options) {
        this.endpoint = options.endpoint
        this.onUpdate = options.onUpdate
        this.onStatusChange = options.onStatusChange || function () {}
        this.fallbackFetchFn = options.fallbackFetchFn

        this.eventSource = null
        this.reconnectAttempts = 0
        this.isActive = false
        this.useFallback = false
        this.pollingInstance = null
        this.heartbeatTimer = null
        this.reconnectTimer = null
        this.lastEventTime = null
    }

    /**
     * Start the SSE connection.
     */
    SSEClient.prototype.start = function () {
        if (this.isActive) {
            log('SSE already active')
            return
        }

        this.isActive = true
        this.useFallback = false
        this.reconnectAttempts = 0
        log('Starting SSE connection to', this.endpoint)

        this._connect()
    }

    /**
     * Stop the SSE connection.
     */
    SSEClient.prototype.stop = function () {
        this.isActive = false
        this._disconnect()
        this._stopFallbackPolling()
        log('SSE stopped')
    }

    /**
     * Clean up all resources.
     */
    SSEClient.prototype.cleanup = function () {
        this.stop()
        this.onUpdate = function () {}
        this.onStatusChange = function () {}
    }

    /**
     * Check if using SSE (vs fallback polling).
     * @returns {boolean} True if SSE is active
     */
    SSEClient.prototype.isUsingSSE = function () {
        return this.isActive && !this.useFallback && this.eventSource !== null
    }

    /**
     * Internal: Connect to SSE endpoint.
     * @private
     */
    SSEClient.prototype._connect = function () {
        var self = this

        if (!this.isActive) {
            return
        }

        // Check for EventSource support
        if (typeof EventSource === 'undefined') {
            log('EventSource not supported, falling back to polling')
            this._startFallbackPolling()
            return
        }

        try {
            this.eventSource = new EventSource(this.endpoint)

            this.eventSource.onopen = function () {
                log('SSE connection opened')
                self.reconnectAttempts = 0
                self._resetHeartbeatTimer()
                self.onStatusChange('connected')
            }

            this.eventSource.onerror = function (e) {
                log('SSE error:', e)
                self._handleError()
            }

            // Listen for jobs_update events
            this.eventSource.addEventListener('jobs_update', function (e) {
                self._resetHeartbeatTimer()
                try {
                    var data = JSON.parse(e.data)
                    self.onUpdate(data)
                } catch (err) {
                    log('Error parsing SSE data:', err)
                }
            })

            // Listen for heartbeat events
            this.eventSource.addEventListener('heartbeat', function () {
                self._resetHeartbeatTimer()
                log('Heartbeat received')
            })

        } catch (err) {
            log('Error creating EventSource:', err)
            this._handleError()
        }
    }

    /**
     * Internal: Disconnect from SSE endpoint.
     * @private
     */
    SSEClient.prototype._disconnect = function () {
        if (this.eventSource) {
            this.eventSource.close()
            this.eventSource = null
        }
        this._clearTimers()
    }

    /**
     * Internal: Clear all timers.
     * @private
     */
    SSEClient.prototype._clearTimers = function () {
        if (this.heartbeatTimer) {
            clearTimeout(this.heartbeatTimer)
            this.heartbeatTimer = null
        }
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer)
            this.reconnectTimer = null
        }
    }

    /**
     * Internal: Reset heartbeat timeout timer.
     * @private
     */
    SSEClient.prototype._resetHeartbeatTimer = function () {
        var self = this

        this.lastEventTime = Date.now()

        if (this.heartbeatTimer) {
            clearTimeout(this.heartbeatTimer)
        }

        this.heartbeatTimer = setTimeout(function () {
            log('Heartbeat timeout - reconnecting')
            self._handleError()
        }, CONFIG.HEARTBEAT_TIMEOUT)
    }

    /**
     * Internal: Handle SSE error.
     * @private
     */
    SSEClient.prototype._handleError = function () {
        var self = this

        this._disconnect()
        this.reconnectAttempts++

        if (!this.isActive) {
            return
        }

        if (this.reconnectAttempts >= CONFIG.MAX_RECONNECT_ATTEMPTS) {
            log('Max reconnect attempts reached, falling back to polling')
            this.onStatusChange('reconnecting')
            this._startFallbackPolling()
            return
        }

        log('Reconnecting in', CONFIG.RECONNECT_DELAY, 'ms (attempt', this.reconnectAttempts, ')')
        this.onStatusChange('reconnecting')

        this.reconnectTimer = setTimeout(function () {
            if (self.isActive) {
                self._connect()
            }
        }, CONFIG.RECONNECT_DELAY)
    }

    /**
     * Internal: Start fallback polling.
     * @private
     */
    SSEClient.prototype._startFallbackPolling = function () {
        var self = this

        if (this.useFallback) {
            return
        }

        this.useFallback = true
        log('Starting fallback polling')

        if (!this.fallbackFetchFn) {
            log('No fallback fetch function provided')
            return
        }

        // Check if VPOPolling is available
        if (typeof window.VPOPolling === 'undefined') {
            log('VPOPolling not available')
            return
        }

        this.pollingInstance = window.VPOPolling.create({
            fetchFn: function () {
                return self.fallbackFetchFn()
                    .then(function (data) {
                        self.onUpdate(data)
                    })
            },
            onStatusChange: function (status) {
                self.onStatusChange(status)
            }
        })

        this.pollingInstance.start()
    }

    /**
     * Internal: Stop fallback polling.
     * @private
     */
    SSEClient.prototype._stopFallbackPolling = function () {
        if (this.pollingInstance) {
            this.pollingInstance.cleanup()
            this.pollingInstance = null
        }
        this.useFallback = false
    }

    // ==========================================================================
    // Public API
    // ==========================================================================

    /**
     * Create an SSE client for jobs updates.
     * @param {Object} options - Configuration options
     * @param {Function} options.onUpdate - Callback for job updates
     * @param {Function} [options.onStatusChange] - Callback for connection status
     * @param {Function} [options.fallbackFetchFn] - Polling fetch function
     * @returns {SSEClient} SSE client instance
     */
    function createJobsSSE(options) {
        return new SSEClient({
            endpoint: CONFIG.JOBS_ENDPOINT,
            onUpdate: options.onUpdate,
            onStatusChange: options.onStatusChange,
            fallbackFetchFn: options.fallbackFetchFn
        })
    }

    // ==========================================================================
    // Export VPOSSE Namespace
    // ==========================================================================

    window.VPOSSE = {
        // Factory
        createJobsSSE: createJobsSSE,

        // Configuration
        CONFIG: CONFIG,

        // Debug
        setDebug: function (enabled) {
            DEBUG = enabled
        }
    }

    log('VPOSSE module initialized')

})()
