/**
 * app.js - Shared utility functions cho hệ thống điểm danh
 * Dùng global functions (không có ES modules)
 */

/**
 * Vô hiệu hóa / kích hoạt nút và hiển thị / ẩn spinner
 * @param {HTMLButtonElement} btn
 * @param {boolean} isLoading
 */
function setButtonLoading(btn, isLoading) {
    btn.disabled = isLoading;
    const spinner = btn.querySelector('.btn-spinner');
    const text = btn.querySelector('.btn-text');
    if (spinner) spinner.classList.toggle('d-none', !isLoading);
    if (text) text.classList.toggle('d-none', isLoading);
}

/**
 * Hiển thị Bootstrap toast ở góc màn hình, tự ẩn sau 3 giây
 * @param {string} message
 * @param {'success'|'danger'|'warning'|'info'} type
 */
function showToast(message, type = 'success') {
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        container.style.zIndex = '1100';
        document.body.appendChild(container);
    }

    const toastId = 'toast-' + Date.now();
    const iconMap = {
        success: '✓',
        danger: '✕',
        warning: '⚠',
        info: 'ℹ'
    };
    const icon = iconMap[type] || '✓';

    const toastEl = document.createElement('div');
    toastEl.id = toastId;
    toastEl.className = `toast align-items-center text-bg-${type} border-0`;
    toastEl.setAttribute('role', 'alert');
    toastEl.setAttribute('aria-live', 'assertive');
    toastEl.setAttribute('aria-atomic', 'true');
    toastEl.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                <strong>${icon}</strong> ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto"
                    data-bs-dismiss="toast" aria-label="Đóng"></button>
        </div>`;

    container.appendChild(toastEl);

    // Dùng Bootstrap Toast nếu có, fallback tự xử lý
    if (window.bootstrap && window.bootstrap.Toast) {
        const bsToast = new window.bootstrap.Toast(toastEl, { delay: 3000 });
        bsToast.show();
        toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
    } else {
        toastEl.style.display = 'block';
        setTimeout(() => toastEl.remove(), 3000);
    }
}

/**
 * Hiển thị thông báo lỗi inline trong container với nút đóng
 * @param {HTMLElement} container
 * @param {string} message
 */
function showInlineError(container, message) {
    container.innerHTML = `
        <div class="alert alert-danger alert-dismissible fade show" role="alert">
            <i class="bi bi-exclamation-triangle-fill me-2"></i>${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"
                    aria-label="Đóng"></button>
        </div>`;
}

/**
 * Xóa thông báo lỗi inline trong container
 * @param {HTMLElement} container
 */
function clearInlineError(container) {
    container.innerHTML = '';
}

/**
 * Wrapper cho fetch với xử lý HTTP 401 tập trung
 * Tự động đính Authorization header từ localStorage nếu có token.
 * @param {string} url
 * @param {RequestInit} options
 * @returns {Promise<Response|undefined>}
 */
async function apiFetch(url, options = {}) {
    // Lấy token từ localStorage
    const token = localStorage.getItem('access_token');
    console.log(`[apiFetch] ${url} | token: ${token ? token.substring(0, 20) + '...' : 'NULL - không có token'}`);

    // Xây dựng headers: bắt đầu với Content-Type, thêm Authorization nếu có token
    const defaultHeaders = { 'Content-Type': 'application/json' };
    if (token) {
        defaultHeaders['Authorization'] = `Bearer ${token}`;
    }

    // Merge với headers do caller truyền vào (caller có thể override)
    // defaultHeaders là base, caller headers được merge vào SAU
    // nhưng Authorization từ token KHÔNG bị caller override
    const callerHeaders = options.headers || {};
    options.headers = {
        ...callerHeaders,
        ...defaultHeaders,  // Authorization luôn thắng nếu có token
    };

    console.log(`[apiFetch] headers gửi đi:`, JSON.stringify(options.headers));

    try {
        const res = await fetch(url, options);
        if (res.status === 401) {
            window.location.href = '/auth/login?expired=1';
            return undefined;
        }
        return res;
    } catch (err) {
        // Network error
        throw new Error('Không thể kết nối đến server. Vui lòng kiểm tra kết nối mạng.');
    }
}

/**
 * Lấy ngày hôm nay theo định dạng YYYY-MM-DD
 * @returns {string}
 */
function getTodayDate() {
    const d = new Date();
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
}

/**
 * Format thời gian từ ISO string hoặc HH:MM
 * @param {string|null} timeStr
 * @returns {string}
 */
function formatTime(timeStr) {
    if (!timeStr) return '—';
    return timeStr;
}
