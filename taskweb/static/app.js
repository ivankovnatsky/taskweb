// Custom confirm dialog using <dialog> — returns Promise<boolean>
let confirmDialogOpen = false;

function showConfirm(message, opts) {
  return new Promise((resolve) => {
    const dlg = document.getElementById("confirm-dialog");
    if (!dlg || typeof dlg.showModal !== "function") {
      resolve(window.confirm(message));
      return;
    }
    dlg.querySelector(".confirm-message").textContent = message;
    const okBtn = dlg.querySelector('[data-action="ok"]');
    const cancelBtn = dlg.querySelector('[data-action="cancel"]');
    const danger = !!(opts && opts.danger);
    okBtn.classList.toggle("btn-delete", danger);
    let result = false;
    function onOk() { result = true; dlg.close(); }
    function onCancel() { result = false; dlg.close(); }
    function onClose() {
      okBtn.removeEventListener("click", onOk);
      cancelBtn.removeEventListener("click", onCancel);
      dlg.removeEventListener("close", onClose);
      confirmDialogOpen = false;
      resolve(result);
    }
    okBtn.addEventListener("click", onOk);
    cancelBtn.addEventListener("click", onCancel);
    dlg.addEventListener("close", onClose);
    confirmDialogOpen = true;
    dlg.showModal();
  });
}

// Generic data-confirm handler for forms
document.querySelectorAll("form[data-confirm]").forEach((form) => {
  let confirmed = false;
  form.addEventListener("submit", (e) => {
    if (confirmed) return;
    e.preventDefault();
    const danger = !!form.querySelector(".btn-delete");
    showConfirm(form.dataset.confirm, { danger }).then((ok) => {
      if (ok) {
        confirmed = true;
        form.submit();
      }
    });
  });
});

// Auto-dismiss flash messages
document.querySelectorAll(".flash").forEach((el) => {
  setTimeout(() => {
    el.style.opacity = "0";
    el.style.transition = "opacity 0.3s";
    setTimeout(() => el.remove(), 300);
  }, 3000);
});

// New task toggle
function toggleNewTask() {
  const btn = document.getElementById("new-task-toggle");
  const form = document.getElementById("add-form");
  if (!btn || !form) return;
  const open = form.style.display !== "none";
  form.style.display = open ? "none" : "";
  btn.classList.toggle("open", !open);
  if (!open) {
    const input = form.querySelector("#description");
    if (input) input.focus();
  }
}

(function () {
  const btn = document.getElementById("new-task-toggle");
  if (btn)
    btn.addEventListener("click", function (e) {
      e.preventDefault();
      toggleNewTask();
    });
})();

// Refresh button
(function () {
  const btn = document.querySelector(".nav-refresh");
  if (btn)
    btn.addEventListener("click", function (e) {
      e.preventDefault();
      location.reload();
    });
})();

