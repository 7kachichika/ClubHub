document.addEventListener("DOMContentLoaded", function () {
  const qInput = document.getElementById("q");
  const startInput = document.getElementById("start");
  const endInput = document.getElementById("end");
  const cards = document.querySelectorAll(".event-card");
  const emptyState = document.getElementById("client-filter-empty");
  const historyPanel = document.getElementById("search-history-panel");
  const toolbarToggle = document.getElementById("toolbar-toggle");
  const toolbarPanel = document.getElementById("toolbar-filter-panel");
  const searchForm = document.getElementById("navbar-event-search");

  // ⭐ 从 Django 注入变量（关键）
  const favoriteOnly = document.body.dataset.favorite === "1";

  const storageKey = "clubhub_search_history";

  function normalise(value) {
    return (value || "").toString().trim().toLowerCase();
  }

  function getHistory() {
    try {
      return JSON.parse(localStorage.getItem(storageKey) || "[]");
    } catch {
      return [];
    }
  }

  function saveHistory(term) {
    const cleaned = (term || "").trim();
    if (!cleaned) return;

    let items = getHistory().filter(i => i.toLowerCase() !== cleaned.toLowerCase());
    items.unshift(cleaned);
    items = items.slice(0, 6);

    localStorage.setItem(storageKey, JSON.stringify(items));
  }

  function renderHistory() {
    if (!historyPanel) return;

    const items = getHistory();

    if (!items.length) {
      historyPanel.innerHTML = '<div class="search-history-empty">No recent searches</div>';
      return;
    }

    historyPanel.innerHTML = items.map(item =>
      `<button type="button" class="search-history-item" data-history-item="${item.replace(/"/g, '&quot;')}">${item}</button>`
    ).join("");
  }

  function showHistory() {
    if (!historyPanel) return;
    renderHistory();
    historyPanel.classList.remove("d-none");
  }

  function hideHistory() {
    if (!historyPanel) return;
    historyPanel.classList.add("d-none");
  }

  function toggleToolbar() {
    if (!toolbarPanel) return;

    const open = toolbarPanel.classList.toggle("is-open");

    if (toolbarToggle) {
      toolbarToggle.setAttribute("aria-expanded", open ? "true" : "false");
    }
  }

  function filterCards() {
    if (!cards.length) return;

    const searchText = normalise(qInput?.value);

    let startDate = startInput?.value ? new Date(startInput.value) : null;
    let endDate = endInput?.value ? new Date(endInput.value) : null;

    if (startDate && endDate && startDate > endDate) {
      [startDate, endDate] = [endDate, startDate];
    }

    let visible = 0;

    cards.forEach(card => {
      const title = normalise(card.dataset.title);
      const desc = normalise(card.dataset.description);
      const location = normalise(card.dataset.location);
      const tags = normalise(card.dataset.tags);
      const eventDate = card.dataset.start ? new Date(card.dataset.start) : null;
      const isFavorited = card.dataset.favorited === "1";

      const matchText =
        !searchText ||
        title.includes(searchText) ||
        desc.includes(searchText) ||
        location.includes(searchText) ||
        tags.includes(searchText);

      const matchStart = !startDate || (eventDate && eventDate >= startDate);
      const matchEnd = !endDate || (eventDate && eventDate <= endDate);
      const matchFav = !favoriteOnly || isFavorited;

      const show = matchText && matchStart && matchEnd && matchFav;

      card.classList.toggle("d-none", !show);

      if (show) visible++;
    });

    if (emptyState) {
      emptyState.classList.toggle("d-none", visible !== 0);
    }
  }

  // ===== 绑定 =====

  toolbarToggle?.addEventListener("click", e => {
    e.preventDefault();
    e.stopPropagation();
    toggleToolbar();
  });

  qInput?.addEventListener("input", () => {
    showHistory();
    filterCards();
  });

  qInput?.addEventListener("focus", showHistory);

  qInput?.form?.addEventListener("submit", () => {
    saveHistory(qInput.value);
  });

  startInput?.addEventListener("change", filterCards);
  endInput?.addEventListener("change", filterCards);

  historyPanel?.addEventListener("mousedown", e => {
    const btn = e.target.closest("[data-history-item]");
    if (!btn || !qInput) return;

    qInput.value = btn.dataset.historyItem;
    filterCards();
  });

  document.addEventListener("click", () => {
    hideHistory();
    toolbarPanel?.classList.remove("is-open");
  });

  document.addEventListener("keydown", e => {
    if (e.key === "Escape") {
      hideHistory();
      toolbarPanel?.classList.remove("is-open");
    }
  });

  filterCards();
});