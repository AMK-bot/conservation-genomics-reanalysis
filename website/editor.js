(() => {
  "use strict";

  const params = new URLSearchParams(window.location.search);
  const editorToken = params.get("token") || "";
  const apiUrl = "/api/content";

  const preview = document.getElementById("sitePreview");
  const connectionBanner = document.getElementById("connectionBanner");
  const selectionLabel = document.getElementById("selectionLabel");
  const saveStatus = document.getElementById("saveStatus");
  const discardButton = document.getElementById("discardButton");
  const undoButton = document.getElementById("undoButton");
  const exportButton = document.getElementById("exportButton");
  const importButton = document.getElementById("importButton");
  const importFile = document.getElementById("importFile");
  const resetButton = document.getElementById("resetButton");
  const saveButton = document.getElementById("saveButton");
  const openSiteLink = document.getElementById("openSiteLink");

  const state = {
    connected: false,
    busy: false,
    dirty: false,
    initialized: false,
    frameReady: false,
    revision: null,
    remoteValues: {},
    savedValues: {},
    canonicalValues: {},
    editableKeys: new Set(),
    frameDocument: null,
  };

  function normalizeText(value) {
    return String(value ?? "")
      .replace(/\u00a0/g, " ")
      .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function isPlainObject(value) {
    return Boolean(value) && typeof value === "object" && !Array.isArray(value);
  }

  function own(object, key) {
    return Object.prototype.hasOwnProperty.call(object, key);
  }

  function cleanValueObject(value) {
    if (!isPlainObject(value)) return {};
    const cleaned = {};
    for (const [key, text] of Object.entries(value)) {
      if (typeof text === "string") cleaned[key] = normalizeText(text);
    }
    return cleaned;
  }

  function unpackContent(payload) {
    const content = isPlainObject(payload?.content) ? payload.content : payload;
    if (!isPlainObject(content)) throw new Error("The editor server returned an invalid response.");
    return {
      revision: typeof content.revision === "string" ? content.revision : null,
      values: cleanValueObject(content.values),
      editableKeys: Array.isArray(content.editable_keys)
        ? content.editable_keys.filter((key) => typeof key === "string")
        : [],
    };
  }

  function setStatus(message, kind = "") {
    saveStatus.textContent = message;
    saveStatus.classList.remove("dirty", "saved", "error");
    if (kind) saveStatus.classList.add(kind);
  }

  function setConnectionBanner(message = "") {
    connectionBanner.hidden = !message;
    if (message) connectionBanner.textContent = message;
  }

  function updateActionStates() {
    saveButton.disabled = !state.connected || state.busy || !state.frameReady || !state.dirty;
    undoButton.disabled = !state.connected || state.busy || !state.frameReady;
    resetButton.disabled = !state.connected || state.busy || !state.frameReady;
    discardButton.disabled = state.busy || !state.frameReady || !state.dirty;
    exportButton.disabled = state.busy || !state.frameReady;
    importButton.disabled = state.busy || !state.frameReady;
  }

  async function requestContent(method = "GET", body = null) {
    const headers = {
      Accept: "application/json",
      "X-Editor-Token": editorToken,
    };
    const options = {
      method,
      headers,
      cache: "no-store",
      credentials: "same-origin",
    };
    if (body !== null) {
      headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }

    const response = await fetch(apiUrl, options);
    let payload = null;
    try {
      payload = await response.json();
    } catch (_error) {
      // A status-specific message below is more useful than a JSON parse error.
    }

    if (!response.ok) {
      const error = new Error(
        payload?.message || payload?.error || `The editor server returned HTTP ${response.status}.`,
      );
      error.status = response.status;
      error.payload = payload;
      throw error;
    }
    return unpackContent(payload);
  }

  function effectiveValues(overrides) {
    const values = {};
    for (const key of state.editableKeys) {
      if (own(overrides, key)) values[key] = normalizeText(overrides[key]);
      else if (own(state.canonicalValues, key)) values[key] = state.canonicalValues[key];
    }
    return values;
  }

  function valuesMatch(left, right) {
    const keys = state.editableKeys;
    for (const key of keys) {
      if (normalizeText(left[key]) !== normalizeText(right[key])) return false;
    }
    return true;
  }

  function editableElements() {
    if (!state.frameDocument) return [];
    return [...state.frameDocument.querySelectorAll("[data-edit-key]")];
  }

  function collectValues() {
    const values = {};
    for (const element of editableElements()) {
      const key = element.dataset.editKey;
      if (key) values[key] = normalizeText(element.textContent);
    }
    return values;
  }

  function applyValues(values, { partial = false } = {}) {
    for (const element of editableElements()) {
      const key = element.dataset.editKey;
      if (!key) continue;
      let nextValue;
      if (own(values, key)) nextValue = values[key];
      else if (!partial && own(state.canonicalValues, key)) nextValue = state.canonicalValues[key];
      else continue;
      element.textContent = normalizeText(nextValue);
    }
  }

  function updateDirtyStatus() {
    if (!state.frameReady) return;
    state.dirty = !valuesMatch(collectValues(), state.savedValues);
    if (state.dirty) {
      setStatus(
        state.connected ? "Draft changes — not saved" : "Local draft — export a copy to keep it",
        "dirty",
      );
    } else {
      setStatus(state.connected ? "All website text saved" : "Local preview — saving unavailable", "saved");
    }
    updateActionStates();
  }

  function humanLabel(key) {
    const sectionNames = {
      hero: "Opening",
      causal: "Causal boundary",
      question: "Research question",
      science_path: "Scientific reasoning path",
      contribution: "Scientific contribution",
      findings: "Findings",
      decision_boundaries: "Decision boundaries",
      corrections: "Research corrections",
      explorer: "Interactive models",
      evidence: "Visual evidence",
      deliverables: "Deliverables",
      reproduce: "Reproducibility",
      limitations: "Limitations",
      closing: "Closing statement",
      footer: "Footer",
    };
    const fieldNames = {
      title: "heading",
      body: "paragraph",
      summary: "summary",
      eyebrow: "introductory label",
      prefix: "opening phrase",
      diagram_label: "diagram label",
      diagram_caption: "diagram caption",
      launch_title: "model heading",
      launch_body: "model introduction",
      closing_quote: "closing quotation",
      question: "question",
      prediction: "prediction",
      stress_test: "stress test",
      result: "result",
      correction: "correction",
      falsifier: "falsifier",
      consequence: "conservation consequence",
      quote: "closing quotation",
    };
    const parts = key.split(".");
    const labels = [sectionNames[parts[0]] || parts[0]];
    for (const part of parts.slice(1)) {
      const step = part.match(/^step(\d+)$/);
      labels.push(step ? `step ${step[1]}` : fieldNames[part] || part.replaceAll("_", " "));
    }
    return labels.join(" · ");
  }

  function selectEditable(element) {
    if (!state.frameDocument) return;
    for (const selected of state.frameDocument.querySelectorAll(".editor-selected")) {
      selected.classList.remove("editor-selected");
    }
    if (!element) {
      selectionLabel.textContent = "Nothing selected yet";
      return;
    }
    element.classList.add("editor-selected");
    selectionLabel.textContent = humanLabel(element.dataset.editKey);
  }

  function insertPlainText(element, text) {
    const documentInFrame = state.frameDocument;
    const selection = documentInFrame?.getSelection();
    if (!selection) return;

    const cleanText = normalizeText(text);
    if (!selection.rangeCount || !element.contains(selection.anchorNode)) {
      element.focus();
      const fallbackRange = documentInFrame.createRange();
      fallbackRange.selectNodeContents(element);
      fallbackRange.collapse(false);
      selection.removeAllRanges();
      selection.addRange(fallbackRange);
    }

    const range = selection.getRangeAt(0);
    range.deleteContents();
    const textNode = documentInFrame.createTextNode(cleanText);
    range.insertNode(textNode);
    range.setStartAfter(textNode);
    range.collapse(true);
    selection.removeAllRanges();
    selection.addRange(range);
    const InputEventConstructor = documentInFrame.defaultView.InputEvent || documentInFrame.defaultView.Event;
    element.dispatchEvent(new InputEventConstructor("input", {
      bubbles: true,
      inputType: "insertText",
      data: cleanText,
    }));
  }

  function injectEditorStyles(documentInFrame) {
    documentInFrame.getElementById("conservation-genomics-editor-styles")?.remove();
    const style = documentInFrame.createElement("style");
    style.id = "conservation-genomics-editor-styles";
    style.textContent = `
      [data-edit-key] {
        cursor: text !important;
        outline: 1px dashed rgba(46, 117, 103, .62);
        outline-offset: 4px;
        border-radius: 2px;
        transition: outline-color .15s ease, background-color .15s ease, box-shadow .15s ease;
      }
      [data-edit-key]:hover {
        outline: 2px solid rgba(46, 117, 103, .82);
        background-color: rgba(235, 240, 232, .58);
      }
      [data-edit-key]:focus,
      [data-edit-key].editor-selected {
        outline: 3px solid #2e7567;
        background-color: rgba(235, 240, 232, .86);
        box-shadow: 0 0 0 6px rgba(235, 240, 232, .58);
      }
      [data-edit-key]:empty::before {
        content: "Type replacement text";
        color: #7a858e;
        font-style: italic;
      }
      a, button { cursor: default !important; }
    `;
    documentInFrame.head.appendChild(style);
  }

  function configurePreview() {
    let documentInFrame;
    try {
      documentInFrame = preview.contentDocument;
      if (!documentInFrame?.documentElement) throw new Error("The preview document is unavailable.");
    } catch (_error) {
      state.frameReady = false;
      setConnectionBanner(
        "This browser blocked access to the local preview. Open the editor through EDIT_WEBSITE.command to enable editing and export.",
      );
      setStatus("Preview editing unavailable", "error");
      updateActionStates();
      return;
    }

    if (state.frameDocument === documentInFrame && state.frameReady) return;
    state.frameDocument = documentInFrame;
    injectEditorStyles(documentInFrame);

    for (const element of documentInFrame.querySelectorAll("[contenteditable]")) {
      if (!element.hasAttribute("data-edit-key")) element.removeAttribute("contenteditable");
    }

    const elements = editableElements();
    for (const element of elements) {
      const key = element.dataset.editKey;
      if (!key) continue;
      state.editableKeys.add(key);
      element.contentEditable = "plaintext-only";
      element.setAttribute("spellcheck", "true");
      element.setAttribute("title", `Editable: ${humanLabel(key)}`);
      element.setAttribute("aria-label", `Editable: ${humanLabel(key)}`);
    }

    const findEditable = (target) => target instanceof documentInFrame.defaultView.Element
      ? target.closest("[data-edit-key]")
      : null;

    documentInFrame.addEventListener("focusin", (event) => {
      const element = findEditable(event.target);
      if (element) selectEditable(element);
    });

    documentInFrame.addEventListener("click", (event) => {
      const element = findEditable(event.target);
      if (element) selectEditable(element);
      const interactive = event.target instanceof documentInFrame.defaultView.Element
        ? event.target.closest("a, button, input, select, textarea, summary")
        : null;
      if (interactive) {
        event.preventDefault();
        event.stopPropagation();
      }
    }, true);

    documentInFrame.addEventListener("submit", (event) => event.preventDefault(), true);

    documentInFrame.addEventListener("keydown", (event) => {
      const element = findEditable(event.target);
      if (!element) return;
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        if (state.connected && state.dirty && !state.busy) saveChanges();
        else if (!state.connected && state.frameReady) exportCopy();
        return;
      }
      if (event.key === "Enter") {
        event.preventDefault();
        setStatus("Each editable field is one paragraph; Enter was not inserted.", "dirty");
      }
    });

    documentInFrame.addEventListener("beforeinput", (event) => {
      if (event.inputType === "insertParagraph" || event.inputType === "insertLineBreak") {
        event.preventDefault();
      }
    });

    documentInFrame.addEventListener("paste", (event) => {
      const element = findEditable(event.target);
      if (!element) return;
      event.preventDefault();
      insertPlainText(element, event.clipboardData?.getData("text/plain") || "");
    });

    documentInFrame.addEventListener("drop", (event) => {
      const element = findEditable(event.target);
      if (!element) return;
      event.preventDefault();
      element.focus();
      insertPlainText(element, event.dataTransfer?.getData("text/plain") || "");
    });

    documentInFrame.addEventListener("input", (event) => {
      const element = findEditable(event.target);
      if (!element) return;
      selectEditable(element);
      updateDirtyStatus();
    });

    documentInFrame.addEventListener("focusout", (event) => {
      const element = findEditable(event.target);
      if (!element) return;
      const normalized = normalizeText(element.textContent);
      if (element.textContent !== normalized) element.textContent = normalized;
      updateDirtyStatus();
    });

    state.frameReady = elements.length > 0;
    if (!state.frameReady) {
      setStatus("No editable text was found in the preview", "error");
      updateActionStates();
      return;
    }

    if (state.initialized) {
      applyValues(state.savedValues);
      updateDirtyStatus();
    }
    updateActionStates();
  }

  async function loadCanonicalValues() {
    try {
      const sourceUrl = new URL("index.html", window.location.href);
      sourceUrl.search = `editor-source=${Date.now()}`;
      const response = await fetch(sourceUrl, { cache: "no-store", credentials: "same-origin" });
      if (!response.ok) return;
      const source = await response.text();
      const sourceDocument = new DOMParser().parseFromString(source, "text/html");
      const canonical = {};
      for (const element of sourceDocument.querySelectorAll("[data-edit-key]")) {
        const key = element.dataset.editKey;
        if (key) canonical[key] = normalizeText(element.textContent);
      }
      state.canonicalValues = canonical;
    } catch (_error) {
      // Direct file mode may prohibit fetch; the rendered preview remains usable.
    }
  }

  function acceptServerState(serverState) {
    state.revision = serverState.revision;
    state.remoteValues = serverState.values;
    for (const key of serverState.editableKeys) state.editableKeys.add(key);
    state.savedValues = effectiveValues(state.remoteValues);
  }

  async function connectToServer() {
    const servedLocally = window.location.protocol === "http:" || window.location.protocol === "https:";
    if (!servedLocally || !editorToken) return false;
    try {
      const serverState = await requestContent();
      state.connected = true;
      acceptServerState(serverState);
      setConnectionBanner();
      return true;
    } catch (error) {
      state.connected = false;
      setConnectionBanner(
        error.status === 401 || error.status === 403
          ? "This editor link is missing or has an expired security token. Close it and reopen EDIT_WEBSITE.command. You can still edit the preview and export a copy."
          : "The local editor server is unavailable. You can still edit the preview and export a copy, but saving is disabled.",
      );
      return false;
    }
  }

  async function refreshLatestState({ apply = true } = {}) {
    const serverState = await requestContent();
    acceptServerState(serverState);
    if (apply) applyValues(state.savedValues);
    updateDirtyStatus();
    return serverState;
  }

  async function withBusy(action) {
    if (state.busy) return;
    state.busy = true;
    updateActionStates();
    try {
      await action();
    } finally {
      state.busy = false;
      updateActionStates();
    }
  }

  async function saveChanges() {
    if (!state.connected || !state.frameReady) return;
    const draft = collectValues();
    await withBusy(async () => {
      setStatus("Saving website text…");
      try {
        const serverState = await requestContent("POST", {
          action: "save",
          base_revision: state.revision,
          values: draft,
        });
        acceptServerState(serverState);
        applyValues(state.savedValues);
        state.dirty = false;
        setStatus("Website text saved", "saved");
      } catch (error) {
        if (error.status === 409) {
          try {
            await refreshLatestState({ apply: false });
            applyValues(draft);
          } catch (_refreshError) {
            // The draft remains in the frame even if the refresh also fails.
          }
          state.dirty = true;
          setStatus("Another editor saved first. Your draft is intact; review it, then save again.", "error");
        } else {
          state.dirty = true;
          setStatus(`Save failed: ${error.message}`, "error");
        }
      }
    });
  }

  async function discardDraft() {
    if (!state.frameReady) return;
    await withBusy(async () => {
      if (state.connected) {
        setStatus("Loading the latest saved text…");
        try {
          await refreshLatestState({ apply: true });
          setStatus("Draft discarded; latest saved text restored", "saved");
          return;
        } catch (error) {
          setStatus(`Could not reload saved text: ${error.message}`, "error");
          return;
        }
      }
      applyValues(state.savedValues);
      state.dirty = false;
      setStatus("Local draft discarded", "saved");
    });
  }

  async function undoLastSave() {
    if (!state.connected) return;
    await withBusy(async () => {
      setStatus("Restoring the previous saved version…");
      try {
        const serverState = await requestContent("POST", {
          action: "undo",
          base_revision: state.revision,
        });
        acceptServerState(serverState);
        applyValues(state.savedValues);
        state.dirty = false;
        setStatus("Previous saved version restored", "saved");
      } catch (error) {
        setStatus(`Undo unavailable: ${error.message}`, "error");
      }
    });
  }

  async function restoreOriginal() {
    if (!state.connected) return;
    const confirmed = window.confirm(
      "Restore every editable sentence to the original website wording? Your current saved wording will remain available through Undo last save.",
    );
    if (!confirmed) return;
    await withBusy(async () => {
      setStatus("Restoring original website wording…");
      try {
        const serverState = await requestContent("POST", {
          action: "reset",
          base_revision: state.revision,
        });
        acceptServerState(serverState);
        applyValues(state.savedValues);
        state.dirty = false;
        setStatus("Original website wording restored", "saved");
      } catch (error) {
        setStatus(`Restore failed: ${error.message}`, "error");
      }
    });
  }

  function exportCopy() {
    if (!state.frameReady) return;
    const payload = {
      version: 1,
      exported_at: new Date().toISOString(),
      values: collectValues(),
    };
    const blob = new Blob([`${JSON.stringify(payload, null, 2)}\n`], { type: "application/json" });
    const downloadUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const date = new Date().toISOString().slice(0, 10);
    link.href = downloadUrl;
    link.download = `conservation-genomics-website-text-${date}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(downloadUrl), 0);
    setStatus(
      state.dirty ? "Draft exported; it is still not saved to the website" : "Website text copy exported",
      state.dirty ? "dirty" : "saved",
    );
  }

  async function importCopy(file) {
    if (!file || !state.frameReady) return;
    try {
      const payload = JSON.parse(await file.text());
      const candidate = isPlainObject(payload?.values) ? payload.values : payload;
      if (!isPlainObject(candidate)) throw new Error("The file must contain a JSON object of website text.");

      const accepted = {};
      let ignored = 0;
      for (const [key, value] of Object.entries(candidate)) {
        if (state.editableKeys.has(key) && typeof value === "string") accepted[key] = normalizeText(value);
        else ignored += 1;
      }
      if (Object.keys(accepted).length === 0) {
        throw new Error("No recognized editable text fields were found in this file.");
      }

      applyValues(accepted, { partial: true });
      updateDirtyStatus();
      if (state.dirty) {
        setStatus(
          ignored
            ? `Imported ${Object.keys(accepted).length} text fields; ignored ${ignored} unrecognized fields`
            : `Imported ${Object.keys(accepted).length} text fields — review, then save`,
          "dirty",
        );
      } else {
        setStatus("Imported text matches the current saved wording", "saved");
      }
    } catch (error) {
      setStatus(`Import failed: ${error.message}`, "error");
    } finally {
      importFile.value = "";
    }
  }

  function jumpToSection(target) {
    if (!state.frameDocument) return;
    if (target === "top") {
      preview.contentWindow.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    state.frameDocument.getElementById(target)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function initializeEvents() {
    saveButton.addEventListener("click", saveChanges);
    discardButton.addEventListener("click", discardDraft);
    undoButton.addEventListener("click", undoLastSave);
    resetButton.addEventListener("click", restoreOriginal);
    exportButton.addEventListener("click", exportCopy);
    importButton.addEventListener("click", () => {
      importFile.value = "";
      importFile.click();
    });
    importFile.addEventListener("change", () => importCopy(importFile.files?.[0]));

    for (const button of document.querySelectorAll("[data-jump]")) {
      button.addEventListener("click", () => jumpToSection(button.dataset.jump));
    }

    openSiteLink.addEventListener("click", () => {
      openSiteLink.href = `index.html?updated=${Date.now()}`;
    });

    window.addEventListener("keydown", (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        if (state.connected && state.dirty && !state.busy) saveChanges();
        else if (!state.connected && state.frameReady) exportCopy();
      }
    });

    window.addEventListener("beforeunload", (event) => {
      if (!state.dirty) return;
      event.preventDefault();
      event.returnValue = "";
    });
  }

  async function initialize() {
    initializeEvents();
    updateActionStates();
    setStatus("Connecting…");

    let resolveFrame;
    const frameLoaded = new Promise((resolve) => { resolveFrame = resolve; });
    const onFrameLoad = () => {
      configurePreview();
      let targetPageLoaded = state.frameReady;
      try {
        targetPageLoaded = targetPageLoaded
          || preview.contentWindow.location.href !== "about:blank";
      } catch (_error) {
        // An inaccessible non-blank frame should resolve so the editor can show its error state.
        targetPageLoaded = true;
      }
      if (targetPageLoaded) resolveFrame();
    };
    preview.addEventListener("load", onFrameLoad);
    try {
      if (
        preview.contentDocument?.readyState === "complete"
        && preview.contentDocument.querySelector("[data-edit-key]")
      ) {
        onFrameLoad();
      }
    } catch (_error) {
      // The iframe load handler will report an access problem with a clearer message.
    }

    const [, connected] = await Promise.all([loadCanonicalValues(), connectToServer()]);
    await frameLoaded;

    if (Object.keys(state.canonicalValues).length === 0) {
      state.canonicalValues = collectValues();
    }

    if (connected) {
      state.savedValues = effectiveValues(state.remoteValues);
      applyValues(state.savedValues);
    } else {
      state.savedValues = collectValues();
      setConnectionBanner(
        connectionBanner.hidden
          ? "Saving is unavailable in this view. Open EDIT_WEBSITE.command to save changes; editing and export still work here."
          : connectionBanner.textContent,
      );
    }

    state.initialized = true;
    state.dirty = false;
    selectEditable(null);
    updateDirtyStatus();
  }

  initialize().catch((error) => {
    setStatus(`Editor could not start: ${error.message}`, "error");
    setConnectionBanner("The visual editor could not initialize. Reopen it through EDIT_WEBSITE.command.");
    updateActionStates();
  });
})();
