// Bring the detail panel into view after an HTMX selection on narrow screens,
// where the workspace columns stack (below Tailwind's lg breakpoint). Moves
// and details saves (POSTs) happen inside the panel, so they don't scroll.
// Loaded in <head> so HTMX's body swaps and history restores never add it
// twice.
document.addEventListener("htmx:afterSettle", (event) => {
  if (event.target.id !== "application-panel") return;
  if (event.detail.requestConfig?.verb !== "get") return;
  if (window.matchMedia("(min-width: 64rem)").matches) return;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  event.target.closest("section").scrollIntoView({
    behavior: reduceMotion.matches ? "auto" : "smooth",
    block: "start",
  });
});
