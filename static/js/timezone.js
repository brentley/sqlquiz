/**
 * Timezone utilities for converting UTC timestamps to local time
 */

/**
 * Format a UTC timestamp or ISO string to local time
 * @param {string|number} utcTime - UTC timestamp (epoch) or ISO string
 * @param {Object} options - Formatting options
 * @returns {string} Formatted local time string
 */
function formatLocalTime(utcTime, options = {}) {
    let date;
    
    if (typeof utcTime === 'number') {
        // It's a timestamp
        date = new Date(utcTime * 1000);
    } else {
        // It's an ISO string
        date = new Date(utcTime);
    }
    
    const defaults = {
        showSeconds: false,
        showTimezone: true,
        dateStyle: 'medium',
        timeStyle: 'short'
    };
    
    const opts = { ...defaults, ...options };
    
    if (opts.showSeconds) {
        opts.timeStyle = 'medium';
    }
    
    // Use Intl.DateTimeFormat for proper localization
    const formatter = new Intl.DateTimeFormat(undefined, {
        dateStyle: opts.dateStyle,
        timeStyle: opts.timeStyle,
        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone
    });
    
    let formatted = formatter.format(date);
    
    if (opts.showTimezone) {
        const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
        const shortTz = date.toLocaleTimeString('en', { timeZoneName: 'short' }).split(' ').pop();
        formatted += ` ${shortTz}`;
    }
    
    return formatted;
}

/**
 * Format time as "X minutes/hours/days ago"
 * @param {string|number} utcTime - UTC timestamp or ISO string
 * @returns {string} Relative time string
 */
function formatRelativeTime(utcTime) {
    let date;
    
    if (typeof utcTime === 'number') {
        date = new Date(utcTime * 1000);
    } else {
        date = new Date(utcTime);
    }
    
    const now = new Date();
    const diffMs = now - date;
    const diffSecs = Math.floor(diffMs / 1000);
    const diffMins = Math.floor(diffSecs / 60);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);
    
    if (diffSecs < 60) {
        return 'just now';
    } else if (diffMins < 60) {
        return `${diffMins} minute${diffMins !== 1 ? 's' : ''} ago`;
    } else if (diffHours < 24) {
        return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
    } else if (diffDays < 7) {
        return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
    } else {
        // For older dates, show the actual date
        return formatLocalTime(utcTime, { showTimezone: false });
    }
}

/**
 * Initialize timezone conversion for all elements with data-utc-time attribute
 */
function initTimezoneConversion() {
    // Convert timestamps on page load
    document.querySelectorAll('[data-utc-time]').forEach(element => {
        const utcTime = element.getAttribute('data-utc-time');
        const format = element.getAttribute('data-time-format') || 'absolute';
        const showSeconds = element.hasAttribute('data-show-seconds');
        const showTimezone = !element.hasAttribute('data-hide-timezone');
        
        try {
            if (format === 'relative') {
                element.textContent = formatRelativeTime(utcTime);
            } else {
                element.textContent = formatLocalTime(utcTime, { 
                    showSeconds, 
                    showTimezone 
                });
            }
        } catch (error) {
            console.warn('Failed to format time:', utcTime, error);
            // Keep original text as fallback
        }
    });
}

/**
 * Get current UTC timestamp
 * @returns {number} Current UTC timestamp in seconds
 */
function getCurrentUTCTimestamp() {
    return Math.floor(Date.now() / 1000);
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', initTimezoneConversion);

// Export functions for use in other scripts
window.TimezonUtils = {
    formatLocalTime,
    formatRelativeTime,
    initTimezoneConversion,
    getCurrentUTCTimestamp
};