(() => {
  "use strict";

  document.documentElement.classList.add("js");

  const header = document.querySelector("[data-header]");
  const navToggle = document.querySelector("[data-nav-toggle]");
  const navLinks = document.querySelector("[data-nav-links]");

  const updateHeader = () => {
    header?.classList.toggle("is-scrolled", window.scrollY > 18);
  };

  const closeNavigation = () => {
    if (!navToggle || !navLinks) return;
    navToggle.setAttribute("aria-expanded", "false");
    navLinks.classList.remove("is-open");
  };

  updateHeader();
  window.addEventListener("scroll", updateHeader, { passive: true });

  navToggle?.addEventListener("click", () => {
    const willOpen = navToggle.getAttribute("aria-expanded") !== "true";
    navToggle.setAttribute("aria-expanded", String(willOpen));
    navLinks?.classList.toggle("is-open", willOpen);
  });

  navLinks?.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", closeNavigation);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeNavigation();
  });

  document.addEventListener("click", (event) => {
    if (!navLinks?.classList.contains("is-open")) return;
    if (navLinks.contains(event.target) || navToggle?.contains(event.target)) return;
    closeNavigation();
  });

  const revealItems = document.querySelectorAll("[data-reveal]");
  if ("IntersectionObserver" in window) {
    const revealObserver = new IntersectionObserver(
      (entries, observer) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        });
      },
      { rootMargin: "0px 0px -8%", threshold: 0.08 }
    );
    revealItems.forEach((item) => revealObserver.observe(item));
  } else {
    revealItems.forEach((item) => item.classList.add("is-visible"));
  }

  const sections = [...document.querySelectorAll("main section[id]")];
  const sectionLinks = [...document.querySelectorAll('.nav-links a[href^="#"]')];
  if ("IntersectionObserver" in window && sections.length && sectionLinks.length) {
    const sectionObserver = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (!visible) return;
        sectionLinks.forEach((link) => {
          const isCurrent = link.getAttribute("href") === `#${visible.target.id}`;
          link.classList.toggle("is-active", isCurrent);
          if (isCurrent) link.setAttribute("aria-current", "location");
          else link.removeAttribute("aria-current");
        });
      },
      { rootMargin: "-20% 0px -66%", threshold: [0.05, 0.25] }
    );
    sections.forEach((section) => sectionObserver.observe(section));
  }

  const cards = [...document.querySelectorAll("[data-deliverable]")];
  const filterButtons = [...document.querySelectorAll("[data-filter]")];
  const searchInput = document.querySelector("[data-search]");
  const resultCount = document.querySelector("[data-result-count]");
  const noResults = document.querySelector("[data-no-results]");
  let activeFilter = "all";

  const normalize = (value) => value.toLowerCase().trim().replace(/\s+/g, " ");

  const updateDeliverables = () => {
    const query = normalize(searchInput?.value || "");
    let visibleCount = 0;

    cards.forEach((card) => {
      const categories = (card.dataset.category || "").split(/\s+/);
      const searchable = normalize(`${card.dataset.searchText || ""} ${card.textContent || ""}`);
      const matchesFilter = activeFilter === "all" || categories.includes(activeFilter);
      const matchesSearch = !query || searchable.includes(query);
      const show = matchesFilter && matchesSearch;
      card.hidden = !show;
      if (show) visibleCount += 1;
    });

    if (resultCount) {
      resultCount.textContent = `${visibleCount} ${visibleCount === 1 ? "deliverable" : "deliverables"}`;
    }
    if (noResults) noResults.hidden = visibleCount !== 0;
  };

  filterButtons.forEach((button) => {
    button.addEventListener("click", () => {
      activeFilter = button.dataset.filter || "all";
      filterButtons.forEach((candidate) => {
        const selected = candidate === button;
        candidate.classList.toggle("is-active", selected);
        candidate.setAttribute("aria-pressed", String(selected));
      });
      updateDeliverables();
    });
  });

  searchInput?.addEventListener("input", updateDeliverables);
  updateDeliverables();

  const copyText = async (text) => {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return;
    }

    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
  };

  document.querySelectorAll("[data-copy]").forEach((button) => {
    const originalLabel = button.textContent;
    button.addEventListener("click", async () => {
      try {
        await copyText(button.dataset.copy || "");
        button.textContent = "Copied";
        button.classList.add("is-copied");
        window.setTimeout(() => {
          button.textContent = originalLabel;
          button.classList.remove("is-copied");
        }, 1700);
      } catch (_error) {
        button.textContent = "Select command";
      }
    });
  });

  const lightbox = document.querySelector("[data-lightbox]");
  const lightboxImage = lightbox?.querySelector("img");
  const lightboxCaption = lightbox?.querySelector("p");
  const lightboxClose = lightbox?.querySelector("[data-lightbox-close]");

  document.querySelectorAll("[data-lightbox-src]").forEach((trigger) => {
    trigger.addEventListener("click", () => {
      if (!lightbox || !lightboxImage || !lightboxCaption) return;
      lightboxImage.src = trigger.dataset.lightboxSrc || "";
      lightboxImage.alt = trigger.querySelector("img")?.alt || "Expanded project screenshot";
      lightboxCaption.textContent = trigger.dataset.lightboxCaption || "";
      if (typeof lightbox.showModal === "function") lightbox.showModal();
    });
  });

  lightboxClose?.addEventListener("click", () => lightbox?.close());
  lightbox?.addEventListener("click", (event) => {
    if (event.target === lightbox) lightbox.close();
  });
})();
