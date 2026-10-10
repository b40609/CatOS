/**
 * catOS v1 - UI Micro-Interactions & Popover Handlers
 */

export function setupComponents() {
  // 1. Telemetry Popover Toggle
  const telemetryBtn = document.getElementById("btn-telemetry-toggle");
  const telemetryPopover = document.getElementById("telemetry-popover");

  if (telemetryBtn && telemetryPopover) {
    telemetryBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      telemetryPopover.classList.toggle("open");
    });

    document.addEventListener("click", (e) => {
      if (!telemetryPopover.contains(e.target) && e.target !== telemetryBtn) {
        telemetryPopover.classList.remove("open");
      }
    });
  }

  // 2. Incident Stream Expand/Collapse Delegation
  document.addEventListener("click", (e) => {
    const item = e.target.closest(".incident-item");
    if (item) {
      item.classList.toggle("expanded");
    }
  });

  // 3. Hash / ID Click-to-Copy
  document.addEventListener("click", (e) => {
    const hashEl = e.target.closest(".hash-id");
    if (hashEl && hashEl.dataset.full) {
      navigator.clipboard.writeText(hashEl.dataset.full).then(() => {
        const originalText = hashEl.textContent;
        hashEl.textContent = "已複製！";
        setTimeout(() => {
          hashEl.textContent = originalText;
        }, 1200);
      }).catch(() => {});
    }
  });

  // 4. Keyboard Shortcuts: Esc to close popovers
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (telemetryPopover) telemetryPopover.classList.remove("open");
    }
  });
}
