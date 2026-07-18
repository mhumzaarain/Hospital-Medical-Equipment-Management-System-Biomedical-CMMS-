/* HEMDESK UI helpers: dark mode, toasts, KPI count-up.
   Must load (deferred) BEFORE alpine.min.js so alpine:init listeners register. */

function toggleTheme() {
  const dark = document.documentElement.classList.toggle("dark");
  localStorage.setItem("hemdesk-theme", dark ? "dark" : "light");
  window.dispatchEvent(new CustomEvent("theme-changed"));
}

let hemdeskToastId = 0;

document.addEventListener("alpine:init", () => {
  Alpine.data("toasts", () => ({
    items: [],
    init() {
      (window.djangoMessages || []).forEach((m, i) =>
        setTimeout(() => this.push(m.level, m.text), 150 * i)
      );
    },
    push(level, text) {
      const id = ++hemdeskToastId;
      this.items.push({ id, level: level || "info", text });
      setTimeout(() => this.dismiss(id), 5000);
    },
    dismiss(id) {
      this.items = this.items.filter((t) => t.id !== id);
    },
  }));

  Alpine.data("countUp", (target, suffix = "") => ({
    shown: "0" + suffix,
    init() {
      const value = Number(target);
      if (!isFinite(value)) { this.shown = String(target); return; }
      const done = () =>
        (this.shown = (Number.isInteger(value) ? value : value.toFixed(1)) + suffix);
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return done();
      const t0 = performance.now();
      const duration = 800;
      const step = (now) => {
        const p = Math.min((now - t0) / duration, 1);
        const eased = 1 - Math.pow(1 - p, 3);
        const current = value * eased;
        this.shown =
          (Number.isInteger(value) ? Math.round(current) : current.toFixed(1)) + suffix;
        if (p < 1) requestAnimationFrame(step);
        else done();
      };
      requestAnimationFrame(step);
    },
  }));
});
