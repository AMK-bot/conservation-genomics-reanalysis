(() => {
  "use strict";

  document.documentElement.classList.add("js");

  const header = document.querySelector("[data-header]");
  const navToggle = document.querySelector("[data-nav-toggle]");
  const navLinks = document.querySelector("[data-nav-links]");

  const updateHeader = () => {
    header?.classList.toggle("is-scrolled", window.scrollY > 18);
  };

  const closeNavigation = ({ restoreFocus = false } = {}) => {
    if (!navToggle || !navLinks) return;
    navToggle.setAttribute("aria-expanded", "false");
    navLinks.classList.remove("is-open");
    if (restoreFocus) navToggle.focus();
  };

  updateHeader();
  window.addEventListener("scroll", updateHeader, { passive: true });

  navToggle?.addEventListener("click", () => {
    const willOpen = navToggle.getAttribute("aria-expanded") !== "true";
    navToggle.setAttribute("aria-expanded", String(willOpen));
    navLinks?.classList.toggle("is-open", willOpen);
  });

  navLinks?.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => closeNavigation());
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && navLinks?.classList.contains("is-open")) {
      event.preventDefault();
      closeNavigation({ restoreFocus: true });
    }
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

  const phase5bRoot = document.querySelector("[data-phase5b-lab]");
  const phase5bStatus = document.querySelector("[data-phase5b-status]");
  const phase5bData = window.PHASE5B_DATA;
  const frozenPhase5b = Object.freeze({
    wolfAssociation: "15/15 primary and 15/15 partial realized-load intervals above zero",
    damage: "1/4 fully direction-concordant metrics",
    neDesign: "0/15 qualifying simulated designs",
    localizationDecision: "IMPLEMENT",
    localization: "24/24 long-ROH population-by-GERP cells beyond null",
    annotationDecision: "DEFER_DUPLICATES_SOURCE_STUDY",
  });
  const formatNumber = (value, digits = 3) => {
    const number = Number(value);
    return Number.isFinite(number) ? number.toFixed(digits) : "not estimable";
  };
  const formatRate = (value) => {
    const number = Number(value);
    return Number.isFinite(number) ? `${(100 * number).toFixed(1)}%` : "not estimable";
  };

  const disablePhase5b = (message) => {
    if (phase5bStatus) phase5bStatus.textContent = message;
    phase5bRoot?.classList.add("is-unavailable");
    phase5bRoot?.querySelectorAll("select").forEach((select) => {
      select.disabled = true;
    });
  };

  const phase5bArraysReady =
    phase5bData &&
    Array.isArray(phase5bData.wolfAssociations) &&
    Array.isArray(phase5bData.damageEffects) &&
    Array.isArray(phase5bData.neDesign) &&
    Array.isArray(phase5bData.wolfLocalization) &&
    Array.isArray(phase5bData.claims);

  if (phase5bRoot && !phase5bArraysReady) {
    disablePhase5b(
      `Interactive rows unavailable; static outcomes remain: ${frozenPhase5b.wolfAssociation}; ` +
        `${frozenPhase5b.damage}; ${frozenPhase5b.neDesign}; §13.4 ` +
        `${frozenPhase5b.localizationDecision} and ${frozenPhase5b.localization}; §13.5 ` +
        `${frozenPhase5b.annotationDecision}.`
    );
  } else if (phase5bRoot && phase5bArraysReady) {
    if (phase5bStatus) {
      phase5bStatus.textContent =
        "Phase 5B COMPLETE · generated tables loaded locally · controls only select precomputed rows";
    }

    const wolfControls = {
      gerp: document.querySelector("[data-wolf-gerp]"),
      roh: document.querySelector("[data-wolf-roh]"),
      outcome: document.querySelector("[data-wolf-outcome]"),
      model: document.querySelector("[data-wolf-model]"),
    };
    const updateWolf = () => {
      const row = phase5bData.wolfAssociations.find(
        (candidate) =>
          Number(candidate.gerp_threshold) === Number(wolfControls.gerp?.value) &&
          Number(candidate.roh_cutoff_mb) === Number(wolfControls.roh?.value) &&
          candidate.outcome === wolfControls.outcome?.value &&
          candidate.model === wolfControls.model?.value
      );
      const estimate = document.querySelector("[data-wolf-estimate]");
      const interval = document.querySelector("[data-wolf-ci]");
      const pValue = document.querySelector("[data-wolf-p]");
      if (estimate) estimate.textContent = row ? formatNumber(row.coefficient) : "missing cell";
      if (interval) interval.textContent = row ? `${formatNumber(row.ci_low)} to ${formatNumber(row.ci_high)}` : "—";
      if (pValue) pValue.textContent = row ? formatNumber(row.permutation_p_two_sided, 4) : "—";
    };
    Object.values(wolfControls).forEach((control) => control?.addEventListener("change", updateWolf));
    updateWolf();

    const damageSelect = document.querySelector("[data-damage-variant]");
    const damageBody = document.querySelector("[data-damage-body]");
    const updateDamage = () => {
      if (!damageBody) return;
      damageBody.replaceChildren();
      const rows = phase5bData.damageEffects.filter(
        (candidate) => candidate.variant_set === damageSelect?.value
      );
      rows.forEach((row) => {
        const tr = document.createElement("tr");
        [
          row.metric,
          formatNumber(row.effect_museum_minus_modern, row.metric === "pi" ? 8 : 5),
          `${formatNumber(row.ci_low, row.metric === "pi" ? 8 : 5)} to ${formatNumber(row.ci_high, row.metric === "pi" ? 8 : 5)}`,
          formatNumber(row.exact_permutation_p_two_sided, 4),
          String(row.direction || "—").replaceAll("_", " "),
        ].forEach((value) => {
          const td = document.createElement("td");
          td.textContent = value;
          tr.appendChild(td);
        });
        damageBody.appendChild(tr);
      });
      if (!rows.length) {
        const tr = document.createElement("tr");
        const td = document.createElement("td");
        td.colSpan = 5;
        td.textContent = "No matching precomputed rows.";
        tr.appendChild(td);
        damageBody.appendChild(tr);
      }
    };
    damageSelect?.addEventListener("change", updateDamage);
    updateDamage();

    const neControls = {
      truth: document.querySelector("[data-ne-truth]"),
      sample: document.querySelector("[data-ne-sample]"),
      markers: document.querySelector("[data-ne-markers]"),
    };
    const updateNe = () => {
      const selectedTruth = Number(neControls.truth?.value);
      const isBoundary = selectedTruth === 500;
      const row = phase5bData.neDesign.find(
        (candidate) =>
          candidate.analysis_type === "scenario" &&
          Number(candidate.true_ne) === selectedTruth &&
          Number(candidate.sample_size) === Number(neControls.sample?.value) &&
          Number(candidate.marker_density) === Number(neControls.markers?.value)
      );
      const values = {
        "[data-ne-correct]": isBoundary
          ? row?.boundary_confident_pass_rate
          : row?.correct_confident_rate,
        "[data-ne-indeterminate]": row?.indeterminate_rate,
        "[data-ne-incorrect]": isBoundary
          ? row?.boundary_confident_fail_rate
          : row?.incorrect_confident_rate,
      };
      Object.entries(values).forEach(([selector, value]) => {
        const target = document.querySelector(selector);
        if (target) target.textContent = row ? formatRate(value) : "missing cell";
      });
      const correctLabel = document.querySelector("[data-ne-correct-label]");
      if (correctLabel) {
        correctLabel.textContent = isBoundary ? "Boundary confident pass" : "Correct confident";
      }
      const incorrectLabel = document.querySelector("[data-ne-incorrect-label]");
      if (incorrectLabel) {
        incorrectLabel.textContent = isBoundary ? "Boundary confident fail" : "Incorrect confident";
      }
      const attempts = document.querySelector("[data-ne-attempts]");
      if (attempts) attempts.textContent = row ? String(row.n_attempted) : "—";
    };
    Object.values(neControls).forEach((control) => control?.addEventListener("change", updateNe));
    updateNe();

    const localizationControls = {
      population: document.querySelector("[data-localization-pop]"),
      gerp: document.querySelector("[data-localization-gerp]"),
      roh: document.querySelector("[data-localization-roh]"),
    };
    const updateLocalization = () => {
      const row = phase5bData.wolfLocalization?.find(
        (candidate) =>
          candidate.POP === localizationControls.population?.value &&
          Number(candidate.gerp_threshold) === Number(localizationControls.gerp?.value) &&
          Number(candidate.roh_cutoff_mb) === Number(localizationControls.roh?.value)
      );
      const estimate = document.querySelector("[data-localization-estimate]");
      const interval = document.querySelector("[data-localization-ci]");
      const pValue = document.querySelector("[data-localization-p]");
      const callable = document.querySelector("[data-localization-callable]");
      if (estimate) {
        estimate.textContent = row
          ? `${formatNumber(row.log2_enrichment)}${row.beyond_null ? " · beyond null" : " · null-compatible"}`
          : "missing cell";
      }
      if (interval) {
        interval.textContent = row
          ? `${formatNumber(row.null_ci_low)} to ${formatNumber(row.null_ci_high)}`
          : "—";
      }
      if (pValue) pValue.textContent = row ? formatNumber(row.permutation_p_two_sided, 4) : "—";
      if (callable) {
        callable.textContent = row
          ? `${Number(row.inside_eligible_genotype_calls).toLocaleString()} / ${Number(row.outside_eligible_genotype_calls).toLocaleString()}`
          : "—";
      }
    };
    Object.values(localizationControls).forEach((control) =>
      control?.addEventListener("change", updateLocalization)
    );
    updateLocalization();

    const neClaim = phase5bData.claims.find((claim) => claim.claim_id === "peafowl_ne_study_design");
    const neCardValue = document.querySelector("[data-ne-resolving]");
    if (neCardValue) {
      neCardValue.textContent = neClaim ? `${neClaim.observed_value} / 15` : "0 / 15";
    }
    const localizationClaim = phase5bData.claims.find(
      (claim) => claim.claim_id === "wolf_roh_localized_realized_burden"
    );
    const localizationCardValue = document.querySelector("[data-localization-support]");
    if (localizationCardValue) {
      localizationCardValue.textContent = localizationClaim
        ? `${localizationClaim.observed_value} / 24`
        : "24 / 24";
    }

    const traceList = document.querySelector("[data-claim-trace-list]");
    if (traceList) {
      traceList.classList.remove("static-claim-summary");
      traceList.replaceChildren();
      phase5bData.claims.forEach((claim) => {
        const article = document.createElement("article");
        const heading = document.createElement("h4");
        heading.textContent = `${claim.section} · ${claim.headline}`;
        const result = document.createElement("p");
        result.className = "claim-trace__result";
        result.textContent = `${claim.claim_status} · ${claim.estimate}`;
        const boundary = document.createElement("p");
        boundary.className = "claim-trace__boundary";
        boundary.textContent = claim.scientific_boundary;
        const links = document.createElement("p");
        [
          ["table", claim.result_table],
          ["provenance", claim.provenance],
          ["validation", claim.validator],
          ["report", claim.report_anchor],
          ["explorer", claim.explorer_anchor],
          ["workflow", String(claim.workflow_rule || "").split("#")[0]],
        ].forEach(([label, href]) => {
          if (!href) return;
          const link = document.createElement("a");
          link.href = href;
          link.textContent = label;
          links.appendChild(link);
        });
        article.append(heading, result, boundary, links);
        traceList.appendChild(article);
      });
    }
  }

  document.querySelectorAll("img").forEach((img) => {
    const showMissingImage = () => {
      img.classList.add("is-missing");
      const container = img.parentElement;
      if (!container || container.querySelector("[data-missing-asset]")) return;
      const note = document.createElement("span");
      note.setAttribute("data-missing-asset", "true");
      note.className = "missing-asset";
      note.textContent = `Image unavailable: ${img.getAttribute("alt") || "project figure"}`;
      container.appendChild(note);
    };
    img.addEventListener("error", showMissingImage);
    if (img.complete && img.naturalWidth === 0) showMissingImage();
  });
})();
