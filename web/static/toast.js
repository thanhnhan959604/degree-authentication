/**
 * GovTech Toast Notification System
 * Trường Đại học Kỹ thuật - Công nghệ Cần Thơ (CTUT)
 * Hiển thị thông báo Toast ở góc phải trên màn hình (Top-Right)
 */

(function() {
  'use strict';

  // 1. Tự động khởi tạo Container chứa Toast ở góc phải nếu chưa có
  function getOrCreateContainer() {
    let container = document.getElementById('gov-toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'gov-toast-container';
      container.className = 'gov-toast-container';
      document.body.appendChild(container);
    }
    return container;
  }

  // 2. Định nghĩa các icon SVG tương ứng với từng loại thông báo
  const ICONS = {
    success: `
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
        <polyline points="22 4 12 14.01 9 11.01"></polyline>
      </svg>
    `,
    error: `
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="15" y1="9" x2="9" y2="15"></line>
        <line x1="9" y1="9" x2="15" y2="15"></line>
      </svg>
    `,
    warning: `
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
        <line x1="12" y1="9" x2="12" y2="13"></line>
        <line x1="12" y1="17" x2="12.01" y2="17"></line>
      </svg>
    `,
    info: `
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="16" x2="12" y2="12"></line>
        <line x1="12" y1="8" x2="12.01" y2="8"></line>
      </svg>
    `
  };

  const DEFAULT_TITLES = {
    success: 'Thành công',
    error: 'Thông báo lỗi',
    warning: 'Cảnh báo',
    info: 'Thông báo hệ thống'
  };

  /**
   * Hiển thị thông báo Toast ở góc phải trên
   * @param {string} message - Nội dung thông báo
   * @param {string} type - 'success' | 'error' | 'warning' | 'info'
   * @param {string} [title] - Tiêu đề tùy chọn
   * @param {number} [duration] - Thời gian tự tắt (ms), mặc định 4000ms
   */
  function showToast(message, type = 'info', title = null, duration = 4000) {
    if (!message) return;
    
    type = String(type).toLowerCase();
    if (type === 'danger') type = 'error';
    if (!['success', 'error', 'warning', 'info'].includes(type)) {
      type = 'info';
    }

    if (!title) {
      title = DEFAULT_TITLES[type] || 'Thông báo';
    }

    const container = getOrCreateContainer();
    const toast = document.createElement('div');
    toast.className = `gov-toast gov-toast-${type}`;

    const formattedMsg = String(message).replace(/\n/g, '<br>');

    toast.innerHTML = `
      <div class="gov-toast-icon-wrap">
        ${ICONS[type] || ICONS.info}
      </div>
      <div class="gov-toast-content">
        <div class="gov-toast-title">${title}</div>
        <div class="gov-toast-message">${formattedMsg}</div>
      </div>
      <button type="button" class="gov-toast-close" title="Đóng thông báo" aria-label="Close">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      </button>
      <div class="gov-toast-progress">
        <div class="gov-toast-progress-bar" style="animation-duration: ${duration}ms;"></div>
      </div>
    `;

    function closeToast() {
      if (toast.classList.contains('toast-hiding')) return;
      toast.classList.add('toast-hiding');
      setTimeout(() => {
        if (toast.parentNode) {
          toast.parentNode.removeChild(toast);
        }
      }, 350);
    }

    const closeBtn = toast.querySelector('.gov-toast-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        closeToast();
      });
    }

    container.appendChild(toast);

    const timer = setTimeout(closeToast, duration);

    toast.addEventListener('mouseenter', () => {
      const bar = toast.querySelector('.gov-toast-progress-bar');
      if (bar) bar.style.animationPlayState = 'paused';
      clearTimeout(timer);
    });

    toast.addEventListener('mouseleave', () => {
      const bar = toast.querySelector('.gov-toast-progress-bar');
      if (bar) bar.style.animationPlayState = 'running';
      setTimeout(closeToast, 1500);
    });

    return toast;
  }

  /**
   * Hiển thị Toast và tự động tải lại trang mượt mà
   */
  function showToastAndReload(message, type = 'success', delay = 1000) {
    try {
      sessionStorage.setItem('gov_pending_toast', JSON.stringify({ message, type }));
    } catch (e) {}
    showToast(message, type);
    setTimeout(() => {
      window.location.reload();
    }, delay);
  }

  // 3. Tự động kiểm tra và hiển thị Toast pending sau khi trang vừa reload
  function checkPendingToast() {
    try {
      const raw = sessionStorage.getItem('gov_pending_toast');
      if (raw) {
        sessionStorage.removeItem('gov_pending_toast');
        const data = JSON.parse(raw);
        if (data && data.message) {
          setTimeout(() => {
            showToast(data.message, data.type || 'success');
          }, 250);
        }
      }
    } catch (e) {}
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', checkPendingToast);
  } else {
    checkPendingToast();
  }

  // 4. GHI ĐÈ HÀM window.alert MẶC ĐỊNH CỦA TRÌNH DUYỆT
  // Bất kỳ gọi lệnh alert(...) nào đều lập tức biến thành Toast góc phải siêu đẹp!
  window.alert = function(msg) {
    if (msg === undefined || msg === null) return;
    const str = String(msg);
    const lower = str.toLowerCase();

    let type = 'info';
    let title = 'Thông báo hệ thống';

    if (
      lower.includes('thành công') ||
      lower.includes('đã duyệt') ||
      lower.includes('đã ký') ||
      lower.includes('đã nạp') ||
      lower.includes('đã cấp') ||
      lower.includes('đã tạo') ||
      lower.includes('đã sao chép') ||
      lower.includes('hợp lệ') ||
      lower.includes('đã thu hồi thành công')
    ) {
      type = 'success';
      title = 'Thao tác thành công';
    } else if (
      lower.includes('lỗi') ||
      lower.includes('thất bại') ||
      lower.includes('từ chối') ||
      lower.includes('không thể') ||
      lower.includes('sai') ||
      lower.includes('hết hạn') ||
      lower.includes('chỉ chấp nhận') ||
      lower.includes('bị từ chối')
    ) {
      type = 'error';
      title = 'Thông báo lỗi';
    } else if (
      lower.includes('cảnh báo') ||
      lower.includes('chú ý') ||
      lower.includes('vui lòng') ||
      lower.includes('yêu cầu')
    ) {
      type = 'warning';
      title = 'Cảnh báo';
    }

    try {
      sessionStorage.setItem('gov_pending_toast', JSON.stringify({ message: str, type, title }));
    } catch (e) {}

    showToast(str, type, title);
  };

  // Xuất ra phạm vi toàn cục
  window.showToast = showToast;
  window.showToastAndReload = showToastAndReload;

})();

