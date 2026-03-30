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
    // Temporarily expand to measure true height
    row.style.maxHeight = 'none';
    const fullHeight = row.scrollHeight;
    row.style.maxHeight = '';
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

  // Check after fonts loaded
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(checkOverflow);
  } else {
    checkOverflow();
  }
  window.addEventListener('resize', checkOverflow);
})();

// New task toggle
(function () {
  const btn = document.getElementById('new-task-toggle');
  const form = document.getElementById('add-form');
  if (!btn || !form) return;

  btn.addEventListener('click', function (e) {
    e.preventDefault();
    const open = form.style.display !== 'none';
    form.style.display = open ? 'none' : '';
    btn.classList.toggle('open', !open);
    if (!open) {
      const input = form.querySelector('#description');
      if (input) input.focus();
    }
  });
})();

// Confirm delete
document.querySelectorAll('.btn-delete').forEach(btn => {
  btn.closest('form').addEventListener('submit', e => {
    if (!confirm('Delete this task?')) {
      e.preventDefault();
    }
  });
});
