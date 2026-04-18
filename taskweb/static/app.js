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
      if (key === "c") {
        const form = document.getElementById("action-complete");
        if (form) {
          e.preventDefault();
          if (confirm("Complete this task?")) form.submit();
        }
        return;
      }
      if (key === "p") {
        const form = document.getElementById("action-pending");
        if (form) {
          e.preventDefault();
          if (confirm("Move this task to pending?")) form.submit();
        }
        return;
      }
      if (key === "w") {
        const form = document.getElementById("action-wait");
        if (form) {
          e.preventDefault();
          if (confirm("Move this task to waiting?")) form.submit();
        }
        return;
      }
      if (key === "d") {
        const form = document.getElementById("action-delete");
        if (form) {
          e.preventDefault();
          if (confirm("Delete this task?")) form.submit();
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

// Confirm delete (only for .btn-delete inside a form without its own onsubmit)
document.querySelectorAll(".btn-delete").forEach((btn) => {
  const form = btn.closest("form");
  if (!form || form.hasAttribute("onsubmit")) return;
  form.addEventListener("submit", (e) => {
    if (!confirm("Delete this task?")) {
      e.preventDefault();
    }
  });
});

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
