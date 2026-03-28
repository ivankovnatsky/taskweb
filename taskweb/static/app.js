// Theme toggle
const toggle = document.getElementById('themeToggle');
const root = document.documentElement;
const mq = window.matchMedia('(prefers-color-scheme: dark)');

function apply(dark) {
  root.setAttribute('data-theme', dark ? 'dark' : 'light');
  toggle.checked = dark;
}

// Initialize from saved preference or system
const saved = localStorage.getItem('taskweb-theme');
if (saved) {
  apply(saved === 'dark');
} else {
  apply(mq.matches);
}

mq.addEventListener('change', e => {
  if (!localStorage.getItem('taskweb-theme')) apply(e.matches);
});

toggle.addEventListener('change', () => {
  const dark = toggle.checked;
  root.setAttribute('data-theme', dark ? 'dark' : 'light');
  localStorage.setItem('taskweb-theme', dark ? 'dark' : 'light');
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
