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
    // If content overflows single row, show the toggle button
    if (row.scrollHeight > row.clientHeight + 4) {
      toggle.style.display = '';
    } else {
      toggle.style.display = 'none';
    }
  }

  toggle.addEventListener('click', function () {
    row.classList.toggle('expanded');
    toggle.textContent = row.classList.contains('expanded') ? '[\u2715]' : '[\u2026]';
  });

  checkOverflow();
  window.addEventListener('resize', checkOverflow);
})();

// Confirm delete
document.querySelectorAll('.btn-delete').forEach(btn => {
  btn.closest('form').addEventListener('submit', e => {
    if (!confirm('Delete this task?')) {
      e.preventDefault();
    }
  });
});
