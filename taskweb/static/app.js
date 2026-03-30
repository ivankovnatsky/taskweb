// Auto-dismiss flash messages
document.querySelectorAll('.flash').forEach(el => {
  setTimeout(() => {
    el.style.opacity = '0';
    el.style.transition = 'opacity 0.3s';
    setTimeout(() => el.remove(), 300);
  }, 3000);
});

// Filter overflow toggle
(function () {
  const row = document.querySelector('.filters-row');
  const toggle = document.getElementById('filter-toggle');
  if (!row || !toggle) return;

  function checkOverflow() {
    // Measure full (unwrapped) height
    row.style.maxHeight = 'none';
    row.offsetHeight; // force reflow
    const fullHeight = row.scrollHeight;

    // Restore clamp and measure again
    row.style.maxHeight = '';
    row.offsetHeight; // force reflow
    const clippedHeight = row.clientHeight;

    if (fullHeight > clippedHeight + 2) {
      toggle.style.display = '';
    } else {
      toggle.style.display = 'none';
    }
  }

  toggle.addEventListener('click', function () {
    row.classList.toggle('expanded');
    toggle.textContent = row.classList.contains('expanded') ? '[\u2715]' : '[\u2026]';
  });

  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(checkOverflow);
  } else {
    checkOverflow();
  }
  window.addEventListener('resize', checkOverflow);
})();

// New task toggle
function toggleNewTask() {
  const btn = document.getElementById('new-task-toggle');
  const form = document.getElementById('add-form');
  if (!btn || !form) return;
  const open = form.style.display !== 'none';
  form.style.display = open ? 'none' : '';
  btn.classList.toggle('open', !open);
  if (!open) {
    const input = form.querySelector('#description');
    if (input) input.focus();
  }
}

(function () {
  const btn = document.getElementById('new-task-toggle');
  if (btn) btn.addEventListener('click', function (e) {
    e.preventDefault();
    toggleNewTask();
  });
})();

// Keyboard navigation
(function () {
  let idBuffer = '';
  let idTimer = null;
  let indicator = null;

  function showIndicator(text) {
    if (!indicator) {
      indicator = document.createElement('div');
      indicator.className = 'kbd-input';
      document.body.appendChild(indicator);
    }
    indicator.textContent = '#' + text;
    indicator.style.display = '';
  }

  function hideIndicator() {
    if (indicator) indicator.style.display = 'none';
  }

  function goToTask(id) {
    // Find task row with matching ID
    const cells = document.querySelectorAll('table.tw td.id, table.tw td.recur');
    for (const cell of cells) {
      if (cell.textContent.trim() === id) {
        const link = cell.closest('tr').querySelector('a.task-link');
        if (link) {
          window.location.href = link.href;
          return;
        }
      }
    }
  }

  document.addEventListener('keydown', function (e) {
    // Skip if user is typing in an input/select/textarea
    const tag = e.target.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') {
      // Escape closes new task form
      if (e.key === 'Escape') {
        const form = document.getElementById('add-form');
        if (form && form.style.display !== 'none') {
          toggleNewTask();
          e.target.blur();
        }
      }
      return;
    }

    // Don't capture if modifier keys are held
    if (e.ctrlKey || e.metaKey || e.altKey) return;

    const key = e.key.toLowerCase();

    // Task detail shortcuts (override nav when on detail page)
    const editLink = document.getElementById('action-edit');
    if (editLink) {
      if (key === 'e') { e.preventDefault(); window.location.href = editLink.href; return; }
      if (key === 'c') {
        e.preventDefault();
        const form = document.getElementById('action-complete');
        if (form) form.submit();
        return;
      }
      if (key === 'd') {
        e.preventDefault();
        if (confirm('Delete this task?')) {
          const form = document.getElementById('action-delete');
          if (form) form.submit();
        }
        return;
      }
    }

    // Letter shortcuts
    if (key === 'n') {
      e.preventDefault();
      toggleNewTask();
      return;
    }

    // Nav shortcuts
    const navLink = document.querySelector('nav a[data-key="' + key + '"]');
    if (navLink) {
      e.preventDefault();
      window.location.href = navLink.href;
      return;
    }

    // Digit input → task ID
    if (/^[0-9]$/.test(e.key)) {
      e.preventDefault();
      idBuffer += e.key;
      showIndicator(idBuffer);

      clearTimeout(idTimer);
      idTimer = setTimeout(function () {
        goToTask(idBuffer);
        idBuffer = '';
        hideIndicator();
      }, 800);
      return;
    }

    // Enter confirms buffered ID immediately
    if (e.key === 'Enter' && idBuffer) {
      e.preventDefault();
      clearTimeout(idTimer);
      goToTask(idBuffer);
      idBuffer = '';
      hideIndicator();
      return;
    }

    // Escape clears buffer, closes form, or navigates back
    if (e.key === 'Escape') {
      if (idBuffer) {
        clearTimeout(idTimer);
        idBuffer = '';
        hideIndicator();
        return;
      }
      const form = document.getElementById('add-form');
      if (form && form.style.display !== 'none') {
        toggleNewTask();
        return;
      }
      const backLink = document.getElementById('back-link');
      if (backLink) {
        window.location.href = backLink.href;
        return;
      }
    }
  });
})();

// Confirm delete (only for .btn-delete inside a form)
document.querySelectorAll('.btn-delete').forEach(btn => {
  const form = btn.closest('form');
  if (!form) return;
  form.addEventListener('submit', e => {
    if (!confirm('Delete this task?')) {
      e.preventDefault();
    }
  });
});
