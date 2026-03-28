// Theme toggle
const toggle = document.getElementById('themeToggle');
const root = document.documentElement;
const mq = window.matchMedia('(prefers-color-scheme: dark)');

function apply(dark) {
  root.setAttribute('data-theme', dark ? 'dark' : 'light');
  toggle.checked = dark;
}

// Always follow system preference on load (no localStorage persistence)
// The toggle is a session-only override
apply(mq.matches);

// Auto-follow system preference changes
mq.addEventListener('change', e => apply(e.matches));

// Manual toggle overrides for current session
toggle.addEventListener('change', () => {
  root.setAttribute('data-theme', toggle.checked ? 'dark' : 'light');
});

// Auto-dismiss flash messages
document.querySelectorAll('.flash').forEach(el => {
  setTimeout(() => {
    el.style.opacity = '0';
    el.style.transition = 'opacity 0.3s';
    setTimeout(() => el.remove(), 300);
  }, 3000);
});

// Confirm delete
document.querySelectorAll('.btn-delete').forEach(btn => {
  btn.closest('form').addEventListener('submit', e => {
    if (!confirm('Delete this task?')) {
      e.preventDefault();
    }
  });
});
