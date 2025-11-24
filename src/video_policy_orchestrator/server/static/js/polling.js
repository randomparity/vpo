/**
 * VPO Polling Module
 *
 * Provides shared polling utilities for live job status updates.
 * Implements exponential backoff, visibility-aware polling, and
 * connection status management.
 */

(function() {
    'use strict';

    // ==========================================================================
    // Configuration Constants (T002)
    // ==========================================================================

    /**
     * Default polling configuration.
     * Can be overridden via data attributes on <body>.
     */
    var CONFIG = {
        /** Default polling interval in milliseconds */
        DEFAULT_INTERVAL: 5000,

        /** Log polling interval in milliseconds */
        LOG_INTERVAL: 15000,

        /** Minimum allowed polling interval */
        MIN_INTERVAL: 2000,

        /** Maximum allowed polling interval */
        MAX_INTERVAL: 60000
    };

    /**
     * Exponential backoff configuration.
     */
    var BACKOFF = {
        /** Initial delay after starting backoff (10 seconds) */
        INITIAL_DELAY: 10000,

        /** Maximum delay during backoff (2 minutes) */
        MAX_DELAY: 120000,

        /** Number of consecutive failures before starting backoff */
        FAILURES_BEFORE_BACKOFF: 3,

        /** Multiplier for delay increase */
        MULTIPLIER: 2
    };

    /**
     * Connection status values.
     */
    var CONNECTION_STATUS = {
        CONNECTED: 'connected',
        RECONNECTING: 'reconnecting',
        ERROR: 'error'
    };

    // ==========================================================================
    // Debug Logging
    // ==========================================================================

    var DEBUG = false;

    /**
     * Log debug messages if DEBUG is enabled.
     * @param {...*} args - Arguments to log
     */
    function log() {
        if (DEBUG) {
            var args = Array.prototype.slice.call(arguments);
            args.unshift('[Polling]');
            console.log.apply(console, args);
        }
    }

    // ==========================================================================
    // BackoffState Class (T005)
    // ==========================================================================

    /**
     * Tracks exponential backoff state for error recovery.
     * @constructor
     */
    function BackoffState() {
        this.errorCount = 0;
        this.currentDelay = 0;
        this.lastSuccessTime = null;
        this.lastErrorTime = null;
    }

    /**
     * Record a successful request, resetting backoff state.
     */
    BackoffState.prototype.recordSuccess = function() {
        this.errorCount = 0;
        this.currentDelay = 0;
        this.lastSuccessTime = Date.now();
        log('Backoff reset on success');
    };

    /**
     * Record a failed request, updating backoff state.
     */
    BackoffState.prototype.recordError = function() {
        this.errorCount++;
        this.lastErrorTime = Date.now();

        if (this.errorCount >= BACKOFF.FAILURES_BEFORE_BACKOFF) {
            var backoffErrors = this.errorCount - BACKOFF.FAILURES_BEFORE_BACKOFF;
            this.currentDelay = Math.min(
                BACKOFF.INITIAL_DELAY * Math.pow(BACKOFF.MULTIPLIER, backoffErrors),
                BACKOFF.MAX_DELAY
            );
        }

        log('Backoff error count:', this.errorCount, 'delay:', this.currentDelay);
    };

    /**
     * Calculate the next polling delay based on backoff state.
     * @param {number} baseInterval - Base polling interval
     * @returns {number} Delay in milliseconds
     */
    BackoffState.prototype.getDelay = function(baseInterval) {
        if (this.currentDelay > 0) {
            return this.currentDelay;
        }
        return baseInterval;
    };

    /**
     * Check if currently in backoff state.
     * @returns {boolean} True if in backoff
     */
    BackoffState.prototype.isInBackoff = function() {
        return this.errorCount >= BACKOFF.FAILURES_BEFORE_BACKOFF;
    };

    // ==========================================================================
    // PollingState Class (T004)
    // ==========================================================================

    /**
     * Runtime state for an active polling loop.
     * @constructor
     * @param {Object} options - Configuration options
     * @param {number} options.interval - Polling interval in milliseconds
     * @param {Function} options.fetchFn - Async function to fetch data
     * @param {Function} [options.onStatusChange] - Callback for connection status changes
     */
    function PollingState(options) {
        this.interval = options.interval || CONFIG.DEFAULT_INTERVAL;
        this.fetchFn = options.fetchFn;
        this.onStatusChange = options.onStatusChange || function() {};

        this.isActive = false;
        this.isVisible = !document.hidden;
        this.timerId = null;
        this.backoff = new BackoffState();
        this.connectionStatus = CONNECTION_STATUS.CONNECTED;
        this.lastFetchTime = null;
        this._isPaused = false;
    }

    /**
     * Start the polling loop.
     */
    PollingState.prototype.start = function() {
        if (this.isActive) {
            log('Polling already active');
            return;
        }

        this.isActive = true;
        this._isPaused = false;
        log('Polling started with interval:', this.interval);

        // Fetch immediately on start
        this._poll();
    };

    /**
     * Stop the polling loop.
     */
    PollingState.prototype.stop = function() {
        this.isActive = false;
        this._clearTimer();
        log('Polling stopped');
    };

    /**
     * Pause polling (e.g., when tab becomes hidden).
     */
    PollingState.prototype.pause = function() {
        if (!this.isActive || this._isPaused) {
            return;
        }

        this._isPaused = true;
        this._clearTimer();
        log('Polling paused');
    };

    /**
     * Resume polling (e.g., when tab becomes visible).
     * Fetches immediately on resume.
     */
    PollingState.prototype.resume = function() {
        if (!this.isActive || !this._isPaused) {
            return;
        }

        this._isPaused = false;
        log('Polling resumed');

        // Fetch immediately on resume
        this._poll();
    };

    /**
     * Clean up all resources.
     */
    PollingState.prototype.cleanup = function() {
        this.stop();
        this.backoff = new BackoffState();
        this.connectionStatus = CONNECTION_STATUS.CONNECTED;
        log('Polling cleaned up');
    };

    /**
     * Internal: Clear the polling timer.
     * @private
     */
    PollingState.prototype._clearTimer = function() {
        if (this.timerId !== null) {
            clearTimeout(this.timerId);
            this.timerId = null;
        }
    };

    /**
     * Internal: Execute a single poll cycle.
     * @private
     */
    PollingState.prototype._poll = function() {
        var self = this;

        if (!this.isActive || this._isPaused) {
            return;
        }

        // Execute the fetch function
        Promise.resolve(this.fetchFn())
            .then(function() {
                self._onSuccess();
            })
            .catch(function(error) {
                self._onError(error);
            })
            .finally(function() {
                self._scheduleNext();
            });
    };

    /**
     * Internal: Handle successful fetch.
     * @private
     */
    PollingState.prototype._onSuccess = function() {
        this.lastFetchTime = Date.now();
        this.backoff.recordSuccess();

        if (this.connectionStatus !== CONNECTION_STATUS.CONNECTED) {
            this.connectionStatus = CONNECTION_STATUS.CONNECTED;
            this.onStatusChange(this.connectionStatus);
            log('Connection restored');
        }
    };

    /**
     * Internal: Handle fetch error.
     * @private
     * @param {Error} error - The error that occurred
     */
    PollingState.prototype._onError = function(error) {
        this.backoff.recordError();
        log('Fetch error:', error.message);

        // Update connection status based on backoff state
        var newStatus = this.backoff.isInBackoff()
            ? CONNECTION_STATUS.ERROR
            : CONNECTION_STATUS.RECONNECTING;

        if (this.connectionStatus !== newStatus) {
            this.connectionStatus = newStatus;
            this.onStatusChange(newStatus);
        }
    };

    /**
     * Internal: Schedule the next poll.
     * @private
     */
    PollingState.prototype._scheduleNext = function() {
        var self = this;

        if (!this.isActive || this._isPaused) {
            return;
        }

        var delay = this.backoff.getDelay(this.interval);
        log('Scheduling next poll in', delay, 'ms');

        this.timerId = setTimeout(function() {
            self._poll();
        }, delay);
    };

    // ==========================================================================
    // Page Visibility API Integration (T006)
    // ==========================================================================

    var visibilityHandlers = [];
    var MAX_HANDLERS = 100;

    /**
     * Register a handler for visibility changes.
     * @param {Function} handler - Function(isVisible) to call on visibility change
     * @returns {Function} Unregister function
     */
    function onVisibilityChange(handler) {
        // Check for duplicate handler
        if (visibilityHandlers.indexOf(handler) !== -1) {
            log('Warning: Duplicate visibility handler registration ignored');
            return function unregister() {};
        }

        // Check handler limit
        if (visibilityHandlers.length >= MAX_HANDLERS) {
            console.warn('[Polling] Maximum visibility handlers reached (' + MAX_HANDLERS + ')');
            return function unregister() {};
        }

        visibilityHandlers.push(handler);

        return function unregister() {
            var index = visibilityHandlers.indexOf(handler);
            if (index > -1) {
                visibilityHandlers.splice(index, 1);
            }
        };
    }

    /**
     * Handle visibility change event.
     * @private
     */
    function handleVisibilityChange() {
        var isVisible = !document.hidden;
        log('Visibility changed:', isVisible ? 'visible' : 'hidden');

        for (var i = 0; i < visibilityHandlers.length; i++) {
            try {
                visibilityHandlers[i](isVisible);
            } catch (e) {
                console.error('[Polling] Visibility handler error:', e);
            }
        }
    }

    // Attach visibility change listener
    document.addEventListener('visibilitychange', handleVisibilityChange);

    // ==========================================================================
    // Connection Status UI (T041)
    // ==========================================================================

    /**
     * Update the connection status indicator in the UI.
     * @param {string} status - One of CONNECTION_STATUS values
     */
    function setConnectionStatus(status) {
        var indicator = document.getElementById('connection-status');
        if (!indicator) {
            return;
        }

        // Update class
        indicator.className = 'connection-status connection-status--' + status;

        // Update title/tooltip
        var titles = {
            'connected': 'Live updates active',
            'reconnecting': 'Reconnecting...',
            'error': 'Connection lost - retrying'
        };
        indicator.setAttribute('title', titles[status] || '');

        // Update aria-label for accessibility
        indicator.setAttribute('aria-label', titles[status] || 'Connection status');

        log('Connection status UI updated:', status);
    }

    // ==========================================================================
    // Configuration Loading (T036, T037)
    // ==========================================================================

    /**
     * Load polling configuration from data attributes on <body>.
     * @returns {Object} Configuration object
     */
    function loadConfig() {
        var body = document.body;
        var config = {
            interval: CONFIG.DEFAULT_INTERVAL,
            enabled: true,
            logInterval: CONFIG.LOG_INTERVAL
        };

        // Read interval from data attribute
        var intervalAttr = body.dataset.pollingInterval;
        if (intervalAttr) {
            var interval = parseInt(intervalAttr, 10);
            if (!isNaN(interval)) {
                // Validate range
                config.interval = Math.max(
                    CONFIG.MIN_INTERVAL,
                    Math.min(CONFIG.MAX_INTERVAL, interval)
                );
            }
        }

        // Read enabled flag
        var enabledAttr = body.dataset.pollingEnabled;
        if (enabledAttr !== undefined) {
            config.enabled = enabledAttr !== 'false';
        }

        // Read log interval
        var logIntervalAttr = body.dataset.pollingLogInterval;
        if (logIntervalAttr) {
            var logInterval = parseInt(logIntervalAttr, 10);
            if (!isNaN(logInterval) && logInterval >= config.interval) {
                config.logInterval = logInterval;
            }
        }

        log('Loaded config:', config);
        return config;
    }

    // ==========================================================================
    // Cleanup on Page Unload (T033)
    // ==========================================================================

    var cleanupHandlers = [];

    /**
     * Register a cleanup handler for page unload.
     * @param {Function} handler - Cleanup function
     * @returns {Function} Unregister function
     */
    function onCleanup(handler) {
        // Check for duplicate handler
        if (cleanupHandlers.indexOf(handler) !== -1) {
            log('Warning: Duplicate cleanup handler registration ignored');
            return function unregister() {};
        }

        // Check handler limit
        if (cleanupHandlers.length >= MAX_HANDLERS) {
            console.warn('[Polling] Maximum cleanup handlers reached (' + MAX_HANDLERS + ')');
            return function unregister() {};
        }

        cleanupHandlers.push(handler);

        return function unregister() {
            var index = cleanupHandlers.indexOf(handler);
            if (index > -1) {
                cleanupHandlers.splice(index, 1);
            }
        };
    }

    /**
     * Handle page unload event.
     * @private
     */
    function handleUnload() {
        log('Page unloading, running cleanup handlers');
        for (var i = 0; i < cleanupHandlers.length; i++) {
            try {
                cleanupHandlers[i]();
            } catch (e) {
                // Ignore errors during cleanup
            }
        }
    }

    // Attach unload listener
    window.addEventListener('beforeunload', handleUnload);

    // ==========================================================================
    // Loading Indicator (T038)
    // ==========================================================================

    /**
     * Show a subtle loading indicator during polling refresh.
     * @param {boolean} show - Whether to show or hide the indicator
     */
    function showLoadingIndicator(show) {
        var indicator = document.getElementById('connection-status');
        if (!indicator) {
            return;
        }

        if (show) {
            indicator.classList.add('connection-status--loading');
        } else {
            indicator.classList.remove('connection-status--loading');
        }
    }

    // ==========================================================================
    // Public API (T010)
    // ==========================================================================

    /**
     * Create a new polling instance.
     * @param {Object} options - Configuration options
     * @param {Function} options.fetchFn - Async function to fetch data
     * @param {number} [options.interval] - Polling interval (defaults to config)
     * @param {Function} [options.onStatusChange] - Connection status callback
     * @returns {PollingState} Polling instance
     */
    function createPolling(options) {
        var config = loadConfig();

        if (!config.enabled) {
            log('Polling disabled by configuration');
            // Return a no-op polling instance
            return {
                start: function() {},
                stop: function() {},
                pause: function() {},
                resume: function() {},
                cleanup: function() {},
                isActive: false
            };
        }

        var polling = new PollingState({
            interval: options.interval || config.interval,
            fetchFn: options.fetchFn,
            onStatusChange: function(status) {
                setConnectionStatus(status);
                if (options.onStatusChange) {
                    options.onStatusChange(status);
                }
            }
        });

        // Register for visibility changes
        var unregisterVisibility = onVisibilityChange(function(isVisible) {
            if (isVisible) {
                polling.resume();
            } else {
                polling.pause();
            }
        });

        // Register cleanup
        var unregisterCleanup = onCleanup(function() {
            polling.cleanup();
        });

        // Wrap cleanup to also unregister handlers
        var originalCleanup = polling.cleanup.bind(polling);
        polling.cleanup = function() {
            unregisterVisibility();
            unregisterCleanup();
            originalCleanup();
        };

        return polling;
    }

    // ==========================================================================
    // Export VPOPolling Namespace
    // ==========================================================================

    window.VPOPolling = {
        // Factory
        create: createPolling,

        // Configuration
        CONFIG: CONFIG,
        BACKOFF: BACKOFF,
        CONNECTION_STATUS: CONNECTION_STATUS,
        loadConfig: loadConfig,

        // Visibility
        onVisibilityChange: onVisibilityChange,

        // Cleanup
        onCleanup: onCleanup,

        // UI
        setConnectionStatus: setConnectionStatus,
        showLoadingIndicator: showLoadingIndicator,

        // Debug
        setDebug: function(enabled) {
            DEBUG = enabled;
        }
    };

    log('VPOPolling module initialized');

})();
