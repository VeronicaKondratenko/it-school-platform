(function () {
  'use strict';

  var root = document.documentElement;

  /* ─── Theme bootstrap (runs immediately, even before DOM ready) ─── */
  try {
    var saved = localStorage.getItem('it-school-theme') || 'dark';
    root.setAttribute('data-theme', saved);
  } catch (e) {
    root.setAttribute('data-theme', 'dark');
  }

  function isDark() { return root.getAttribute('data-theme') !== 'light'; }

  var SUN =
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>' +
    '<line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>' +
    '<line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>' +
    '<line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>';

  var MOON =
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';

  function render(btn) {
    var dark = isDark();
    var icon = dark ? SUN : MOON;
    if (btn.classList.contains('theme-toggle-header')) {
      btn.innerHTML = icon;
    } else if (btn.classList.contains('theme-toggle-float')) {
      btn.innerHTML = icon + '<span>' + (dark ? 'Світла' : 'Темна') + '</span>';
    } else {
      btn.innerHTML = icon + '<span>' + (dark ? 'Світла тема' : 'Темна тема') + '</span>';
    }
    btn.title = dark ? 'Увімкнути світлу тему' : 'Увімкнути темну тему';
  }

  function renderAll() {
    var all = document.querySelectorAll('.theme-toggle-btn,.theme-toggle-header,.theme-toggle-float');
    for (var i = 0; i < all.length; i++) render(all[i]);
  }

  function toggle() {
    var next = isDark() ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try { localStorage.setItem('it-school-theme', next); } catch (e) {}
    renderAll();
  }

  function makeBtn(cls) {
    var b = document.createElement('button');
    b.className = cls;
    b.type = 'button';
    b.setAttribute('aria-label', 'Перемкнути тему');
    b.setAttribute('data-theme-toggle', '1');
    render(b);
    b.addEventListener('click', toggle);
    return b;
  }

  /* Inject the toggle into the best available location. Idempotent:
     if a toggle already exists anywhere, do nothing. */
  function inject() {
    if (document.querySelector('[data-theme-toggle]')) return true;

    var sidebarBottom = document.querySelector('.sidebar-bottom');
    if (sidebarBottom) {
      sidebarBottom.insertBefore(makeBtn('theme-toggle-btn'), sidebarBottom.firstChild);
      return true;
    }

    var navActions = document.querySelector('.nav-actions');
    if (navActions) {
      navActions.insertBefore(makeBtn('theme-toggle-header'), navActions.firstChild);
      return true;
    }

    var headerInner = document.querySelector('.header-inner, .header-content, .app-header .header-nav, .app-header');
    if (headerInner) {
      var burger = headerInner.querySelector('.burger, .mobile-menu-btn');
      if (burger) headerInner.insertBefore(makeBtn('theme-toggle-header'), burger);
      else headerInner.appendChild(makeBtn('theme-toggle-header'));
      return true;
    }

    /* Last resort: floating button so the control is ALWAYS available */
    document.body.appendChild(makeBtn('theme-toggle-float'));
    return true;
  }

  /* Robust injection: try now, on DOM ready, and a few retries to beat
     any late client-side rendering that rebuilds the sidebar. Also watch
     the DOM and re-inject if our button gets wiped out. */
  function ensureToggle() {
    inject();
    renderAll();
  }

  function start() {
    ensureToggle();

    // Retry a few times in case the sidebar is built/replaced by JS after load
    var tries = 0;
    var iv = setInterval(function () {
      tries++;
      if (!document.querySelector('[data-theme-toggle]')) ensureToggle();
      else renderAll();
      if (tries >= 8) clearInterval(iv);
    }, 250);

    // If something removes our toggle later, put it back
    if (window.MutationObserver) {
      var mo = new MutationObserver(function () {
        if (!document.querySelector('[data-theme-toggle]')) ensureToggle();
      });
      mo.observe(document.body, { childList: true, subtree: true });
    }
  }

  /* ─── Theme-aware toasts ─── */
  function patchToasts() {
    window._origShowToast = window.showToast;
    window.showToast = function (message, type) {
      var container = document.getElementById('toast-container');
      if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:99999;display:flex;flex-direction:column;gap:8px;pointer-events:none;';
        document.body.appendChild(container);
      }
      var colors = { success: '#10b981', error: '#ef4444', warning: '#f59e0b', info: '#3b82f6' };
      var accent = colors[type] || colors.info;
      var dark = isDark();
      var toast = document.createElement('div');
      toast.style.cssText = [
        'background:' + (dark ? '#1a1f33' : '#ffffff'),
        'color:' + (dark ? '#ffffff' : '#0f172a'),
        'border:1px solid ' + (dark ? 'rgba(255,255,255,0.1)' : 'rgba(15,23,42,0.12)'),
        'border-left:3px solid ' + accent,
        'border-radius:10px', 'padding:0.75rem 1.1rem',
        'box-shadow:0 8px 24px rgba(0,0,0,0.25)',
        'font-family:Manrope,sans-serif', 'font-size:0.875rem', 'font-weight:600',
        'max-width:320px', 'pointer-events:auto', 'animation:_toastIn .25s ease'
      ].join(';');
      toast.textContent = message;
      if (!document.getElementById('_toastKeyframes')) {
        var s = document.createElement('style');
        s.id = '_toastKeyframes';
        s.textContent = '@keyframes _toastIn{from{opacity:0;transform:translateX(14px)}to{opacity:1;transform:translateX(0)}}';
        document.head.appendChild(s);
      }
      container.appendChild(toast);
      setTimeout(function () { toast.remove(); }, 3500);
    };
  }

  function run() {
    start();
    patchToasts();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', run);
  } else {
    run();
  }
})();
