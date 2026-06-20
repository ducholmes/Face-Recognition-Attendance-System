/**
 * Authentication utilities for Face Attendance System
 * Handles token management, user session, and protected routes
 */

const AUTH_CONFIG = {
    API_BASE: window.location.origin.replace(':5001', ':8000'),
    TOKEN_KEY: 'access_token',
    REFRESH_TOKEN_KEY: 'refresh_token',
    USER_KEY: 'user'
};

// Authentication Manager
class AuthManager {
    constructor() {
        this.token = localStorage.getItem(AUTH_CONFIG.TOKEN_KEY) || sessionStorage.getItem(AUTH_CONFIG.TOKEN_KEY);
        this.refreshToken = localStorage.getItem(AUTH_CONFIG.REFRESH_TOKEN_KEY) || sessionStorage.getItem(AUTH_CONFIG.REFRESH_TOKEN_KEY);
        this.user = this.getUser();
    }

    // Get current user from storage
    getUser() {
        const userStr = localStorage.getItem(AUTH_CONFIG.USER_KEY) || sessionStorage.getItem(AUTH_CONFIG.USER_KEY);
        if (userStr) {
            try {
                return JSON.parse(userStr);
            } catch (e) {
                console.error('Error parsing user data:', e);
                return null;
            }
        }
        return null;
    }

    // Check if user is authenticated
    isAuthenticated() {
        return !!this.token && !!this.user;
    }

    // Get access token
    getToken() {
        return this.token;
    }

    // Save authentication data
    saveAuth(accessToken, refreshToken, user, rememberMe = true) {
        this.token = accessToken;
        this.refreshToken = refreshToken;
        this.user = user;

        const storage = rememberMe ? localStorage : sessionStorage;
        storage.setItem(AUTH_CONFIG.TOKEN_KEY, accessToken);
        storage.setItem(AUTH_CONFIG.REFRESH_TOKEN_KEY, refreshToken);
        storage.setItem(AUTH_CONFIG.USER_KEY, JSON.stringify(user));
    }

    // Clear authentication data
    clearAuth() {
        this.token = null;
        this.refreshToken = null;
        this.user = null;

        localStorage.removeItem(AUTH_CONFIG.TOKEN_KEY);
        localStorage.removeItem(AUTH_CONFIG.REFRESH_TOKEN_KEY);
        localStorage.removeItem(AUTH_CONFIG.USER_KEY);
        localStorage.removeItem('remember_me');

        sessionStorage.removeItem(AUTH_CONFIG.TOKEN_KEY);
        sessionStorage.removeItem(AUTH_CONFIG.REFRESH_TOKEN_KEY);
        sessionStorage.removeItem(AUTH_CONFIG.USER_KEY);
    }

    // Logout
    async logout() {
        try {
            // Call logout endpoint if needed
            await fetch('/auth/logout', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            });
        } catch (error) {
            console.error('Logout error:', error);
        } finally {
            this.clearAuth();
            window.location.href = '/auth/login';
        }
    }

    // Check user role
    hasRole(role) {
        return this.user && this.user.role === role;
    }

    // Check if user has any of the specified roles
    hasAnyRole(roles) {
        return this.user && roles.includes(this.user.role);
    }

    // Get authorization header
    getAuthHeader() {
        return {
            'Authorization': `Bearer ${this.token}`,
            'Content-Type': 'application/json'
        };
    }

    // Make authenticated API request
    async apiRequest(url, options = {}) {
        const defaultOptions = {
            headers: this.getAuthHeader()
        };

        const mergedOptions = {
            ...defaultOptions,
            ...options,
            headers: {
                ...defaultOptions.headers,
                ...(options.headers || {})
            }
        };

        try {
            const response = await fetch(url, mergedOptions);
            
            // Handle unauthorized
            if (response.status === 401) {
                this.clearAuth();
                window.location.href = '/auth/login';
                throw new Error('Unauthorized');
            }

            return response;
        } catch (error) {
            console.error('API request error:', error);
            throw error;
        }
    }
}

