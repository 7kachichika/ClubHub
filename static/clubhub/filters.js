document.addEventListener("DOMContentLoaded", function () {
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

    let items = getHistory().filter((item) => item.toLowerCase() !== cleaned.toLowerCase());
    items.unshift(cleaned);
    items = items.slice(0, 6);

    localStorage.setItem(storageKey, JSON.stringify(items));
  }

  function renderHistory(historyPanel) {
    if (!historyPanel) return;

    const items = getHistory();

    if (!items.length) {
      historyPanel.innerHTML = '<div class="search-history-empty">No recent searches</div>';
      return;
    }

    historyPanel.innerHTML = items
      .map(
        (item) =>
          `<button type="button" class="search-history-item" aria-label="Search for ${item.replace(
            /"/g,
            "&quot;"
          )}" data-history-item="${item.replace(/"/g, "&quot;")}">${item}</button>`
      )
      .join("");
  }

  function showHistory(historyPanel) {
    if (!historyPanel) return;
    renderHistory(historyPanel);
    historyPanel.classList.remove("d-none");
  }

  function hideHistory(historyPanel) {
    if (!historyPanel) return;
    historyPanel.classList.add("d-none");
  }

  function initToolbar(toggle, panel) {
    if (!toggle || !panel) return;

    let lastFocused = null;

    function getFirstFocusable(container) {
      const selector =
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
      return container.querySelector(selector);
    }

    function openToolbar() {
      lastFocused = document.activeElement;
      panel.classList.add("is-open");
      toggle.setAttribute("aria-expanded", "true");
      panel.setAttribute("aria-hidden", "false");

      const first = getFirstFocusable(panel);
      if (first) {
        window.setTimeout(() => first.focus(), 0);
      }
    }

    function closeToolbar() {
      panel.classList.remove("is-open");
      toggle.setAttribute("aria-expanded", "false");
      panel.setAttribute("aria-hidden", "true");

      if (lastFocused && typeof lastFocused.focus === "function") {
        lastFocused.focus();
      }
    }

    function toggleToolbar() {
      if (panel.classList.contains("is-open")) {
        closeToolbar();
      } else {
        openToolbar();
      }
    }

    toggle.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      toggleToolbar();
    });

    document.addEventListener("click", function (event) {
      if (
        panel.classList.contains("is-open") &&
        !panel.contains(event.target) &&
        event.target !== toggle &&
        !toggle.contains(event.target)
      ) {
        closeToolbar();
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        closeToolbar();
      }
    });

    panel.setAttribute("aria-hidden", panel.classList.contains("is-open") ? "false" : "true");
  }

  function initHomeSearch() {
    const qInput = document.getElementById("q");
    const startInput = document.getElementById("start");
    const endInput = document.getElementById("end");
    const cards = document.querySelectorAll(".event-card");
    const emptyState = document.getElementById("client-filter-empty");
    const historyPanel = document.getElementById("search-history-panel");
    const toolbarToggle = document.getElementById("toolbar-toggle");
    const toolbarPanel = document.getElementById("toolbar-filter-panel");
    const searchForm = document.getElementById("navbar-event-search");

    if (!searchForm) return;

    initToolbar(toolbarToggle, toolbarPanel);

    function filterCards() {
      if (!cards.length) return;

      const searchText = normalise(qInput?.value);

      let startDate = startInput?.value ? new Date(startInput.value) : null;
      let endDate = endInput?.value ? new Date(endInput.value) : null;

      if (startDate && endDate && startDate > endDate) {
        [startDate, endDate] = [endDate, startDate];
      }

      let visible = 0;

      cards.forEach((card) => {
        const title = normalise(card.dataset.title);
        const desc = normalise(card.dataset.description);
        const location = normalise(card.dataset.location);
        const tags = normalise(card.dataset.tags);
        const organizer = normalise(card.dataset.organizer);
        const eventDate = card.dataset.start ? new Date(card.dataset.start) : null;
        const isFavorited = card.dataset.favorited === "1";

        const matchText =
          !searchText ||
          title.includes(searchText) ||
          desc.includes(searchText) ||
          location.includes(searchText) ||
          tags.includes(searchText) ||
          organizer.includes(searchText);

        const matchStart = !startDate || (eventDate && eventDate >= startDate);
        const matchEnd = !endDate || (eventDate && eventDate <= endDate);
        const matchFav = !favoriteOnly || isFavorited;

        const show = matchText && matchStart && matchEnd && matchFav;
        card.classList.toggle("d-none", !show);

        if (show) visible += 1;
      });

      if (emptyState) {
        emptyState.classList.toggle("d-none", visible !== 0);
      }
    }

    qInput?.addEventListener("input", function () {
      showHistory(historyPanel);
      filterCards();
    });

    qInput?.addEventListener("focus", function () {
      showHistory(historyPanel);
    });

    searchForm.addEventListener("submit", function () {
      if (qInput) saveHistory(qInput.value);
    });

    startInput?.addEventListener("change", filterCards);
    endInput?.addEventListener("change", filterCards);

    historyPanel?.addEventListener("mousedown", function (event) {
      const button = event.target.closest("[data-history-item]");
      if (!button || !qInput) return;

      qInput.value = button.dataset.historyItem;
      hideHistory(historyPanel);
      filterCards();
    });

    document.addEventListener("click", function (event) {
      if (historyPanel && !historyPanel.contains(event.target) && event.target !== qInput) {
        hideHistory(historyPanel);
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        hideHistory(historyPanel);
      }
    });

    filterCards();
  }

  function initGlobalSearch() {
    const qInput = document.getElementById("global-q");
    const toolbarToggle = document.getElementById("global-toolbar-toggle");
    const toolbarPanel = document.getElementById("global-toolbar-filter-panel");
    const searchForm = document.getElementById("navbar-global-search");

    if (!searchForm) return;

    initToolbar(toolbarToggle, toolbarPanel);

    searchForm.addEventListener("submit", function () {
      if (qInput) saveHistory(qInput.value);
    });
  }

  // -----------------------------------------------------------------------
  // AJAX favorite toggle — event_detail page only
  // -----------------------------------------------------------------------
  function getCsrfToken() {
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : "";
  }

  function initFavoriteToggle() {
    const btn   = document.getElementById("favorite-btn");
    if (!btn) return;

    const label = document.getElementById("favorite-btn-label");
    const toast = document.getElementById("favorite-toast");
    const icon  = btn.querySelector("i");

    function showToast(msg) {
      if (!toast) return;
      toast.textContent = msg;
      toast.classList.remove("d-none");
      clearTimeout(btn._toastTimer);
      btn._toastTimer = setTimeout(() => toast.classList.add("d-none"), 3000);
    }

    function applyState(favorited) {
      btn.classList.toggle("btn-dark", favorited);
      btn.classList.toggle("btn-outline-dark", !favorited);
      if (icon) {
        icon.classList.toggle("bi-heart-fill", favorited);
        icon.classList.toggle("bi-heart", !favorited);
      }
      if (label) label.textContent = favorited ? "Favorited" : "Add to favorites";
      btn.setAttribute("aria-pressed", String(favorited));
      btn.setAttribute("aria-label", favorited ? "Remove from favorites" : "Add to favorites");
    }

    btn.addEventListener("click", function () {
      btn.disabled = true;

      fetch(btn.dataset.url, {
        method: "POST",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken": getCsrfToken(),
        },
      })
        .then(function (res) {
          if (!res.ok) throw new Error("HTTP " + res.status);
          return res.json();
        })
        .then(function (data) {
          applyState(data.favorited);
          showToast(data.message);
        })
        .catch(function () {
          showToast("Could not update favorites — please try again.");
        })
        .finally(function () {
          btn.disabled = false;
        });
    });
  }

  initHomeSearch();
  initGlobalSearch();
  initFavoriteToggle();
});