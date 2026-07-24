(() => {
  "use strict";

  const overrides = window.WEBSITE_CONTENT_OVERRIDES;
  if (!overrides || typeof overrides !== "object" || Array.isArray(overrides)) {
    return;
  }

  for (const element of document.querySelectorAll("[data-edit-key]")) {
    const key = element.dataset.editKey;
    if (Object.prototype.hasOwnProperty.call(overrides, key)) {
      element.textContent = String(overrides[key]);
    }
  }
})();