// Keyboard navigation
(function () {
  let idBuffer = "";
  let idTimer = null;
  let indicator = null;

  function showIndicator(text) {
    if (!indicator) {
      indicator = document.createElement("div");
      indicator.className = "kbd-input";
      document.body.appendChild(indicator);
    }
    indicator.textContent = "#" + text;
    indicator.style.display = "";
  }

  function hideIndicator() {
    if (indicator) indicator.style.display = "none";
  }

  function goToTask(id) {
    // Find task row with matching ID
    const cells = document.querySelectorAll(
      "table.tw td.id, table.tw td.recur",
    );
    for (const cell of cells) {
      if (cell.textContent.trim() === id) {
        const link = cell.closest("tr").querySelector("a.task-link");
        if (link) {
          window.location.href = link.href;
          return;
        }
      }
    }
  }

  document.addEventListener("keydown", function (e) {
    // Skip all shortcuts while confirm dialog is open
    if (confirmDialogOpen) return;
    // Skip if user is typing in an input/select/textarea
    const tag = e.target.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") {
      // Escape closes new task form
      if (e.key === "Escape") {
        const form = document.getElementById("add-form");
        if (form && form.style.display !== "none") {
          toggleNewTask();
          e.target.blur();
        }
      }
      return;
    }

    // Don't capture if modifier keys are held
    if (e.ctrlKey || e.metaKey || e.altKey) return;

    // Skip all shortcuts on edit page (has its own keybinds in inline script)
    if (document.getElementById("edit-save")) return;

    const key = e.key.toLowerCase();

    // Task detail shortcuts (override nav when on detail page)
    const editLink = document.getElementById("action-edit");
    if (editLink) {
      if (key === "e") {
        e.preventDefault();
        window.location.href = editLink.href;
        return;
      }
      const actionMap = { c: "action-complete", p: "action-pending", w: "action-wait", d: "action-delete" };
      if (actionMap[key]) {
        const form = document.getElementById(actionMap[key]);
        if (form) {
          e.preventDefault();
          form.requestSubmit();
        }
        return;
      }
    }

    // Letter shortcuts
    if (key === "n") {
      e.preventDefault();
      toggleNewTask();
      return;
    }

    if (key === "r" && document.querySelector(".nav-refresh")) {
      e.preventDefault();
      location.reload();
      return;
    }

    if (key === "s") {
      const searchField = document.getElementById("search-field");
      if (searchField) {
        e.preventDefault();
        searchField.focus();
        return;
      }
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
        idBuffer = "";
        hideIndicator();
      }, 800);
      return;
    }

    // Enter confirms buffered ID immediately
    if (e.key === "Enter" && idBuffer) {
      e.preventDefault();
      clearTimeout(idTimer);
      goToTask(idBuffer);
      idBuffer = "";
      hideIndicator();
      return;
    }

    // Escape clears buffer, closes form, or navigates back
    if (e.key === "Escape") {
      if (idBuffer) {
        clearTimeout(idTimer);
        idBuffer = "";
        hideIndicator();
        return;
      }
      const form = document.getElementById("add-form");
      if (form && form.style.display !== "none") {
        toggleNewTask();
        return;
      }
      const backLink = document.getElementById("back-link");
      if (backLink) {
        window.location.href = backLink.href;
        return;
      }
    }
  });
})();

// Clickable table rows
document.querySelectorAll("tr[data-href]").forEach(function (row) {
  row.addEventListener("click", function (e) {
    if (!e.target.closest("a, button, form")) {
      window.location = row.dataset.href;
    }
  });
});

// Project autocomplete dropdown
(function () {
  document.querySelectorAll('input[data-projects]').forEach(function (input) {
    var raw = input.getAttribute('data-projects');
    if (!raw) return;
    var allProjects;
    try { allProjects = JSON.parse(raw); } catch (e) { allProjects = raw.split(',').filter(function (s) { return s.length > 0; }); }
    if (!allProjects.length) return;

    var list = input.parentElement.querySelector('.autocomplete-list');
    if (!list) return;
    var activeIdx = -1;
    var justSelected = false;

    function render(filter) {
      var q = (filter || '').toLowerCase();
      var matches = allProjects.filter(function (p) {
        return !q || p.toLowerCase().indexOf(q) !== -1;
      });
      list.innerHTML = '';
      activeIdx = -1;
      if (!matches.length) {
        list.classList.remove('open');
        return;
      }
      matches.forEach(function (p) {
        var div = document.createElement('div');
        div.className = 'autocomplete-item';
        div.textContent = p;
        div.addEventListener('mousedown', function (e) {
          e.preventDefault(); // prevent blur
        });
        div.addEventListener('click', function () {
          input.value = p;
          justSelected = true;
          close();
        });
        list.appendChild(div);
      });
      list.classList.add('open');
    }

    function close() {
      list.classList.remove('open');
      activeIdx = -1;
    }

    function setActive(idx) {
      var items = list.querySelectorAll('.autocomplete-item');
      items.forEach(function (el) { el.classList.remove('active'); });
      if (idx >= 0 && idx < items.length) {
        activeIdx = idx;
        items[idx].classList.add('active');
        items[idx].scrollIntoView({ block: 'nearest' });
      }
    }

    input.addEventListener('focus', function () {
      render(input.value);
    });

    input.addEventListener('input', function () {
      if (justSelected) { justSelected = false; return; }
      render(input.value);
    });

    input.addEventListener('blur', function () {
      // Small delay so click on item registers
      setTimeout(close, 150);
    });

    input.addEventListener('keydown', function (e) {
      if (!list.classList.contains('open')) return;
      var items = list.querySelectorAll('.autocomplete-item');
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActive(activeIdx < items.length - 1 ? activeIdx + 1 : 0);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActive(activeIdx > 0 ? activeIdx - 1 : items.length - 1);
      } else if (e.key === 'Enter' && activeIdx >= 0) {
        e.preventDefault();
        input.value = items[activeIdx].textContent;
        close();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        close();
      }
    });
  });
})();

