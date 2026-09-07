const ICON_SUCCESS = '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>';
const ICON_ERROR   = '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>';

(function() {
  const STYLE_ID = 'toast-style';
  if (!document.getElementById(STYLE_ID)) {
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .toast-container{position:fixed;top:10px;right:10px;z-index:99999;display:flex;flex-direction:column;gap:8px;pointer-events:none}
      .toast-item{display:flex;align-items:center;gap:8px;color:#fff;padding:10px 16px;border-radius:2px;font-size:14px;transform:translateX(130%);opacity:0;transition:all 0.3s ease;white-space:nowrap;box-shadow:0 2px 6px rgba(0,0,0,0.1)}
      .toast-item.show{transform:translateX(0);opacity:1}
      .toast-icon{width:16px;height:16px;flex-shrink:0}
      .toast-success{background:rgba(0,196,140,0.75)}
      .toast-error{background:rgba(255,59,48,0.75)}
    `;
    document.head.appendChild(style);
  }
})();

function initToastContainer() {
  if (!document.getElementById('toastBox')) {
    const div = document.createElement('div');
    div.id = 'toastBox';
    div.className = 'toast-container';
    document.body.appendChild(div);
  }
}

function createToast(msg, type, icon) {
  initToastContainer();
  const box = document.getElementById('toastBox');
  const el = document.createElement('div');
  el.className = `toast-item toast-${type}`;
  el.innerHTML = icon + '<span>' + msg + '</span>';
  box.appendChild(el);

  // Force reflow
  void el.offsetWidth;

  el.classList.add('show');

  setTimeout(() => {
    el.classList.remove('show');
    setTimeout(() => el.remove(), 400);
  }, 2200);
}

window.toast = {
  success(msg = '成功') {
    createToast(msg, 'success', ICON_SUCCESS);
  },
  error(msg = '错误') {
    createToast(msg, 'error', ICON_ERROR);
  }
};