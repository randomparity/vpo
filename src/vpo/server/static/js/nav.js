/**
 * VPO Web UI - Navigation Enhancement
 *
 * Provides client-side navigation state detection as a fallback
 * for server-side active state rendering.
 */

(function () {
    'use strict'

    /**
     * Apply active class to navigation link matching current path.
     * This serves as a fallback if server-side rendering didn't set the active state.
     */
    function highlightCurrentSection() {
        var currentPath = window.location.pathname
        var navLinks = document.querySelectorAll('.nav-link')

        navLinks.forEach(function (link) {
            var href = link.getAttribute('href')

            // Check if this link matches the current path
            if (href === currentPath ||
                (currentPath === '/' && href === '/jobs')) {
                link.classList.add('active')
                link.setAttribute('aria-current', 'page')
            }
        })
    }

    // Run on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', highlightCurrentSection)
    } else {
        highlightCurrentSection()
    }
})()