// Search field — client-side filtering with server-side cross-status search on Enter
(function () {
  const field = document.getElementById("search-field");
  if (!field) return;
  const table = document.querySelector("table.tw");
  const rows = table ? table.querySelectorAll("tbody tr") : [];

  function clientFilter() {
    if (!rows.length) return;
    const q = field.value.toLowerCase().trim();
    const isNumeric = /^\d+$/.test(q);
    rows.forEach(function (row) {
      let match;
      if (!q) {
        match = true;
      } else if (isNumeric) {
        const cells = row.querySelectorAll(
          "td.id, td.recur, td.proj, td.tag, td.tag-next, td.desc",
        );
        if (cells.length > 0) {
          const text = Array.from(cells)
            .map((c) => c.textContent.toLowerCase())
            .join(" ");
          match = text.includes(q);
        } else {
          match = row.textContent.toLowerCase().includes(q);
        }
      } else {
        match = row.textContent.toLowerCase().includes(q) ||
          (row.dataset.uuid && row.dataset.uuid.toLowerCase().includes(q));
      }
      row.style.display = match ? "" : "none";
    });
  }

  function serverSearch() {
    const q = field.value.trim();
    if (q) {
      // Determine current status from the active nav link
      const activeNav = document.querySelector("nav a.active[data-key]");
      const keyMap = {
        p: "pending",
        w: "waiting",
        c: "completed",
        d: "deleted",
      };
      const status = activeNav
        ? keyMap[activeNav.dataset.key] || "pending"
        : "pending";
      window.location.href =
        "/search?q=" + encodeURIComponent(q) + "&status=" + status;
    } else {
      // Clear search: reload current page without q
      const url = new URL(window.location.href);
      url.searchParams.delete("q");
      url.searchParams.delete("page");
      window.location.href = url.toString();
    }
  }

  // Instant client-side filtering while typing
  field.addEventListener("input", clientFilter);

  // Enter submits to server for cross-status search
  field.addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
      e.preventDefault();
      serverSearch();
    }
  });

  // "/" focuses search, Escape clears and blurs it
  document.addEventListener("keydown", function (e) {
    if (confirmDialogOpen) return;
    if (
      e.target.tagName === "INPUT" ||
      e.target.tagName === "TEXTAREA" ||
      e.target.tagName === "SELECT"
    ) {
      if (e.key === "Escape" && e.target === field) {
        if (field.value) {
          field.value = "";
          clientFilter();
          // Clear server-side query too
          const url = new URL(window.location.href);
          if (url.searchParams.has("q")) {
            url.searchParams.delete("q");
            url.searchParams.delete("page");
            window.location.href = url.toString();
          }
        } else {
          field.blur();
        }
        e.preventDefault();
      }
      return;
    }
    if (e.key === "/" && !e.ctrlKey && !e.metaKey) {
      e.preventDefault();
      field.focus();
    }
  });
})();