// Create global auth manager instance
const authManager = new AuthManager();

// Initialize authentication on page load
document.addEventListener('DOMContentLoaded', function() {
    // Check if on protected page (KHÔNG bao gồm /attendance - cho phép truy cập tự do)
    const protectedPages = ['/dashboard', '/students', '/register', '/student', '/attendance/history', '/settings'];
    const currentPath = window.location.pathname;
    
    const isProtectedPage = protectedPages.some(page => currentPath.startsWith(page));
    
    if (isProtectedPage) {
        // Check authentication
        if (!authManager.isAuthenticated()) {
            window.location.href = '/auth/login';
            return;
        }

        // Update UI with user info
        updateUserUI();

        // Setup logout button
        const logoutBtn = document.getElementById('logoutBtn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', function(e) {
                e.preventDefault();
                authManager.logout();
            });
        }
    }

    // If on login/register page and already authenticated, redirect
    const authPages = ['/auth/login', '/auth/register'];
    if (authPages.includes(currentPath) && authManager.isAuthenticated()) {
        const user = authManager.getUser();
        if (user.role === 'admin' || user.role === 'teacher') {
            window.location.href = '/dashboard';
        } else if (user.role === 'student') {
            window.location.href = '/student/profile';
        }
    }

    // Redirect students away from admin/teacher pages (KHÔNG bao gồm /attendance)
    const adminTeacherPages = ['/dashboard', '/students', '/attendance/history', '/settings'];
    if (authManager.isAuthenticated()) {
        const user = authManager.getUser();
        const isAdminTeacherPage = adminTeacherPages.some(page => currentPath.startsWith(page));
        
        if (user.role === 'student' && isAdminTeacherPage) {
            window.location.href = '/student/profile';
            return;
        }
        
        // Redirect admin/teacher away from student pages
        const studentPages = ['/student/profile', '/student/register'];
        const isStudentPage = studentPages.some(page => currentPath.startsWith(page));
        
        if ((user.role === 'admin' || user.role === 'teacher') && isStudentPage) {
            window.location.href = '/dashboard';
            return;
        }
    }
});

// Update UI with user information
function updateUserUI() {
    const user = authManager.getUser();
    if (!user) return;

    // Update user email
    const userEmailEl = document.getElementById('userEmail');
    if (userEmailEl) {
        userEmailEl.textContent = user.email;
    }

    // Update user role
    const userRoleEl = document.getElementById('userRole');
    if (userRoleEl) {
        const roleNames = {
            'admin': 'Quản trị viên',
            'teacher': 'Giáo viên',
            'student': 'Học sinh'
        };
        userRoleEl.textContent = roleNames[user.role] || user.role;
    }

    // Hide/show elements based on role
    updateRoleBasedUI(user.role);
}

// Update UI elements based on user role
function updateRoleBasedUI(role) {
    // Hide admin-only features for non-admin users
    if (role !== 'admin') {
        const adminOnlyElements = document.querySelectorAll('[data-role="admin"], [data-role-required="admin"]');
        adminOnlyElements.forEach(el => {
            el.style.display = 'none';
        });
    }

    // Hide teacher features for students
    if (role === 'student') {
        const teacherElements = document.querySelectorAll('[data-role="teacher"]');
        teacherElements.forEach(el => {
            el.style.display = 'none';
        });
    }
}

// Show toast notification
function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) return;

    const toastId = 'toast-' + Date.now();
    const bgClass = {
        'success': 'bg-success',
        'error': 'bg-danger',
        'warning': 'bg-warning',
        'info': 'bg-info'
    }[type] || 'bg-info';

    const toastHTML = `
        <div id="${toastId}" class="toast align-items-center text-white ${bgClass} border-0" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    `;

    toastContainer.insertAdjacentHTML('beforeend', toastHTML);
    
    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, { delay: 3000 });
    toast.show();

    // Remove toast element after it's hidden
    toastElement.addEventListener('hidden.bs.toast', function() {
        toastElement.remove();
    });
}

// Export for use in other scripts
window.authManager = authManager;
window.showToast = showToast;
