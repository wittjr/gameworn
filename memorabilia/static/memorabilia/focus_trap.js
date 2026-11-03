// Shared modal focus-trap helper used by the gallery lightbox and the global
// delete-confirmation modal. Exposed as window.GWFocusTrap = { activate, getFocusable }.
(function (global) {
  const FOCUSABLE_SELECTOR = [
    'a[href]',
    'button:not([disabled])',
    'textarea:not([disabled])',
    'input:not([disabled])',
    'select:not([disabled])',
    '[tabindex]:not([tabindex="-1"])',
  ].join(',');

  // Focusable, visible descendants of container, in DOM (tab) order.
  function getFocusable(container) {
    return Array.prototype.filter.call(
      container.querySelectorAll(FOCUSABLE_SELECTOR),
      function (el) { return el.offsetParent !== null; }
    );
  }

  // Focuses initialFocusEl (or the first focusable element in container), traps
  // Tab/Shift+Tab within container, and restores focus to whatever was focused
  // before activation once the returned deactivate function is called.
  function activate(container, opts) {
    opts = opts || {};
    const previouslyFocused = document.activeElement;
    const initialFocusEl = opts.initialFocus || getFocusable(container)[0] || container;
    initialFocusEl.focus();

    function handleKeydown(e) {
      if (e.key !== 'Tab') return;
      const focusable = getFocusable(container);
      if (focusable.length === 0) { e.preventDefault(); return; }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;

      if (e.shiftKey) {
        if (active === first || !container.contains(active)) {
          e.preventDefault();
          last.focus();
        }
      } else if (active === last || !container.contains(active)) {
        e.preventDefault();
        first.focus();
      }
    }

    container.addEventListener('keydown', handleKeydown);

    return function deactivate() {
      container.removeEventListener('keydown', handleKeydown);
      if (previouslyFocused && typeof previouslyFocused.focus === 'function') {
        previouslyFocused.focus();
      }
    };
  }

  global.GWFocusTrap = { activate: activate, getFocusable: getFocusable };
}(window));
