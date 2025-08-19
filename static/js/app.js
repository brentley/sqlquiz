// Common JavaScript functionality for SQLQuiz

// Global utility functions
const SQLQuiz = {
    // Show toast notification
    showToast: function(message, type = 'info', duration = 5000) {
        const toastContainer = this.getToastContainer();
        const toast = this.createToast(message, type);
        
        toastContainer.appendChild(toast);
        
        // Show toast with animation
        setTimeout(() => toast.classList.add('show'), 100);
        
        // Auto remove toast
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 150);
        }, duration);
    },

    // Get or create toast container
    getToastContainer: function() {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'toast-container position-fixed top-0 end-0 p-3';
            container.style.zIndex = '9999';
            document.body.appendChild(container);
        }
        return container;
    },

    // Create toast element
    createToast: function(message, type) {
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${this.getBootstrapColor(type)} border-0`;
        toast.setAttribute('role', 'alert');
        
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    <i class="fas ${this.getIcon(type)} me-2"></i>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" 
                        onclick="this.closest('.toast').remove()"></button>
            </div>
        `;
        
        return toast;
    },

    // Map alert types to Bootstrap colors
    getBootstrapColor: function(type) {
        const colorMap = {
            'success': 'success',
            'error': 'danger',
            'warning': 'warning',
            'info': 'info',
            'danger': 'danger'
        };
        return colorMap[type] || 'info';
    },

    // Map alert types to Font Awesome icons
    getIcon: function(type) {
        const iconMap = {
            'success': 'fa-check-circle',
            'error': 'fa-exclamation-circle',
            'warning': 'fa-exclamation-triangle',
            'info': 'fa-info-circle',
            'danger': 'fa-exclamation-circle'
        };
        return iconMap[type] || 'fa-info-circle';
    },

    // Format SQL query for display
    formatSQL: function(sql) {
        return sql
            .replace(/\b(SELECT|FROM|WHERE|JOIN|INNER JOIN|LEFT JOIN|RIGHT JOIN|GROUP BY|ORDER BY|HAVING|UNION|INSERT|UPDATE|DELETE)\b/gi, '<strong>$1</strong>')
            .replace(/\b(AND|OR|NOT|IN|EXISTS|LIKE|BETWEEN|IS NULL|IS NOT NULL)\b/gi, '<em>$1</em>');
    },

    // Copy text to clipboard
    copyToClipboard: async function(text, successMessage = 'Copied to clipboard!') {
        try {
            await navigator.clipboard.writeText(text);
            this.showToast(successMessage, 'success', 2000);
        } catch (err) {
            console.error('Failed to copy: ', err);
            this.showToast('Failed to copy to clipboard', 'error');
        }
    },

    // Debounce function for search inputs
    debounce: function(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    // Format file size
    formatFileSize: function(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },

    // Format number with commas
    formatNumber: function(num) {
        return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    },

    // Validate SQL query (basic validation)
    validateSQL: function(sql) {
        const trimmed = sql.trim().toUpperCase();
        
        // Must start with SELECT
        if (!trimmed.startsWith('SELECT')) {
            return {
                valid: false,
                error: 'Query must start with SELECT'
            };
        }
        
        // Check for dangerous keywords
        const dangerous = ['DELETE', 'DROP', 'ALTER', 'INSERT', 'UPDATE', 'CREATE'];
        for (const keyword of dangerous) {
            if (trimmed.includes(keyword)) {
                return {
                    valid: false,
                    error: `Query contains prohibited keyword: ${keyword}`
                };
            }
        }
        
        // Basic syntax check - must contain FROM
        if (!trimmed.includes('FROM')) {
            return {
                valid: false,
                error: 'Query must contain FROM clause'
            };
        }
        
        return { valid: true };
    },

    // Get query execution time
    startTimer: function() {
        return performance.now();
    },

    endTimer: function(startTime) {
        const endTime = performance.now();
        const duration = endTime - startTime;
        
        if (duration < 1000) {
            return Math.round(duration) + ' ms';
        } else {
            return (duration / 1000).toFixed(2) + ' s';
        }
    },

    // Local storage helpers
    saveToLocalStorage: function(key, data) {
        try {
            localStorage.setItem(key, JSON.stringify(data));
        } catch (e) {
            console.error('Failed to save to localStorage:', e);
        }
    },

    loadFromLocalStorage: function(key, defaultValue = null) {
        try {
            const item = localStorage.getItem(key);
            return item ? JSON.parse(item) : defaultValue;
        } catch (e) {
            console.error('Failed to load from localStorage:', e);
            return defaultValue;
        }
    },

    // Export results to CSV
    exportToCSV: function(data, filename = 'query_results.csv') {
        if (!data || !data.columns || !data.results) {
            this.showToast('No data to export', 'warning');
            return;
        }

        // Create CSV content
        let csv = data.columns.join(',') + '\n';
        
        data.results.forEach(row => {
            const values = data.columns.map(col => {
                const value = row[col];
                if (value === null || value === undefined) {
                    return '';
                }
                // Escape commas and quotes
                if (typeof value === 'string' && (value.includes(',') || value.includes('"'))) {
                    return '"' + value.replace(/"/g, '""') + '"';
                }
                return value;
            });
            csv += values.join(',') + '\n';
        });

        // Create download link
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        
        link.setAttribute('href', url);
        link.setAttribute('download', filename);
        link.style.visibility = 'hidden';
        
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        this.showToast('CSV exported successfully!', 'success');
    }
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Add keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl+/ or Cmd+/ for help
        if ((e.ctrlKey || e.metaKey) && e.key === '/') {
            e.preventDefault();
            // Show help modal if it exists
            const helpModal = document.getElementById('helpModal');
            if (helpModal) {
                new bootstrap.Modal(helpModal).show();
            }
        }
    });

    // Add loading states to forms
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function() {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.classList.add('loading');
                submitBtn.disabled = true;
            }
        });
    });

    // Add copy buttons to code blocks
    const codeBlocks = document.querySelectorAll('code');
    codeBlocks.forEach(block => {
        if (block.textContent.length > 20) { // Only add to longer code blocks
            block.style.position = 'relative';
            const copyBtn = document.createElement('button');
            copyBtn.className = 'btn btn-sm btn-outline-secondary copy-btn';
            copyBtn.style.cssText = 'position: absolute; top: 5px; right: 5px; font-size: 12px; padding: 2px 6px;';
            copyBtn.innerHTML = '<i class="fas fa-copy"></i>';
            copyBtn.onclick = () => SQLQuiz.copyToClipboard(block.textContent);
            
            const wrapper = document.createElement('div');
            wrapper.style.position = 'relative';
            wrapper.style.display = 'inline-block';
            
            block.parentNode.insertBefore(wrapper, block);
            wrapper.appendChild(block);
            wrapper.appendChild(copyBtn);
        }
    });

    // Add tooltips to buttons with title attributes
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[title]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

// Make SQLQuiz globally available
window.SQLQuiz = SQLQuiz;