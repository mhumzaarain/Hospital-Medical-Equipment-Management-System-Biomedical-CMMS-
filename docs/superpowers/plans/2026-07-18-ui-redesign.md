# Clinical Sky UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the entire HEMDESK Django CMMS with a "Clinical Sky" design system (light + dark), and add interactivity: live search/filters, toasts, animated dashboard KPIs, theme-aware charts.

**Architecture:** All styling flows from one Tailwind v4 `input.css` (design tokens + component classes), compiled with the standalone CLI. Interactivity uses the already-vendored htmx (live partials), Alpine.js (toasts, count-ups, dark mode), and Chart.js (via a new `charts.js` theme wrapper). Backend changes are limited to: htmx partial responses for equipment list, queue search/filter params, two new dashboard metrics + trend values, and one model property.

**Tech Stack:** Django 5 templates · Tailwind v4 standalone CLI (`bin/tailwindcss.exe`) · htmx · Alpine.js · Chart.js (all vendored in `static/js/`) · pytest.

## Global Constraints

- **No new runtime dependencies.** Only the vendored libs above. No Node, no npm, no CDN links.
- **CSS rebuild command (run after any template/CSS change):** `bin/tailwindcss.exe -i static/css/input.css -o static/css/app.css --minify` (from repo root; in Git Bash use `bin/tailwindcss.exe` as-is).
- **Tests:** run with `uv run pytest -q` from repo root. Suite must stay green after every task.
- **Commit style: single-line commit messages** (user preference).
- **No model migrations** (a Python `@property` is allowed; no field changes).
- **Tailwind v4 syntax notes:** `@apply` works only with *utilities* — never `@apply` a custom component class; instead share declarations via multi-selector rules. Dark mode uses `@custom-variant dark (&:where(.dark, .dark *));` keyed off `.dark` on `<html>`.
- **Script order in base.html matters:** `app.js` (deferred) must load **before** `alpine.min.js` (deferred) so `alpine:init` listeners register in time.
- `prefers-reduced-motion: reduce` must disable all non-essential animation (CSS rule + JS checks).

---

### Task 1: Design-system CSS foundation

**Files:**
- Modify: `static/css/input.css` (full rewrite)
- Regenerate: `static/css/app.css`

**Interfaces:**
- Produces (used by all later template tasks): component classes `.card`, `.card-hover`, `.btn-primary`, `.btn-danger`, `.btn-success`, `.btn-warn`, `.btn-ghost`, `.btn-sm`, `.badge-working`, `.badge-repair`, `.badge-danger`, `.badge-info`, `.badge-muted`, `.nav-link`, `.nav-link-active`, `.nav-heading`, `.link`, `.table`, `.table-card`, `.row-hover`, `.skeleton`, `.toast-progress`; utility `animate-fade-up`; CSS vars `--chart-tick`, `--chart-grid`, `--chart-bar`, `--chart-bar-hover`, `--chart-tooltip-bg`, `--chart-tooltip-fg`, `--chart-cat-1`…`--chart-cat-8`; automatic form-control styling for `input`/`select`/`textarea` inside `<main>`.

- [ ] **Step 1: Rewrite `static/css/input.css`** with exactly:

```css
@import "tailwindcss";
@source "../../templates";
@source "../js/app.js";
@source "../js/charts.js";

@custom-variant dark (&:where(.dark, .dark *));

@theme {
  --animate-fade-up: fade-up 0.35s ease-out both;

  @keyframes fade-up {
    from { opacity: 0; transform: translateY(6px); }
    to   { opacity: 1; transform: none; }
  }
  @keyframes shimmer {
    from { background-position: 200% 0; }
    to   { background-position: -200% 0; }
  }
  @keyframes toast-bar {
    from { width: 100%; }
    to   { width: 0%; }
  }
}

/* Chart.js reads these at render time; .dark swaps them (charts re-render on toggle). */
:root {
  --chart-tick: #64748b;
  --chart-grid: rgb(100 116 139 / 0.15);
  --chart-bar: #0284c7;
  --chart-bar-hover: #0369a1;
  --chart-tooltip-bg: #0f172a;
  --chart-tooltip-fg: #f1f5f9;
  --chart-cat-1: #0284c7;
  --chart-cat-2: #b45309;
  --chart-cat-3: #15803d;
  --chart-cat-4: #b91c1c;
  --chart-cat-5: #7c3aed;
  --chart-cat-6: #0f766e;
  --chart-cat-7: #be185d;
  --chart-cat-8: #64748b;
}
.dark {
  --chart-tick: #94a3b8;
  --chart-grid: rgb(148 163 184 / 0.15);
  --chart-bar: #38bdf8;
  --chart-bar-hover: #7dd3fc;
  --chart-tooltip-bg: #f1f5f9;
  --chart-tooltip-fg: #0f172a;
  --chart-cat-1: #38bdf8;
  --chart-cat-2: #fbbf24;
  --chart-cat-3: #4ade80;
  --chart-cat-4: #f87171;
  --chart-cat-5: #a78bfa;
  --chart-cat-6: #2dd4bf;
  --chart-cat-7: #f472b6;
  --chart-cat-8: #94a3b8;
}

@layer components {
  /* Surfaces */
  .card {
    @apply rounded-xl border border-slate-200 bg-white shadow-sm
           dark:border-slate-800 dark:bg-slate-900;
  }
  .card-hover {
    @apply transition duration-200 hover:-translate-y-0.5 hover:shadow-md;
  }

  /* Buttons — shared base via multi-selector (v4: cannot @apply .btn) */
  .btn, .btn-primary, .btn-danger, .btn-success, .btn-warn, .btn-ghost {
    @apply inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg
           px-4 py-2 text-sm font-medium transition duration-150 active:scale-[.98]
           focus-visible:outline-2 focus-visible:outline-offset-2
           focus-visible:outline-sky-500 disabled:pointer-events-none disabled:opacity-50;
  }
  .btn-primary { @apply bg-sky-700 text-white shadow-sm hover:bg-sky-600; }
  .btn-danger  { @apply bg-red-700 text-white shadow-sm hover:bg-red-600; }
  .btn-success { @apply bg-emerald-700 text-white shadow-sm hover:bg-emerald-600; }
  .btn-warn    { @apply bg-amber-600 text-white shadow-sm hover:bg-amber-500; }
  .btn-ghost {
    @apply border border-slate-300 bg-white text-slate-700 hover:bg-slate-50
           dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800;
  }
  .btn-sm { @apply px-3 py-1.5 text-xs; }

  /* Badges (status pills) */
  .badge, .badge-working, .badge-repair, .badge-danger, .badge-info, .badge-muted {
    @apply inline-flex items-center gap-1.5 whitespace-nowrap rounded-full
           px-2.5 py-0.5 text-xs font-medium;
  }
  .badge-working { @apply bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300; }
  .badge-repair  { @apply bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300; }
  .badge-danger  { @apply bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300; }
  .badge-info    { @apply bg-sky-100 text-sky-800 dark:bg-sky-500/15 dark:text-sky-300; }
  .badge-muted   { @apply bg-slate-200 text-slate-600 dark:bg-slate-700/40 dark:text-slate-300; }

  /* Form controls — one rule styles every Django widget inside <main>. Explicit
     utility classes on an element still win (utilities layer beats components). */
  .field,
  main input:where(:not([type="checkbox"], [type="radio"], [type="hidden"], [type="submit"], [type="file"])),
  main select,
  main textarea {
    @apply w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm
           text-slate-900 shadow-xs transition placeholder:text-slate-400
           focus:border-sky-500 focus:ring-2 focus:ring-sky-500/30 focus:outline-none
           dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100
           dark:placeholder:text-slate-500;
  }
  main select { @apply pr-8; }
  main input[type="checkbox"] { @apply size-4 rounded border-slate-300 accent-sky-600; }

  /* Tables */
  .table-card { @apply card overflow-x-auto p-0; }
  .table { @apply w-full text-sm; }
  .table thead th {
    @apply border-b border-slate-200 bg-slate-50 px-4 py-3 text-left text-xs
           font-semibold uppercase tracking-wide text-slate-500
           dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-400;
  }
  .table tbody td { @apply border-b border-slate-100 px-4 py-3 align-top dark:border-slate-800; }
  .table tbody tr:last-child td { @apply border-b-0; }
  .row-hover { @apply transition-colors hover:bg-sky-50/60 dark:hover:bg-slate-800/60; }

  /* Sidebar nav */
  .nav-link, .nav-link-active {
    @apply flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm
           text-sky-100/90 transition-colors hover:bg-white/10 hover:text-white;
  }
  .nav-link-active { @apply bg-white/15 font-medium text-white; }
  .nav-heading {
    @apply px-3 pb-1 pt-4 text-[10px] font-semibold uppercase tracking-widest text-sky-200/60;
  }

  .link { @apply font-medium text-sky-700 hover:underline dark:text-sky-400; }

  /* Skeleton shimmer (htmx loading) */
  .skeleton {
    border-radius: 0.375rem;
    background: linear-gradient(90deg, var(--color-slate-200) 25%,
                var(--color-slate-100) 50%, var(--color-slate-200) 75%);
    background-size: 200% 100%;
    animation: shimmer 1.5s linear infinite;
  }
  .dark .skeleton {
    background-image: linear-gradient(90deg, var(--color-slate-800) 25%,
                var(--color-slate-700) 50%, var(--color-slate-800) 75%);
  }

  /* Toast auto-dismiss progress bar */
  .toast-progress { animation: toast-bar 5s linear forwards; }
}

/* htmx indicators: hidden unless a request is in flight */
.htmx-indicator { display: none; }
.htmx-indicator.htmx-request { display: table-row-group; }
div.htmx-indicator.htmx-request, span.htmx-indicator.htmx-request { display: block; }

@media (prefers-reduced-motion: reduce) {
  *, ::before, ::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

- [ ] **Step 2: Rebuild CSS**

Run: `bin/tailwindcss.exe -i static/css/input.css -o static/css/app.css --minify`
Expected: "Done in …ms", no errors. (`.card` etc. only appear in output once templates use them — that's expected; the file must simply compile.)

- [ ] **Step 3: Run test suite to confirm nothing broke**

Run: `uv run pytest -q`
Expected: all pass (CSS is not covered by tests; this is a regression guard).

- [ ] **Step 4: Commit**

```bash
git add static/css/input.css static/css/app.css
git commit -m "feat: Clinical Sky design system tokens and component classes"
```

---

### Task 2: Interaction JS — `app.js` (theme, toasts, count-up) and `charts.js`

**Files:**
- Create: `static/js/app.js`
- Create: `static/js/charts.js`

**Interfaces:**
- Produces: global `toggleTheme()` (flips `.dark`, persists `hemdesk-theme` in localStorage, dispatches `theme-changed` window event); Alpine data components `toasts` (reads `window.djangoMessages = [{level, text}]`) and `countUp(target, suffix)` (exposes `shown`); global `hemdeskChart(canvasId, scriptId, kind)` where `kind` is `'bar'`, `'bar-h'`, or `'doughnut'` — theme-aware, re-renders on `theme-changed`.
- Consumes: CSS vars from Task 1; `Chart` global from vendored `chart.umd.js`.

- [ ] **Step 1: Create `static/js/app.js`** with exactly:

```js
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
```

- [ ] **Step 2: Create `static/js/charts.js`** with exactly:

```js
/* Theme-aware Chart.js wrapper. Load after chart.umd.js on pages with charts. */
(function () {
  const css = (name) =>
    getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const rebuilders = [];

  function tooltip() {
    return {
      backgroundColor: css("--chart-tooltip-bg"),
      titleColor: css("--chart-tooltip-fg"),
      bodyColor: css("--chart-tooltip-fg"),
      cornerRadius: 8,
      padding: 10,
      displayColors: false,
    };
  }

  function barConfig(data, horizontal) {
    return {
      type: "bar",
      data: {
        labels: data.labels,
        datasets: [{
          data: data.values,
          backgroundColor: css("--chart-bar"),
          hoverBackgroundColor: css("--chart-bar-hover"),
          borderRadius: 6,
          maxBarThickness: 42,
        }],
      },
      options: {
        indexAxis: horizontal ? "y" : "x",
        responsive: true,
        animation: reduced ? false : { duration: 800, easing: "easeOutQuart" },
        plugins: { legend: { display: false }, tooltip: tooltip() },
        scales: {
          x: {
            ticks: { color: css("--chart-tick") },
            grid: horizontal
              ? { color: css("--chart-grid") }
              : { display: false },
            border: { display: false },
            beginAtZero: true,
          },
          y: {
            ticks: { color: css("--chart-tick") },
            grid: horizontal
              ? { display: false }
              : { color: css("--chart-grid") },
            border: { display: false },
            beginAtZero: true,
          },
        },
      },
    };
  }

  function doughnutConfig(data) {
    const palette = [1, 2, 3, 4, 5, 6, 7, 8].map((i) => css("--chart-cat-" + i));
    return {
      type: "doughnut",
      data: {
        labels: data.labels,
        datasets: [{ data: data.values, backgroundColor: palette, borderWidth: 0 }],
      },
      options: {
        responsive: true,
        cutout: "65%",
        animation: reduced ? false : { duration: 800, easing: "easeOutQuart" },
        plugins: {
          legend: {
            display: true,
            position: "bottom",
            labels: { color: css("--chart-tick"), usePointStyle: true, boxWidth: 8 },
          },
          tooltip: tooltip(),
        },
      },
    };
  }

  window.hemdeskChart = function (canvasId, scriptId, kind) {
    /* json_script double-encodes because the view passes a JSON string. */
    const data = JSON.parse(JSON.parse(document.getElementById(scriptId).textContent));
    const make = () =>
      kind === "doughnut"
        ? doughnutConfig(data)
        : barConfig(data, kind === "bar-h");
    let chart = new Chart(document.getElementById(canvasId), make());
    rebuilders.push(() => {
      chart.destroy();
      chart = new Chart(document.getElementById(canvasId), make());
    });
  };

  window.addEventListener("theme-changed", () => rebuilders.forEach((fn) => fn()));
})();
```

- [ ] **Step 3: Commit**

```bash
git add static/js/app.js static/js/charts.js
git commit -m "feat: theme toggle, toast, count-up, and chart theming JS helpers"
```

---

### Task 3: App shell — base.html (sidebar, header, toasts, dark toggle)

**Files:**
- Modify: `templates/base.html` (full rewrite)
- Delete: `templates/partials/_messages.html`
- Test: `tests/test_ui.py` (new file)

**Interfaces:**
- Consumes: `.nav-link`, `.nav-link-active`, `.nav-heading` (Task 1); `toggleTheme()`, `toasts` (Task 2).
- Produces: template blocks `title`, `page_title`, `content`, `extra_js` — all page tasks below extend these. Active-nav convention: `{% with active=request.resolver_match.url_name %}` and substring checks.

- [ ] **Step 1: Write failing tests** — create `tests/test_ui.py`:

```python
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_sidebar_marks_active_nav(client, engineer):
    client.force_login(engineer)
    response = client.get(reverse("equipment_list"))
    assert b"nav-link-active" in response.content


def test_messages_rendered_as_toast_payload(client, engineer, equipment):
    client.force_login(engineer)
    response = client.post(
        reverse("workorder_open", args=[equipment.pk]), follow=True
    )
    assert b"window.djangoMessages" in response.content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ui.py -q`
Expected: 2 failures (`nav-link-active` and `window.djangoMessages` not in content).

- [ ] **Step 3: Rewrite `templates/base.html`** with exactly:

```html
{% load static %}
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}{{ HOSPITAL_NAME }} CMMS{% endblock %}</title>
  <link rel="stylesheet" href="{% static 'css/app.css' %}">
  <link rel="icon" type="image/png" href="{% static 'img/favicon.png' %}">
  <script>
    (function () {
      var t = localStorage.getItem("hemdesk-theme");
      if (t === "dark" || (!t && window.matchMedia("(prefers-color-scheme: dark)").matches))
        document.documentElement.classList.add("dark");
    })();
  </script>
  <script src="{% static 'js/htmx.min.js' %}" defer></script>
  <script src="{% static 'js/app.js' %}" defer></script>
  <script src="{% static 'js/alpine.min.js' %}" defer></script>
</head>
<body class="bg-slate-100 text-slate-900 antialiased dark:bg-slate-950 dark:text-slate-100">
<div class="flex min-h-screen">
  {% if user.is_authenticated %}
  {% with active=request.resolver_match.url_name %}
  <aside class="flex w-60 shrink-0 flex-col bg-gradient-to-b from-sky-950 to-sky-900 text-white dark:border-r dark:border-slate-800 dark:from-slate-950 dark:to-slate-900">
    <a href="{% url 'home' %}"
       class="flex items-center gap-2.5 border-b border-white/10 px-4 py-4">
      <img src="{% static 'img/favicon.png' %}" alt="HEMDESK" class="h-8 w-8 rounded-lg">
      <span class="text-lg font-bold tracking-wide">HEMDESK</span>
    </a>
    <nav class="flex-1 overflow-y-auto px-3 py-2">
      <p class="nav-heading">Operations</p>
      <a href="{% url 'equipment_list' %}"
         class="nav-link {% if active in 'equipment_list equipment_detail equipment_create equipment_edit equipment_condemn' %}nav-link-active{% endif %}">
        <svg class="size-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/></svg>
        Equipment
      </a>
      <a href="{% url 'complaint_new' %}"
         class="nav-link {% if active == 'complaint_new' %}nav-link-active{% endif %}">
        <svg class="size-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>
        New Complaint
      </a>
      <a href="{% url 'my_complaints' %}"
         class="nav-link {% if active == 'my_complaints' %}nav-link-active{% endif %}">
        <svg class="size-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/></svg>
        My Complaints
      </a>
      {% if user.is_engineer_or_admin %}
      <p class="nav-heading">Insights</p>
      <a href="{% url 'complaint_queue' %}"
         class="nav-link {% if active in 'complaint_queue complaint_close workorder_detail workorder_complete' %}nav-link-active{% endif %}">
        <svg class="size-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/></svg>
        Queue
      </a>
      <a href="{% url 'dashboard' %}"
         class="nav-link {% if active in 'dashboard engineer_resolved' %}nav-link-active{% endif %}">
        <svg class="size-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/></svg>
        Dashboard
      </a>
      {% endif %}
      {% if user.is_staff %}
      <p class="nav-heading">Admin</p>
      <a href="{% url 'admin:index' %}" class="nav-link">
        <svg class="size-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1 1 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/></svg>
        Admin
      </a>
      {% endif %}
    </nav>
    <div class="space-y-1 border-t border-white/10 px-3 py-3">
      <div class="mb-1 flex items-center gap-2.5 px-2">
        <span class="flex size-8 shrink-0 items-center justify-center rounded-full bg-sky-500/30 text-xs font-bold uppercase">
          {% if user.first_name %}{{ user.first_name|slice:":1" }}{{ user.last_name|slice:":1" }}{% else %}{{ user.username|slice:":2" }}{% endif %}
        </span>
        <span class="min-w-0">
          <span class="block truncate text-sm font-medium">{{ user.get_full_name|default:user.username }}</span>
          <span class="block text-xs text-sky-200/70">{{ user.employee_id }}</span>
        </span>
      </div>
      <button type="button" onclick="toggleTheme()" class="nav-link">
        <svg class="size-4 shrink-0 dark:hidden" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>
        <svg class="hidden size-4 shrink-0 dark:block" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg>
        <span class="dark:hidden">Dark mode</span><span class="hidden dark:inline">Light mode</span>
      </button>
      <a href="{% url 'password_change' %}"
         class="nav-link {% if active == 'password_change' %}nav-link-active{% endif %}">
        <svg class="size-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21 2-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0 3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg>
        Change password
      </a>
      <form method="post" action="{% url 'logout' %}">
        {% csrf_token %}
        <button class="nav-link">
          <svg class="size-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/></svg>
          Log out
        </button>
      </form>
    </div>
  </aside>
  {% endwith %}
  {% endif %}
  <div class="flex min-w-0 flex-1 flex-col">
    <header class="flex h-14 items-center gap-4 border-b border-slate-200 bg-white/80 px-6 backdrop-blur dark:border-slate-800 dark:bg-slate-900/80">
      {% if user.is_authenticated %}
        <h2 class="text-sm font-semibold text-slate-700 dark:text-slate-200">{% block page_title %}{% endblock %}</h2>
        <span class="ml-auto text-sm text-slate-500 dark:text-slate-400">{{ HOSPITAL_NAME }}</span>
      {% else %}
        <a href="{% url 'home' %}" class="flex items-center gap-2">
          <img src="{% static 'img/favicon.png' %}" alt="HEMDESK" class="h-8 w-8 rounded-lg">
          <span class="text-lg font-bold tracking-wide text-sky-900 dark:text-sky-300">HEMDESK</span>
        </a>
        <span class="ml-auto text-sm text-slate-500 dark:text-slate-400">{{ HOSPITAL_NAME }}</span>
      {% endif %}
    </header>
    <main class="flex-1 px-6 py-6">
      <div class="mx-auto max-w-6xl animate-fade-up">
        {% block content %}{% endblock %}
      </div>
    </main>
  </div>
</div>
{% if messages %}
<script>
  window.djangoMessages = [
    {% for message in messages %}{ level: "{{ message.tags|default:'info'|escapejs }}", text: "{{ message|escapejs }}" }{% if not forloop.last %},{% endif %}{% endfor %}
  ];
</script>
{% endif %}
<div x-data="toasts"
     class="pointer-events-none fixed right-4 top-4 z-50 flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2">
  <template x-for="t in items" :key="t.id">
    <div class="card pointer-events-auto relative overflow-hidden p-3 pr-9 text-sm shadow-lg"
         x-transition:enter="transition duration-200 ease-out"
         x-transition:enter-start="translate-x-4 opacity-0"
         x-transition:enter-end="translate-x-0 opacity-100"
         x-transition:leave="transition duration-150 ease-in"
         x-transition:leave-start="opacity-100"
         x-transition:leave-end="opacity-0">
      <div class="flex items-start gap-2.5">
        <span class="mt-1.5 size-2 shrink-0 rounded-full"
              :class="t.level.includes('error') ? 'bg-red-500'
                      : t.level.includes('warning') ? 'bg-amber-500'
                      : t.level.includes('success') ? 'bg-emerald-500' : 'bg-sky-500'"></span>
        <span x-text="t.text"></span>
      </div>
      <button class="absolute right-2 top-2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
              @click="dismiss(t.id)" aria-label="Dismiss">
        <svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
      </button>
      <span class="toast-progress absolute bottom-0 left-0 h-0.5 bg-sky-500/60"></span>
    </div>
  </template>
</div>
{% block extra_js %}{% endblock %}
</body>
</html>
```

- [ ] **Step 4: Delete `templates/partials/_messages.html`**

```bash
git rm templates/partials/_messages.html
```

- [ ] **Step 5: Rebuild CSS, run tests**

Run: `bin/tailwindcss.exe -i static/css/input.css -o static/css/app.css --minify && uv run pytest -q`
Expected: full suite passes, including the two new tests.

- [ ] **Step 6: Commit**

```bash
git add templates/base.html tests/test_ui.py static/css/app.css
git commit -m "feat: Clinical Sky app shell — icon sidebar, active nav, toasts, dark mode"
```

---

### Task 4: Login page

**Files:**
- Modify: `templates/registration/login.html` (full rewrite)

**Interfaces:**
- Consumes: base blocks, `.card`, `.btn-primary`, auto `.field` styling (Task 1).

- [ ] **Step 1: Rewrite `templates/registration/login.html`** with exactly:

```html
{% extends "base.html" %}
{% load static %}
{% block title %}Log in — {{ HOSPITAL_NAME }}{% endblock %}
{% block content %}
<div class="card mx-auto mt-10 grid max-w-3xl overflow-hidden md:grid-cols-2">
  <div class="relative hidden flex-col justify-between bg-gradient-to-br from-sky-950 via-sky-900 to-sky-800 p-8 text-white md:flex">
    <div class="pointer-events-none absolute inset-0 opacity-10"
         style="background-image: radial-gradient(currentColor 1px, transparent 1px); background-size: 22px 22px;"></div>
    <div class="relative flex items-center gap-2.5">
      <img src="{% static 'img/favicon.png' %}" alt="HEMDESK" class="h-9 w-9 rounded-lg">
      <span class="text-xl font-bold tracking-wide">HEMDESK</span>
    </div>
    <div class="relative">
      <h2 class="text-2xl font-bold leading-snug">Every device.<br>Every repair.<br>One desk.</h2>
      <p class="mt-3 text-sm text-sky-200">
        {{ HOSPITAL_NAME }}'s medical equipment, complaints and repairs — tracked end to end.
      </p>
    </div>
    <p class="relative text-xs text-sky-300/70">Hospital Equipment Management Desk</p>
  </div>
  <div class="p-8">
    <img src="{% static 'img/logo.png' %}" alt="{{ HOSPITAL_NAME }}" class="mb-6 h-14 w-auto md:hidden">
    <h1 class="text-xl font-bold">Welcome back</h1>
    <p class="mb-6 mt-1 text-sm text-slate-500 dark:text-slate-400">Sign in to continue.</p>
    {% if form.errors %}
      <div class="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300">
        Invalid username or password.
      </div>
    {% endif %}
    <form method="post" class="space-y-4">
      {% csrf_token %}
      <div>
        <label class="mb-1 block text-sm font-medium" for="id_username">Username</label>
        {{ form.username }}
      </div>
      <div>
        <label class="mb-1 block text-sm font-medium" for="id_password">Password</label>
        {{ form.password }}
      </div>
      <button class="btn-primary w-full">Log in</button>
    </form>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 2: Rebuild CSS, run tests**

Run: `bin/tailwindcss.exe -i static/css/input.css -o static/css/app.css --minify && uv run pytest -q`
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add templates/registration/login.html static/css/app.css
git commit -m "feat: split-screen brand login page"
```

---

### Task 5: Home page (greeting + quick actions)

**Files:**
- Modify: `templates/home.html` (full rewrite)

- [ ] **Step 1: Rewrite `templates/home.html`** with exactly:

```html
{% extends "base.html" %}
{% load static %}
{% block title %}Welcome — {{ HOSPITAL_NAME }}{% endblock %}
{% block page_title %}Home{% endblock %}
{% block content %}
{% now "G" as hour %}
<div class="mt-2">
  <h1 class="text-2xl font-bold">
    {% if hour|add:"0" < 5 %}Working late{% elif hour|add:"0" < 12 %}Good morning{% elif hour|add:"0" < 17 %}Good afternoon{% else %}Good evening{% endif %},
    {{ user.first_name|default:user.username }} 👋
  </h1>
  <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
    {{ HOSPITAL_NAME }} · signed in as {{ user.get_full_name|default:user.username }} ({{ user.employee_id }})
  </p>
</div>
<div class="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
  <a href="{% url 'complaint_new' %}" class="card card-hover group p-5">
    <span class="flex size-10 items-center justify-center rounded-lg bg-amber-100 text-amber-700 transition group-hover:scale-105 dark:bg-amber-500/15 dark:text-amber-300">
      <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>
    </span>
    <h2 class="mt-3 font-semibold">Report a fault</h2>
    <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">Something broken? Lodge a complaint and the biomedical team takes it from there.</p>
  </a>
  <a href="{% url 'equipment_list' %}" class="card card-hover group p-5">
    <span class="flex size-10 items-center justify-center rounded-lg bg-sky-100 text-sky-700 transition group-hover:scale-105 dark:bg-sky-500/15 dark:text-sky-300">
      <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/></svg>
    </span>
    <h2 class="mt-3 font-semibold">Browse equipment</h2>
    <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">The full device registry — status, department, history and repairs.</p>
  </a>
  <a href="{% url 'my_complaints' %}" class="card card-hover group p-5">
    <span class="flex size-10 items-center justify-center rounded-lg bg-emerald-100 text-emerald-700 transition group-hover:scale-105 dark:bg-emerald-500/15 dark:text-emerald-300">
      <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/></svg>
    </span>
    <h2 class="mt-3 font-semibold">My complaints</h2>
    <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">Track what you've reported and confirm completed repairs.</p>
  </a>
  {% if user.is_engineer_or_admin %}
  <a href="{% url 'complaint_queue' %}" class="card card-hover group p-5">
    <span class="flex size-10 items-center justify-center rounded-lg bg-violet-100 text-violet-700 transition group-hover:scale-105 dark:bg-violet-500/15 dark:text-violet-300">
      <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/></svg>
    </span>
    <h2 class="mt-3 font-semibold">Complaint queue</h2>
    <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">Open complaints waiting for an engineer. Live-updating.</p>
  </a>
  <a href="{% url 'dashboard' %}" class="card card-hover group p-5">
    <span class="flex size-10 items-center justify-center rounded-lg bg-rose-100 text-rose-700 transition group-hover:scale-105 dark:bg-rose-500/15 dark:text-rose-300">
      <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/></svg>
    </span>
    <h2 class="mt-3 font-semibold">Dashboard</h2>
    <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">KPIs, downtime, fault trends and engineer performance — last 30 days.</p>
  </a>
  {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 2: Rebuild CSS, run tests**

Run: `bin/tailwindcss.exe -i static/css/input.css -o static/css/app.css --minify && uv run pytest -q`
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add templates/home.html static/css/app.css
git commit -m "feat: home page greeting and quick-action cards"
```

---

### Task 6: Equipment list — live search, filter chips, skeleton

**Files:**
- Create: `templates/equipment/_list_rows.html`
- Modify: `templates/equipment/list.html` (full rewrite)
- Modify: `apps/equipment/views.py:18-36` (`EquipmentListView`)
- Test: `tests/test_ui.py` (append)

**Interfaces:**
- Consumes: `.table`, `.table-card`, `.row-hover`, `.badge-*`, `.skeleton`, `.btn-primary` (Task 1).
- Produces: `EquipmentListView.get_template_names()` returning `["equipment/_list_rows.html"]` when the `HX-Request` header is present. `_list_rows.html` renders `<tr>` rows for `object_list` (used by both full page and htmx swap).

- [ ] **Step 1: Write failing tests** — append to `tests/test_ui.py`:

```python
def test_equipment_list_htmx_returns_rows_partial(client, engineer, equipment):
    client.force_login(engineer)
    response = client.get(reverse("equipment_list"), HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    assert b"<html" not in response.content
    assert b"SN-0001" in response.content


def test_equipment_list_htmx_status_filter(client, engineer, make_equipment):
    make_equipment(serial_number="SN-OK", status="working")
    make_equipment(serial_number="SN-BAD", status="in_repair")
    client.force_login(engineer)
    response = client.get(
        reverse("equipment_list"), {"status": "in_repair"}, HTTP_HX_REQUEST="true"
    )
    assert b"SN-BAD" in response.content
    assert b"SN-OK" not in response.content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ui.py -q`
Expected: the two new tests fail (`<html` IS in content — full page returned).

- [ ] **Step 3: Modify `EquipmentListView`** in `apps/equipment/views.py` — add `get_template_names` to the class:

```python
class EquipmentListView(LoginRequiredMixin, ListView):
    model = Equipment
    template_name = "equipment/list.html"
    paginate_by = 25

    def get_template_names(self):
        if self.request.headers.get("HX-Request"):
            return ["equipment/_list_rows.html"]
        return [self.template_name]

    def get_queryset(self):
        qs = super().get_queryset().select_related("department")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(serial_number__icontains=q)
                | Q(name__icontains=q)
                | Q(model_number__icontains=q)
                | Q(manufacturer__icontains=q)
            )
        status = self.request.GET.get("status", "")
        if status:
            qs = qs.filter(status=status)
        return qs
```

- [ ] **Step 4: Create `templates/equipment/_list_rows.html`** with exactly:

```html
{% for eq in object_list %}
<tr class="row-hover cursor-pointer" onclick="window.location='{% url 'equipment_detail' eq.pk %}'">
  <td><a class="link" href="{% url 'equipment_detail' eq.pk %}">{{ eq.name }}</a></td>
  <td>{{ eq.model_number }}</td>
  <td class="font-mono text-xs">{{ eq.serial_number }}</td>
  <td>{{ eq.department }}</td>
  <td>
    {% if eq.status == 'working' %}<span class="badge-working"><span class="size-1.5 rounded-full bg-current"></span>Working</span>
    {% elif eq.status == 'in_repair' %}<span class="badge-repair"><span class="size-1.5 rounded-full bg-current"></span>In Repair</span>
    {% else %}<span class="badge-danger"><span class="size-1.5 rounded-full bg-current"></span>Condemned</span>{% endif %}
  </td>
  <td>{% if eq.is_critical_asset %}<span class="text-amber-500" title="Critical asset">★</span>{% endif %}</td>
</tr>
{% empty %}
<tr><td colspan="6" class="p-6 text-center text-slate-500 dark:text-slate-400">No equipment found.</td></tr>
{% endfor %}
```

- [ ] **Step 5: Rewrite `templates/equipment/list.html`** with exactly:

```html
{% extends "base.html" %}
{% block title %}Equipment Registry{% endblock %}
{% block page_title %}Equipment Registry{% endblock %}
{% block content %}
<div class="mb-5 flex items-center justify-between">
  <div>
    <h1 class="text-2xl font-bold">Equipment Registry</h1>
    <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">Search updates as you type.</p>
  </div>
  {% if user.is_engineer_or_admin %}
    <a href="{% url 'equipment_create' %}" class="btn-primary">+ Add Equipment</a>
  {% endif %}
</div>
<form id="eq-filter" method="get" class="mb-4 flex flex-wrap items-center gap-2" onsubmit="return false">
  <div class="relative w-80 max-w-full">
    <svg class="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
    <input type="search" name="q" value="{{ request.GET.q }}" placeholder="Search serial, name, model…"
           class="field pl-9" autocomplete="off"
           hx-get="{% url 'equipment_list' %}" hx-trigger="input changed delay:300ms, search"
           hx-target="#eq-rows" hx-include="#eq-filter" hx-indicator="#eq-skeleton">
  </div>
  <div class="flex gap-1.5" role="radiogroup" aria-label="Status filter">
    {% for value, label in status_choices %}
    <label class="cursor-pointer">
      <input type="radio" name="status" value="{{ value }}" class="peer sr-only"
             {% if request.GET.status == value or not request.GET.status and not value %}checked{% endif %}
             hx-get="{% url 'equipment_list' %}" hx-trigger="change"
             hx-target="#eq-rows" hx-include="#eq-filter" hx-indicator="#eq-skeleton">
      <span class="inline-flex rounded-full border border-slate-300 bg-white px-3 py-1 text-xs font-medium text-slate-600 transition peer-checked:border-sky-600 peer-checked:bg-sky-600 peer-checked:text-white dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">{{ label }}</span>
    </label>
    {% endfor %}
  </div>
</form>
<div class="table-card">
  <table class="table">
    <thead><tr>
      <th>Name</th><th>Model</th><th>Serial #</th>
      <th>Department</th><th>Status</th><th>Critical</th>
    </tr></thead>
    <tbody id="eq-skeleton" class="htmx-indicator">
      {% for _ in "123" %}
      <tr>
        <td><span class="skeleton block h-4 w-28"></span></td>
        <td><span class="skeleton block h-4 w-16"></span></td>
        <td><span class="skeleton block h-4 w-20"></span></td>
        <td><span class="skeleton block h-4 w-24"></span></td>
        <td><span class="skeleton block h-4 w-16"></span></td>
        <td><span class="skeleton block h-4 w-6"></span></td>
      </tr>
      {% endfor %}
    </tbody>
    <tbody id="eq-rows">
      {% include "equipment/_list_rows.html" %}
    </tbody>
  </table>
</div>
{% if is_paginated %}
<div class="mt-4 flex items-center justify-between text-sm">
  <span class="text-slate-500 dark:text-slate-400">Page {{ page_obj.number }} of {{ paginator.num_pages }}</span>
  <div class="flex gap-2">
    {% if page_obj.has_previous %}
      <a class="btn-ghost btn-sm" href="?q={{ request.GET.q|urlencode }}&status={{ request.GET.status|urlencode }}&page={{ page_obj.previous_page_number }}">← Prev</a>
    {% endif %}
    {% if page_obj.has_next %}
      <a class="btn-ghost btn-sm" href="?q={{ request.GET.q|urlencode }}&status={{ request.GET.status|urlencode }}&page={{ page_obj.next_page_number }}">Next →</a>
    {% endif %}
  </div>
</div>
{% endif %}
{% endblock %}
```

- [ ] **Step 6: Add `status_choices` to the view context** — in `EquipmentListView` add:

```python
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status_choices"] = [("", "All")] + list(EquipmentStatus.choices)
        return ctx
```

(`EquipmentStatus` is already imported in `apps/equipment/views.py`.)

- [ ] **Step 7: Rebuild CSS, run tests**

Run: `bin/tailwindcss.exe -i static/css/input.css -o static/css/app.css --minify && uv run pytest -q`
Expected: all pass, including the two new htmx tests.

- [ ] **Step 8: Commit**

```bash
git add templates/equipment/list.html templates/equipment/_list_rows.html apps/equipment/views.py tests/test_ui.py static/css/app.css
git commit -m "feat: equipment registry live search with filter chips and skeleton loading"
```

---

### Task 7: Equipment detail — status timeline and work-order cards

**Files:**
- Modify: `templates/equipment/detail.html` (full rewrite)

- [ ] **Step 1: Rewrite `templates/equipment/detail.html`** with exactly:

```html
{% extends "base.html" %}
{% block title %}{{ equipment.name }}{% endblock %}
{% block page_title %}Equipment{% endblock %}
{% block content %}
<div class="mb-5 flex flex-wrap items-start justify-between gap-3">
  <div>
    <h1 class="text-2xl font-bold">{{ equipment.name }} <span class="font-normal text-slate-400">{{ equipment.model_number }}</span></h1>
    <p class="mt-0.5 font-mono text-sm text-slate-500 dark:text-slate-400">{{ equipment.serial_number }}</p>
  </div>
  {% if equipment.status == 'working' %}<span class="badge-working px-3 py-1 text-sm"><span class="size-2 rounded-full bg-current"></span>{{ equipment.get_status_display }}</span>
  {% elif equipment.status == 'in_repair' %}<span class="badge-repair px-3 py-1 text-sm"><span class="size-2 rounded-full bg-current"></span>{{ equipment.get_status_display }}</span>
  {% else %}<span class="badge-danger px-3 py-1 text-sm"><span class="size-2 rounded-full bg-current"></span>{{ equipment.get_status_display }}</span>{% endif %}
</div>
<div class="grid gap-6 md:grid-cols-2">
  <div class="card p-5">
    <h2 class="mb-3 font-semibold">Details</h2>
    <dl class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
      <dt class="text-slate-500 dark:text-slate-400">Manufacturer</dt><dd>{{ equipment.manufacturer }}</dd>
      <dt class="text-slate-500 dark:text-slate-400">Vendor</dt><dd>{{ equipment.vendor|default:"—" }}</dd>
      <dt class="text-slate-500 dark:text-slate-400">Department</dt><dd>{{ equipment.department }}</dd>
      <dt class="text-slate-500 dark:text-slate-400">Critical asset</dt>
      <dd>{% if equipment.is_critical_asset %}<span class="text-amber-500">★</span> Yes{% else %}No{% endif %}</dd>
      <dt class="text-slate-500 dark:text-slate-400">Purchased</dt><dd>{{ equipment.purchase_date|default:"—" }}</dd>
      <dt class="text-slate-500 dark:text-slate-400">Installed</dt><dd>{{ equipment.installation_date|default:"—" }}</dd>
      <dt class="text-slate-500 dark:text-slate-400">Repairs completed</dt><dd>{{ completed_repair_count }}</dd>
      {% if equipment.status == 'condemned' %}
      <dt class="text-slate-500 dark:text-slate-400">Condemned</dt>
      <dd>{{ equipment.condemned_at }} — {{ equipment.condemned_location }}</dd>
      {% endif %}
    </dl>
    {% if can_engineer and equipment.status != 'condemned' %}
    <div class="mt-5 flex flex-wrap gap-2 border-t border-slate-100 pt-4 dark:border-slate-800">
      <a href="{% url 'equipment_edit' equipment.pk %}" class="btn-ghost btn-sm">Edit</a>
      <form method="post" action="{% url 'workorder_open' equipment.pk %}">
        {% csrf_token %}
        <button class="btn-warn btn-sm">Open Work Order</button>
      </form>
      <a href="{% url 'equipment_condemn' equipment.pk %}" class="btn-danger btn-sm">Condemn…</a>
    </div>
    {% endif %}
  </div>
  <div class="card p-5">
    <h2 class="mb-3 font-semibold">Status History</h2>
    <ol class="relative space-y-4 border-l border-slate-200 pl-5 dark:border-slate-700">
      {% for event in status_events %}
      <li class="relative">
        <span class="absolute -left-[26px] top-1 size-3 rounded-full border-2 border-white bg-sky-500 dark:border-slate-900"></span>
        <p class="text-xs text-slate-500 dark:text-slate-400">{{ event.created_at }}</p>
        <p class="text-sm">{{ event.get_old_status_display }} → <span class="font-medium">{{ event.get_new_status_display }}</span>
          <span class="text-slate-500 dark:text-slate-400">by {{ event.actor }}</span></p>
        {% if event.remark %}<p class="mt-0.5 text-sm text-slate-600 dark:text-slate-300">“{{ event.remark }}”</p>{% endif %}
      </li>
      {% empty %}<li class="text-sm text-slate-500 dark:text-slate-400">No status changes yet.</li>{% endfor %}
    </ol>
  </div>
</div>
<div class="card mt-6 p-5">
  <h2 class="mb-3 font-semibold">Work Orders</h2>
  <div class="space-y-3">
    {% for wo in work_orders %}
    <div class="flex flex-wrap items-center gap-2 rounded-lg border border-slate-100 px-4 py-3 text-sm dark:border-slate-800">
      {% if can_engineer %}
        <a class="link" href="{% url 'workorder_detail' wo.pk %}">WO #{{ wo.pk }}</a>
      {% else %}<span class="font-medium">WO #{{ wo.pk }}</span>{% endif %}
      {% if wo.status == 'completed' %}<span class="badge-working">{{ wo.get_status_display }}</span>
      {% elif wo.status == 'cancelled' %}<span class="badge-muted">{{ wo.get_status_display }}</span>
      {% elif wo.status == 'in_progress' %}<span class="badge-repair">{{ wo.get_status_display }}</span>
      {% else %}<span class="badge-info">{{ wo.get_status_display }}</span>{% endif %}
      {% if wo.outcome %}<span class="text-slate-500 dark:text-slate-400">{{ wo.get_outcome_display }}</span>{% endif %}
      {% if wo.fault_category %}<span class="badge-muted">{{ wo.get_fault_category_display }}</span>{% endif %}
      <span class="ml-auto text-slate-500 dark:text-slate-400">opened {{ wo.opened_at|date }}</span>
    </div>
    {% empty %}<p class="text-sm text-slate-500 dark:text-slate-400">No repairs recorded.</p>{% endfor %}
  </div>
</div>
{% endblock %}
```

- [ ] **Step 2: Rebuild CSS, run tests**

Run: `bin/tailwindcss.exe -i static/css/input.css -o static/css/app.css --minify && uv run pytest -q`
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add templates/equipment/detail.html static/css/app.css
git commit -m "feat: equipment detail with status timeline and work-order cards"
```

---

### Task 8: Forms restyle (equipment, condemn, close, complete, password)

**Files:**
- Modify: `templates/equipment/form.html`
- Modify: `templates/equipment/condemn.html`
- Modify: `templates/maintenance/complaint_close.html`
- Modify: `templates/maintenance/workorder_complete.html`
- Modify: `templates/registration/password_change_form.html`
- Modify: `templates/registration/password_change_done.html`

All six keep their existing field loops/logic — only the wrapper, headings, buttons and error/help styling change. Inputs are auto-styled by the Task 1 `main input/select/textarea` rule.

- [ ] **Step 1: Rewrite `templates/equipment/form.html`**:

```html
{% extends "base.html" %}
{% block title %}{% if equipment %}Edit{% else %}Add{% endif %} Equipment{% endblock %}
{% block page_title %}Equipment{% endblock %}
{% block content %}
<div class="card mx-auto max-w-xl p-6">
  <h1 class="text-xl font-bold">
    {% if equipment %}Edit {{ equipment.serial_number }}{% else %}Add Equipment{% endif %}
  </h1>
  <p class="mb-5 mt-1 text-sm text-slate-500 dark:text-slate-400">
    {% if equipment %}Update the registry record.{% else %}Register a new device in the registry.{% endif %}
  </p>
  <form method="post" class="space-y-4">
    {% csrf_token %}
    {% for field in form %}
    <div>
      <label class="mb-1 block text-sm font-medium" for="{{ field.id_for_label }}">{{ field.label }}</label>
      {{ field }}
      {% if field.help_text %}<p class="mt-1 text-xs text-slate-500 dark:text-slate-400">{{ field.help_text }}</p>{% endif %}
      {% for error in field.errors %}<p class="mt-1 text-sm text-red-700 dark:text-red-400">{{ error }}</p>{% endfor %}
    </div>
    {% endfor %}
    <div class="flex justify-end gap-2 border-t border-slate-100 pt-4 dark:border-slate-800">
      <button class="btn-primary">Save</button>
    </div>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 2: Rewrite `templates/equipment/condemn.html`**:

```html
{% extends "base.html" %}
{% block title %}Condemn {{ equipment.serial_number }}{% endblock %}
{% block page_title %}Equipment{% endblock %}
{% block content %}
<div class="card mx-auto max-w-xl overflow-hidden">
  <div class="border-b border-red-200 bg-red-50 px-6 py-4 dark:border-red-500/30 dark:bg-red-500/10">
    <h1 class="text-xl font-bold text-red-800 dark:text-red-300">Condemn equipment</h1>
    <p class="mt-1 text-sm text-red-700/80 dark:text-red-300/80">This cannot be undone.</p>
  </div>
  <div class="p-6">
    <p class="mb-5 text-sm text-slate-600 dark:text-slate-300">
      {{ equipment }} will be permanently retired. Its record and full history
      are preserved forever. Any active work order and open complaints will be
      closed automatically.
    </p>
    <form method="post" class="space-y-4">
      {% csrf_token %}
      {% for field in form %}
      <div>
        <label class="mb-1 block text-sm font-medium" for="{{ field.id_for_label }}">{{ field.label }}</label>
        {{ field }}
        {% if field.help_text %}<p class="mt-1 text-xs text-slate-500 dark:text-slate-400">{{ field.help_text }}</p>{% endif %}
        {% for error in field.errors %}<p class="mt-1 text-sm text-red-700 dark:text-red-400">{{ error }}</p>{% endfor %}
      </div>
      {% endfor %}
      <div class="flex justify-end gap-2 border-t border-slate-100 pt-4 dark:border-slate-800">
        <a href="{% url 'equipment_detail' equipment.pk %}" class="btn-ghost">Cancel</a>
        <button class="btn-danger">Condemn permanently</button>
      </div>
    </form>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 3: Rewrite `templates/maintenance/complaint_close.html`**:

```html
{% extends "base.html" %}
{% block title %}Close Complaint #{{ complaint.pk }}{% endblock %}
{% block page_title %}Queue{% endblock %}
{% block content %}
<div class="card mx-auto max-w-xl p-6">
  <h1 class="text-xl font-bold">Close Complaint #{{ complaint.pk }}</h1>
  <p class="mb-5 mt-1 text-sm text-slate-500 dark:text-slate-400">
    {{ complaint.equipment }} — “{{ complaint.description|truncatechars:120 }}”
    by {{ complaint.reporter }} ({{ complaint.created_at }})
  </p>
  <form method="post" class="space-y-4">
    {% csrf_token %}
    {% for error in form.non_field_errors %}
      <p class="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300">{{ error }}</p>
    {% endfor %}
    <div>
      <label class="mb-1 block text-sm font-medium">Reason</label>
      {{ form.close_reason }}
    </div>
    <div>
      <label class="mb-1 block text-sm font-medium">Original complaint (if duplicate)</label>
      {{ form.duplicate_of }}
    </div>
    <div>
      <label class="mb-1 block text-sm font-medium">Note</label>
      {{ form.close_note }}
      <p class="mt-1 text-xs text-slate-500 dark:text-slate-400">
        e.g. “Already reported by Nurse Khan, complaint #482.”</p>
    </div>
    <div class="flex justify-end gap-2 border-t border-slate-100 pt-4 dark:border-slate-800">
      <a href="{% url 'complaint_queue' %}" class="btn-ghost">Back to queue</a>
      <button class="btn-primary">Close complaint</button>
    </div>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 4: Rewrite `templates/maintenance/workorder_complete.html`**:

```html
{% extends "base.html" %}
{% block title %}Complete WO #{{ wo.pk }}{% endblock %}
{% block page_title %}Work Order{% endblock %}
{% block content %}
<div class="card mx-auto max-w-xl p-6">
  <h1 class="text-xl font-bold">Complete Work Order #{{ wo.pk }}</h1>
  <p class="mb-5 mt-1 text-sm text-slate-500 dark:text-slate-400">{{ wo.equipment }}</p>
  <form method="post" class="space-y-4">
    {% csrf_token %}
    <div>
      <label class="mb-1 block text-sm font-medium">Fault category <span class="text-red-600">*</span></label>
      {{ form.fault_category }}
      {% for error in form.fault_category.errors %}
        <p class="mt-1 text-sm text-red-700 dark:text-red-400">{{ error }}</p>{% endfor %}
    </div>
    <div>
      <label class="mb-1 block text-sm font-medium">Who worked on this repair?</label>
      {{ form.participants }}
      <p class="mt-1 text-xs text-slate-500 dark:text-slate-400">{{ form.participants.help_text }}</p>
    </div>
    <div>
      <label class="mb-1 block text-sm font-medium">Closing remark (optional)</label>
      {{ form.remark }}
    </div>
    <div class="flex justify-end gap-2 border-t border-slate-100 pt-4 dark:border-slate-800">
      <a href="{% url 'workorder_detail' wo.pk %}" class="btn-ghost">Cancel</a>
      <button class="btn-success">Mark repaired &amp; return to service</button>
    </div>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 5: Rewrite `templates/registration/password_change_form.html`**:

```html
{% extends "base.html" %}
{% block title %}Change password{% endblock %}
{% block page_title %}Account{% endblock %}
{% block content %}
<div class="card mx-auto max-w-md p-8">
  <h1 class="text-xl font-bold">Change your password</h1>
  <p class="mb-5 mt-1 text-sm text-slate-500 dark:text-slate-400">Pick something strong and unique.</p>
  {% if form.non_field_errors %}
    <div class="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300">
      {{ form.non_field_errors }}
    </div>
  {% endif %}
  <form method="post" class="space-y-4">
    {% csrf_token %}
    {% for field in form %}
    <div>
      <label class="mb-1 block text-sm font-medium" for="{{ field.id_for_label }}">{{ field.label }}</label>
      {{ field }}
      {% for error in field.errors %}
        <p class="mt-1 text-sm text-red-700 dark:text-red-400">{{ error }}</p>
      {% endfor %}
      {% if field.help_text %}
        <div class="mt-1 text-xs text-slate-500 dark:text-slate-400">{{ field.help_text|safe }}</div>
      {% endif %}
    </div>
    {% endfor %}
    <button class="btn-primary w-full">Update password</button>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 6: Rewrite `templates/registration/password_change_done.html`**:

```html
{% extends "base.html" %}
{% block title %}Password changed{% endblock %}
{% block page_title %}Account{% endblock %}
{% block content %}
<div class="card mx-auto max-w-md p-8 text-center">
  <span class="mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300">
    <svg class="size-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
  </span>
  <h1 class="text-xl font-bold">Password updated</h1>
  <p class="mb-6 mt-1 text-sm text-slate-500 dark:text-slate-400">
    Your password has been changed. You are still logged in.
  </p>
  <a href="{% url 'home' %}" class="btn-primary">Back to the app</a>
</div>
{% endblock %}
```

- [ ] **Step 7: Rebuild CSS, run tests**

Run: `bin/tailwindcss.exe -i static/css/input.css -o static/css/app.css --minify && uv run pytest -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add templates/equipment/form.html templates/equipment/condemn.html templates/maintenance/complaint_close.html templates/maintenance/workorder_complete.html templates/registration/password_change_form.html templates/registration/password_change_done.html static/css/app.css
git commit -m "feat: unified form card styling across all form pages"
```

---

### Task 9: Complaint form, my complaints, search-results partial

**Files:**
- Modify: `templates/maintenance/complaint_form.html`
- Modify: `templates/maintenance/my_complaints.html`
- Modify: `templates/equipment/_search_results.html`

- [ ] **Step 1: Rewrite `templates/equipment/_search_results.html`** (used by the complaint form picker):

```html
{% for eq in results %}
<button type="button"
        class="block w-full border-b border-slate-100 px-3 py-2 text-left text-sm transition-colors last:border-b-0 hover:bg-sky-50 dark:border-slate-800 dark:hover:bg-slate-800"
        @click="select({{ eq.pk }}, '{{ eq.name|escapejs }}',
                '{{ eq.model_number|escapejs }}', '{{ eq.serial_number|escapejs }}',
                '{{ eq.department|escapejs }}')">
  <span class="font-medium">{{ eq.name }}</span>
  <span class="text-slate-500 dark:text-slate-400">{{ eq.model_number }} ·
    <span class="font-mono text-xs">{{ eq.serial_number }}</span> · {{ eq.department }}</span>
</button>
{% empty %}
<div class="px-3 py-2 text-sm text-slate-500 dark:text-slate-400">No matching equipment.</div>
{% endfor %}
```

- [ ] **Step 2: Rewrite `templates/maintenance/complaint_form.html`** (keep the Alpine `select()` contract exactly as-is):

```html
{% extends "base.html" %}
{% block title %}New Complaint{% endblock %}
{% block page_title %}New Complaint{% endblock %}
{% block content %}
<div class="card mx-auto max-w-xl p-6"
     x-data="{ picked: null, name: '', model: '', serial: '', dept: '',
               select(id, name, model, serial, dept) {
                 this.picked = id; this.name = name; this.model = model;
                 this.serial = serial; this.dept = dept;
                 document.getElementById('id_equipment').value = id;
                 document.getElementById('search-results').innerHTML = '';
               } }">
  <h1 class="text-xl font-bold">Lodge a Complaint</h1>
  <p class="mb-5 mt-1 text-sm text-slate-500 dark:text-slate-400">
    Reporting as <strong>{{ user.get_full_name|default:user.username }}</strong>
    (ID: {{ user.employee_id }}) — attached automatically.
  </p>
  <div class="mb-4">
    <label class="mb-1 block text-sm font-medium">Find the equipment</label>
    <input type="search" name="q" placeholder="Type serial number, name or model…"
           autocomplete="off"
           hx-get="{% url 'equipment_search' %}" hx-trigger="input changed delay:300ms"
           hx-target="#search-results" hx-vals='{"exclude_unavailable": "1"}'>
    <div id="search-results"
         class="mt-1 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm empty:border-0 empty:shadow-none dark:border-slate-700 dark:bg-slate-900"></div>
  </div>
  <template x-if="picked">
    <div class="mb-4 rounded-lg border border-sky-200 bg-sky-50 p-3 text-sm dark:border-sky-500/30 dark:bg-sky-500/10">
      <div><span class="text-slate-500 dark:text-slate-400">Equipment:</span> <span x-text="name"></span>
           <span x-text="model"></span></div>
      <div><span class="text-slate-500 dark:text-slate-400">Serial #:</span>
           <span class="font-mono" x-text="serial"></span></div>
      <div><span class="text-slate-500 dark:text-slate-400">Department:</span> <span x-text="dept"></span></div>
    </div>
  </template>
  <form method="post" class="space-y-4">
    {% csrf_token %}
    {{ form.equipment }}
    <div>
      <label class="mb-1 block text-sm font-medium">What is wrong?</label>
      {{ form.description }}
      {% for error in form.description.errors %}
        <p class="mt-1 text-sm text-red-700 dark:text-red-400">{{ error }}</p>{% endfor %}
      {% for error in form.equipment.errors %}
        <p class="mt-1 text-sm text-red-700 dark:text-red-400">Please pick the equipment above.</p>{% endfor %}
    </div>
    <button class="btn-primary w-full" :disabled="!picked">Submit Complaint</button>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 3: Rewrite `templates/maintenance/my_complaints.html`**:

```html
{% extends "base.html" %}
{% block title %}My Complaints{% endblock %}
{% block page_title %}My Complaints{% endblock %}
{% block content %}
<h1 class="mb-4 text-2xl font-bold">My Complaints</h1>
{% if pending_confirmations %}
<div class="mb-4 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300">
  <svg class="size-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 8v4"/><path d="M12 16h.01"/></svg>
  You have {{ pending_confirmations }} repaired complaint{{ pending_confirmations|pluralize }} to confirm below.
</div>
{% endif %}
<div class="table-card">
  <table class="table">
    <thead><tr>
      <th>#</th><th>Equipment</th><th>Description</th><th>Lodged</th><th>Status</th>
    </tr></thead>
    <tbody>
      {% for c in complaints %}
      <tr class="row-hover">
        <td class="tabular-nums">{{ c.pk }}</td>
        <td>{{ c.equipment.name }}
          <span class="font-mono text-xs text-slate-500 dark:text-slate-400">{{ c.equipment.serial_number }}</span></td>
        <td>{{ c.description|truncatechars:80 }}</td>
        <td class="whitespace-nowrap">{{ c.created_at|date:"Y-m-d H:i" }}</td>
        <td>
          {% if c.status == 'closed' %}<span class="badge-muted">{{ c.get_status_display }}</span>
          {% elif c.status == 'attached' %}<span class="badge-repair">{{ c.get_status_display }}</span>
          {% else %}<span class="badge-info">{{ c.get_status_display }}</span>{% endif %}
          {% if c.close_reason %}<span class="text-xs text-slate-500 dark:text-slate-400">({{ c.get_close_reason_display }})</span>{% endif %}
        </td>
      </tr>
      {% if c.is_awaiting_confirmation %}
      <tr class="bg-amber-50 dark:bg-amber-500/10">
        <td colspan="5">
          <form method="post" action="{% url 'complaint_confirm' c.pk %}"
                class="flex flex-wrap items-center gap-3">
            {% csrf_token %}
            <span class="font-medium">Is the machine functional now?</span>
            <button name="functional" value="yes" class="btn-success btn-sm">Yes, functional</button>
            <button name="functional" value="no" class="btn-danger btn-sm">No, not functional</button>
          </form>
        </td>
      </tr>
      {% endif %}
      {% empty %}
      <tr><td colspan="5" class="p-6 text-center text-slate-500 dark:text-slate-400">
        You have not lodged any complaints.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

- [ ] **Step 4: Rebuild CSS, run tests**

Run: `bin/tailwindcss.exe -i static/css/input.css -o static/css/app.css --minify && uv run pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add templates/maintenance/complaint_form.html templates/maintenance/my_complaints.html templates/equipment/_search_results.html static/css/app.css
git commit -m "feat: restyle complaint form, my complaints, and equipment picker"
```

---

### Task 10: Queue — search, state filter, urgency tint

**Files:**
- Modify: `apps/maintenance/models.py` (add `Complaint.age_hours` property)
- Modify: `apps/maintenance/views.py:75-100` (`_open_complaints_queryset`, `complaint_queue`, `complaint_queue_rows`)
- Modify: `templates/maintenance/queue.html` (full rewrite)
- Modify: `templates/maintenance/_queue_rows.html` (full rewrite)
- Test: `tests/test_ui.py` (append)

**Interfaces:**
- Produces: `_open_complaints_queryset(request)` — now takes the request and applies `q` (text) and `state` (`unassigned`/`assigned`) GET filters; `Complaint.age_hours` → float hours since `created_at`.

- [ ] **Step 1: Write failing tests** — append to `tests/test_ui.py`:

```python
def test_queue_rows_text_filter(client, engineer, staff_user, make_equipment):
    from apps.maintenance.services import lodge_complaint

    eq1 = make_equipment(serial_number="SN-AAA")
    eq2 = make_equipment(serial_number="SN-BBB")
    lodge_complaint(staff_user, eq1, "screen flickers")
    lodge_complaint(staff_user, eq2, "no power")
    client.force_login(engineer)
    response = client.get(reverse("complaint_queue_rows"), {"q": "flickers"})
    assert b"SN-AAA" in response.content
    assert b"SN-BBB" not in response.content


def test_queue_rows_unassigned_filter(client, engineer, staff_user, equipment):
    from apps.maintenance.services import lodge_complaint, open_work_order

    lodge_complaint(staff_user, equipment, "no power")
    open_work_order(equipment, engineer)
    client.force_login(engineer)
    response = client.get(reverse("complaint_queue_rows"), {"state": "unassigned"})
    assert b"no power" not in response.content


def test_complaint_age_hours(staff_user, equipment):
    from apps.maintenance.services import lodge_complaint

    c = lodge_complaint(staff_user, equipment, "no power")
    assert 0 <= c.age_hours < 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ui.py -q`
Expected: 3 new failures (filters not applied; `age_hours` missing).

- [ ] **Step 3: Add `age_hours` property** to the `Complaint` model in `apps/maintenance/models.py` (next to `is_awaiting_confirmation`; **no migration needed**):

```python
    @property
    def age_hours(self):
        from django.utils import timezone

        return (timezone.now() - self.created_at).total_seconds() / 3600.0
```

- [ ] **Step 4: Update queue views** in `apps/maintenance/views.py`. Add `Q` to the imports at the top:

```python
from django.db.models import Q
```

Replace `_open_complaints_queryset`, `complaint_queue`, and `complaint_queue_rows` with:

```python
def _open_complaints_queryset(request):
    qs = (
        Complaint.objects.filter(
            status__in=[ComplaintStatus.OPEN, ComplaintStatus.ATTACHED]
        )
        .select_related("equipment__department", "reporter", "work_order")
        .order_by("-created_at")
    )
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(equipment__name__icontains=q)
            | Q(equipment__serial_number__icontains=q)
            | Q(description__icontains=q)
            | Q(reporter__username__icontains=q)
            | Q(reporter__first_name__icontains=q)
            | Q(reporter__last_name__icontains=q)
        )
    state = request.GET.get("state", "")
    if state == "unassigned":
        qs = qs.filter(work_order__isnull=True)
    elif state == "assigned":
        qs = qs.filter(work_order__isnull=False)
    return qs


@login_required
def complaint_queue(request):
    _require_engineer(request.user)
    return render(
        request,
        "maintenance/queue.html",
        {"complaints": _open_complaints_queryset(request)},
    )


@login_required
def complaint_queue_rows(request):
    _require_engineer(request.user)
    return render(
        request,
        "maintenance/_queue_rows.html",
        {"complaints": _open_complaints_queryset(request)},
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_ui.py -q`
Expected: PASS (all).

- [ ] **Step 6: Rewrite `templates/maintenance/queue.html`**:

```html
{% extends "base.html" %}
{% block title %}Complaint Queue{% endblock %}
{% block page_title %}Complaint Queue{% endblock %}
{% block content %}
<div class="mb-5">
  <h1 class="text-2xl font-bold">Complaint Queue</h1>
  <p class="mt-1 flex items-center gap-1.5 text-sm text-slate-500 dark:text-slate-400">
    <span class="relative flex size-2">
      <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75"></span>
      <span class="relative inline-flex size-2 rounded-full bg-emerald-500"></span>
    </span>
    Live — refreshes every 10 seconds.
  </p>
</div>
<form id="queue-filter" method="get" class="mb-4 flex flex-wrap items-center gap-2" onsubmit="return false">
  <div class="relative w-80 max-w-full">
    <svg class="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
    <input type="search" name="q" placeholder="Search equipment, serial, reporter…"
           class="field pl-9" autocomplete="off"
           hx-get="{% url 'complaint_queue_rows' %}" hx-trigger="input changed delay:300ms, search"
           hx-target="#queue-rows" hx-include="#queue-filter">
  </div>
  <div class="flex gap-1.5" role="radiogroup" aria-label="State filter">
    {% for value, label in queue_states %}{% endfor %}
    <label class="cursor-pointer">
      <input type="radio" name="state" value="" class="peer sr-only" checked
             hx-get="{% url 'complaint_queue_rows' %}" hx-trigger="change"
             hx-target="#queue-rows" hx-include="#queue-filter">
      <span class="inline-flex rounded-full border border-slate-300 bg-white px-3 py-1 text-xs font-medium text-slate-600 transition peer-checked:border-sky-600 peer-checked:bg-sky-600 peer-checked:text-white dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">All</span>
    </label>
    <label class="cursor-pointer">
      <input type="radio" name="state" value="unassigned" class="peer sr-only"
             hx-get="{% url 'complaint_queue_rows' %}" hx-trigger="change"
             hx-target="#queue-rows" hx-include="#queue-filter">
      <span class="inline-flex rounded-full border border-slate-300 bg-white px-3 py-1 text-xs font-medium text-slate-600 transition peer-checked:border-sky-600 peer-checked:bg-sky-600 peer-checked:text-white dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">Unassigned</span>
    </label>
    <label class="cursor-pointer">
      <input type="radio" name="state" value="assigned" class="peer sr-only"
             hx-get="{% url 'complaint_queue_rows' %}" hx-trigger="change"
             hx-target="#queue-rows" hx-include="#queue-filter">
      <span class="inline-flex rounded-full border border-slate-300 bg-white px-3 py-1 text-xs font-medium text-slate-600 transition peer-checked:border-sky-600 peer-checked:bg-sky-600 peer-checked:text-white dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">Has WO</span>
    </label>
  </div>
</form>
<div class="table-card">
  <table class="table">
    <thead><tr>
      <th>#</th><th>Equipment</th><th>Department</th><th>Description</th>
      <th>Reporter</th><th>Received</th><th>State</th><th></th>
    </tr></thead>
    <tbody id="queue-rows"
           hx-get="{% url 'complaint_queue_rows' %}" hx-trigger="every 10s"
           hx-include="#queue-filter" hx-swap="innerHTML">
      {% include "maintenance/_queue_rows.html" %}
    </tbody>
  </table>
</div>
{% endblock %}
```

(Note: the stray empty `{% for value, label in queue_states %}{% endfor %}` loop must NOT be included — write the three literal chip labels exactly as shown above without that line.)

- [ ] **Step 7: Rewrite `templates/maintenance/_queue_rows.html`**:

```html
{% for c in complaints %}
<tr class="row-hover {% if not c.work_order and c.age_hours > 24 %}bg-red-50/60 dark:bg-red-500/10{% elif not c.work_order and c.age_hours > 4 %}bg-amber-50/60 dark:bg-amber-500/10{% endif %}">
  <td class="tabular-nums">{{ c.pk }}</td>
  <td>
    <a class="link" href="{% url 'equipment_detail' c.equipment.pk %}">{{ c.equipment.name }}</a>
    <span class="font-mono text-xs text-slate-500 dark:text-slate-400">{{ c.equipment.serial_number }}</span>
  </td>
  <td>{{ c.equipment.department }}</td>
  <td>{{ c.description|truncatechars:60 }}</td>
  <td>{{ c.reporter.get_full_name|default:c.reporter.username }}
    <span class="text-xs text-slate-500 dark:text-slate-400">({{ c.reporter.employee_id }})</span></td>
  <td class="whitespace-nowrap">{{ c.created_at|timesince }} ago</td>
  <td>
    {% if c.work_order %}
      <a class="link" href="{% url 'workorder_detail' c.work_order.pk %}">WO #{{ c.work_order.pk }}</a>
    {% else %}<span class="badge-muted">unassigned</span>{% endif %}
  </td>
  <td class="whitespace-nowrap">
    {% if not c.work_order %}
    <form method="post" action="{% url 'workorder_open' c.equipment.pk %}" class="inline">
      {% csrf_token %}
      <button class="btn-warn btn-sm">Open WO</button>
    </form>
    {% endif %}
    <a href="{% url 'complaint_close' c.pk %}" class="btn-ghost btn-sm">Close…</a>
  </td>
</tr>
{% empty %}
<tr><td colspan="8" class="p-6 text-center text-slate-500 dark:text-slate-400">
  No open complaints. 🎉</td></tr>
{% endfor %}
```

- [ ] **Step 8: Rebuild CSS, run full suite**

Run: `bin/tailwindcss.exe -i static/css/input.css -o static/css/app.css --minify && uv run pytest -q`
Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add apps/maintenance/models.py apps/maintenance/views.py templates/maintenance/queue.html templates/maintenance/_queue_rows.html tests/test_ui.py static/css/app.css
git commit -m "feat: queue live search, state filter chips, and age-based urgency tint"
```

---

### Task 11: Work order detail

**Files:**
- Modify: `templates/maintenance/workorder_detail.html` (full rewrite)

- [ ] **Step 1: Rewrite `templates/maintenance/workorder_detail.html`**:

```html
{% extends "base.html" %}
{% block title %}WO #{{ wo.pk }}{% endblock %}
{% block page_title %}Work Order{% endblock %}
{% block content %}
<div class="mb-5 flex flex-wrap items-start justify-between gap-3">
  <div>
    <h1 class="text-2xl font-bold">Work Order #{{ wo.pk }}</h1>
    <p class="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
      <a class="link" href="{% url 'equipment_detail' wo.equipment.pk %}">{{ wo.equipment }}</a>
      · {{ wo.equipment.department }}</p>
  </div>
  {% if wo.status == 'completed' %}<span class="badge-working px-3 py-1 text-sm">{{ wo.get_status_display }}</span>
  {% elif wo.status == 'cancelled' %}<span class="badge-muted px-3 py-1 text-sm">{{ wo.get_status_display }}</span>
  {% elif wo.status == 'in_progress' %}<span class="badge-repair px-3 py-1 text-sm">{{ wo.get_status_display }}</span>
  {% else %}<span class="badge-info px-3 py-1 text-sm">{{ wo.get_status_display }}</span>{% endif %}
</div>
<div class="grid gap-6 md:grid-cols-2">
  <div class="card p-5 text-sm">
    <h2 class="mb-3 font-semibold">Timeline</h2>
    <dl class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5">
      <dt class="text-slate-500 dark:text-slate-400">Opened</dt><dd>{{ wo.opened_at }} by {{ wo.opened_by }}</dd>
      <dt class="text-slate-500 dark:text-slate-400">Repair started</dt><dd>{{ wo.repair_started_at|default:"—" }}</dd>
      <dt class="text-slate-500 dark:text-slate-400">Repair completed</dt><dd>{{ wo.repair_completed_at|default:"—" }}</dd>
      {% if wo.closed_by %}<dt class="text-slate-500 dark:text-slate-400">Closed by</dt><dd>{{ wo.closed_by }}</dd>{% endif %}
      {% if wo.outcome %}<dt class="text-slate-500 dark:text-slate-400">Outcome</dt><dd>{{ wo.get_outcome_display }}</dd>{% endif %}
      {% if wo.fault_category %}<dt class="text-slate-500 dark:text-slate-400">Fault</dt><dd>{{ wo.get_fault_category_display }}</dd>{% endif %}
      <dt class="text-slate-500 dark:text-slate-400">Participants</dt>
      <dd>{% for p in wo.participants.all %}{{ p }}{% if not forloop.last %}, {% endif %}{% empty %}—{% endfor %}</dd>
    </dl>
    {% if can_engineer and wo.is_active %}
    <div class="mt-4 flex flex-wrap gap-2 border-t border-slate-100 pt-4 dark:border-slate-800">
      {% if wo.status == 'open' %}
      <form method="post" action="{% url 'workorder_start' wo.pk %}">{% csrf_token %}
        <button class="btn-warn btn-sm">Start repair</button>
      </form>
      {% endif %}
      {% if wo.status == 'in_progress' %}
      <a href="{% url 'workorder_complete' wo.pk %}" class="btn-success btn-sm">Complete…</a>
      {% endif %}
      <form method="post" action="{% url 'workorder_join' wo.pk %}">{% csrf_token %}
        <button class="btn-primary btn-sm">I'm working on this</button>
      </form>
      <form method="post" action="{% url 'workorder_cancel' wo.pk %}">{% csrf_token %}
        <input type="hidden" name="note" value="No fault found.">
        <button class="btn-ghost btn-sm">Cancel (no fault)</button>
      </form>
    </div>
    {% endif %}
  </div>
  <div class="card p-5">
    <h2 class="mb-3 font-semibold">Attached Complaints ({{ wo.complaints.count }})</h2>
    <ul class="space-y-3 text-sm">
      {% for c in wo.complaints.all %}
      <li class="rounded-lg border border-slate-100 p-3 dark:border-slate-800">
        <p>#{{ c.pk }} — “{{ c.description|truncatechars:100 }}”</p>
        <p class="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{{ c.reporter }} · {{ c.created_at }} · {{ c.get_status_display }}</p>
        {% if c.is_awaiting_confirmation %}
        <p class="mt-1"><span class="badge-repair">Awaiting staff confirmation</span></p>
        {% elif c.functional_confirmation == 'functional' %}
        <p class="mt-1"><span class="badge-working">Staff confirmed: Functional ✓</span></p>
        {% elif c.functional_confirmation == 'not_functional' %}
        <p class="mt-1"><span class="badge-danger">Staff reported: NOT functional ✗</span></p>
        {% endif %}
      </li>
      {% empty %}<li class="text-slate-500 dark:text-slate-400">Engineer-initiated (no complaints).</li>
      {% endfor %}
    </ul>
  </div>
</div>
<div class="card mt-6 p-5">
  <h2 class="mb-3 font-semibold">Remarks</h2>
  <ul class="mb-4 space-y-2 text-sm">
    {% for remark in wo.remarks.all %}
    <li class="rounded-lg p-3
        {% if remark.kind == 'delay' %}border border-amber-200 bg-amber-50 dark:border-amber-500/30 dark:bg-amber-500/10
        {% elif remark.kind == 'system' %}bg-slate-50 text-slate-600 dark:bg-slate-800/60 dark:text-slate-300
        {% else %}bg-sky-50 dark:bg-sky-500/10{% endif %}">
      <span class="text-xs text-slate-500 dark:text-slate-400">{{ remark.created_at }} · {{ remark.author }}
        {% if remark.kind != 'note' %}· {{ remark.get_kind_display }}{% endif %}</span>
      <div class="mt-0.5">{{ remark.text }}</div>
    </li>
    {% empty %}<li class="text-slate-500 dark:text-slate-400">No remarks yet.</li>{% endfor %}
  </ul>
  {% if can_engineer %}
  <form method="post" action="{% url 'workorder_remark' wo.pk %}" class="space-y-2 border-t border-slate-100 pt-4 dark:border-slate-800">
    {% csrf_token %}
    {{ remark_form.text }}
    <div class="flex items-center gap-3">
      <div class="w-44">{{ remark_form.kind }}</div>
      <button class="btn-primary btn-sm">Add remark</button>
    </div>
  </form>
  {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 2: Rebuild CSS, run tests**

Run: `bin/tailwindcss.exe -i static/css/input.css -o static/css/app.css --minify && uv run pytest -q`
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add templates/maintenance/workorder_detail.html static/css/app.css
git commit -m "feat: restyle work order detail with badges and card layout"
```

---

### Task 12: Dashboard backend — new KPIs and trends (TDD)

**Files:**
- Modify: `apps/reports/metrics.py` (add `equipment_working_percent`)
- Modify: `apps/reports/views.py:12-44` (`dashboard`)
- Test: `tests/test_ui.py` (append)

**Interfaces:**
- Produces: `metrics.equipment_working_percent() -> int | None` (percent of non-condemned equipment currently Working; `None` when no equipment). Dashboard context gains: `working_percent` (int|None), `downtime_hours` (float), `repairs_delta` (int), `downtime_delta` (float) — deltas are current-30-days minus previous-30-days.

- [ ] **Step 1: Write failing tests** — append to `tests/test_ui.py`:

```python
def test_equipment_working_percent(make_equipment):
    from apps.reports import metrics

    make_equipment(serial_number="SN-W1", status="working")
    make_equipment(serial_number="SN-W2", status="working")
    make_equipment(serial_number="SN-R1", status="in_repair")
    make_equipment(serial_number="SN-C1", status="condemned")
    assert metrics.equipment_working_percent() == 67  # 2 of 3 non-condemned


def test_equipment_working_percent_empty(db):
    from apps.reports import metrics

    assert metrics.equipment_working_percent() is None


def test_dashboard_kpi_context(client, engineer):
    response_client = client
    response_client.force_login(engineer)
    response = response_client.get(reverse("dashboard"))
    assert response.status_code == 200
    for key in ("working_percent", "downtime_hours", "repairs_delta", "downtime_delta"):
        assert key in response.context
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ui.py -q`
Expected: 3 new failures (`equipment_working_percent` does not exist; context keys missing).

- [ ] **Step 3: Add metric** to `apps/reports/metrics.py`. Extend the equipment import at the top:

```python
from apps.equipment.models import Equipment, EquipmentStatus
```

Append at the end of the file:

```python
def equipment_working_percent():
    active = Equipment.objects.exclude(status=EquipmentStatus.CONDEMNED)
    total = active.count()
    if total == 0:
        return None
    working = active.filter(status=EquipmentStatus.WORKING).count()
    return round(100 * working / total)
```

- [ ] **Step 4: Extend the dashboard view** — in `apps/reports/views.py`, inside `dashboard`, after `faults = …` add:

```python
    prev_start = window_start - timedelta(days=30)
    repairs_completed = metrics.repairs_completed_count(window_start, window_end)
    repairs_prev = metrics.repairs_completed_count(prev_start, window_start)
    downtime_hours = round(sum(downtime.values()), 1)
    downtime_prev = round(
        sum(
            metrics.critical_downtime_by_department(prev_start, window_start).values()
        ),
        1,
    )
```

and change the context dict — replace the `"repairs_completed"` line and add the four new keys:

```python
    context = {
        "repairs_completed": repairs_completed,
        "repairs_delta": repairs_completed - repairs_prev,
        "open_workorders": metrics.open_workorders_count(),
        "working_percent": metrics.equipment_working_percent(),
        "downtime_hours": downtime_hours,
        "downtime_delta": round(downtime_hours - downtime_prev, 1),
        ...  # remaining keys exactly as they are today
    }
```

(“…” here means: keep every other existing key — `delayed`, `resolved`, `confirmations`, and the four `*_json` entries — unchanged. Do not literally write `...`.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest -q`
Expected: full suite passes.

- [ ] **Step 6: Commit**

```bash
git add apps/reports/metrics.py apps/reports/views.py tests/test_ui.py
git commit -m "feat: dashboard KPIs — equipment working percent, downtime hours, 30-day trends"
```

---

### Task 13: Dashboard template + engineer drill-down

**Files:**
- Modify: `templates/reports/dashboard.html` (full rewrite)
- Modify: `templates/reports/engineer_resolved.html` (full rewrite)

**Interfaces:**
- Consumes: context keys from Task 12; `hemdeskChart` + `countUp` from Task 2; `json_script` blocks keep their existing IDs (`downtime-data`, `complaints-data`, `devices-data`, `faults-data`) so `test_dashboard_renders_for_engineer` (asserts `chart.umd.js`) keeps passing.

- [ ] **Step 1: Rewrite `templates/reports/dashboard.html`**:

```html
{% extends "base.html" %}
{% load static %}
{% block title %}Dashboard{% endblock %}
{% block page_title %}Dashboard{% endblock %}
{% block content %}
<div class="mb-5 flex items-baseline justify-between">
  <h1 class="text-2xl font-bold">Dashboard</h1>
  <span class="text-sm text-slate-500 dark:text-slate-400">last 30 days</span>
</div>
<div class="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
  <div class="card p-5">
    <div class="flex items-baseline justify-between gap-2">
      <span class="text-3xl font-bold tabular-nums"
            x-data="countUp({{ repairs_completed }})" x-text="shown">{{ repairs_completed }}</span>
      <span class="{% if repairs_delta >= 0 %}badge-working{% else %}badge-danger{% endif %}">
        {% if repairs_delta >= 0 %}▲{% else %}▼{% endif %} {{ repairs_delta|stringformat:"+d" }}</span>
    </div>
    <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">Repairs completed</p>
  </div>
  <div class="card p-5">
    <div class="flex items-baseline justify-between gap-2">
      <span class="text-3xl font-bold tabular-nums"
            x-data="countUp({{ open_workorders }})" x-text="shown">{{ open_workorders }}</span>
    </div>
    <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">Work orders open right now</p>
  </div>
  <div class="card p-5">
    <div class="flex items-baseline justify-between gap-2">
      {% if working_percent is not None %}
      <span class="text-3xl font-bold tabular-nums"
            x-data="countUp({{ working_percent }}, '%')" x-text="shown">{{ working_percent }}%</span>
      {% else %}<span class="text-3xl font-bold">—</span>{% endif %}
    </div>
    <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">Equipment working</p>
  </div>
  <div class="card p-5">
    <div class="flex items-baseline justify-between gap-2">
      <span class="text-3xl font-bold tabular-nums"
            x-data="countUp({{ downtime_hours }}, 'h')" x-text="shown">{{ downtime_hours }}h</span>
      <span class="{% if downtime_delta > 0 %}badge-danger{% else %}badge-working{% endif %}">
        {% if downtime_delta > 0 %}▲{% else %}▼{% endif %} {{ downtime_delta }}</span>
    </div>
    <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">Critical downtime</p>
  </div>
</div>
<div class="grid gap-6 md:grid-cols-2">
  <div class="card p-5">
    <h2 class="mb-3 font-semibold">Critical-asset downtime <span class="text-sm font-normal text-slate-500 dark:text-slate-400">hours, by department</span></h2>
    <canvas id="chart-downtime"></canvas>
  </div>
  <div class="card p-5">
    <h2 class="mb-3 font-semibold">Complaints per department</h2>
    <canvas id="chart-complaints"></canvas>
  </div>
  <div class="card p-5">
    <h2 class="mb-3 font-semibold">Most-complained devices</h2>
    <canvas id="chart-devices"></canvas>
  </div>
  <div class="card p-5">
    <h2 class="mb-3 font-semibold">Fault categories <span class="text-sm font-normal text-slate-500 dark:text-slate-400">completed repairs</span></h2>
    <canvas id="chart-faults"></canvas>
  </div>
</div>
<div class="mt-6 grid gap-6 md:grid-cols-2">
  <div class="card p-5">
    <h2 class="mb-3 font-semibold">Repairs with delay remarks</h2>
    <ul class="space-y-2 text-sm">
      {% for d in delayed %}
      <li class="rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-500/30 dark:bg-amber-500/10">
        <a class="link" href="{% url 'workorder_detail' d.wo_id %}">WO #{{ d.wo_id }}</a>
        — {{ d.equipment }}
        <div class="mt-0.5 text-slate-600 dark:text-slate-300">“{{ d.latest_delay_note }}”</div>
      </li>
      {% empty %}<li class="text-slate-500 dark:text-slate-400">No delays recorded. 🎉</li>{% endfor %}
    </ul>
  </div>
  <div class="card p-5">
    <h2 class="font-semibold">Complaints resolved <span class="text-sm font-normal text-slate-500 dark:text-slate-400">· last 30 days · per engineer</span></h2>
    <p class="mb-3 mt-1 text-xs text-slate-500 dark:text-slate-400">
      Complaints an engineer helped resolve — by completing the repair (credits
      everyone who worked on it) or by closing a duplicate / false alarm. Click a
      number to see which equipment and the remarks.
    </p>
    <table class="w-full text-sm">
      <thead><tr class="border-b border-slate-200 text-left dark:border-slate-800">
        <th class="py-1.5 font-medium text-slate-500 dark:text-slate-400">Engineer</th>
        <th class="py-1.5 font-medium text-slate-500 dark:text-slate-400">Complaints resolved</th></tr></thead>
      <tbody>
        {% for e in resolved %}
        <tr class="border-b border-slate-100 dark:border-slate-800">
          <td class="py-1.5">{{ e.name }}
            <span class="text-slate-500 dark:text-slate-400">({{ e.employee_id }})</span></td>
          <td class="py-1.5"><a class="link tabular-nums"
            href="{% url 'engineer_resolved' e.user_id %}">{{ e.resolved_count }}</a></td></tr>
        {% empty %}<tr><td colspan="2" class="py-2 text-slate-500 dark:text-slate-400">
          No complaints resolved in this window.</td></tr>{% endfor %}
      </tbody>
    </table>
  </div>
  <div class="card p-5">
    <h2 class="mb-3 font-semibold">Recent staff confirmations <span class="text-sm font-normal text-slate-500 dark:text-slate-400">· last 30 days</span></h2>
    <ul class="space-y-2 text-sm">
      {% for c in confirmations %}
      <li class="rounded-lg p-3 {% if c.is_functional %}bg-emerald-50 dark:bg-emerald-500/10{% else %}border border-red-200 bg-red-50 dark:border-red-500/30 dark:bg-red-500/10{% endif %}">
        {% if c.work_order_id %}<a class="link"
          href="{% url 'workorder_detail' c.work_order_id %}">WO #{{ c.work_order_id }}</a>
        {% endif %} — {{ c.equipment }}:
        {% if c.is_functional %}<span class="text-emerald-800 dark:text-emerald-300">Functional ✓</span>
        {% else %}<span class="font-medium text-red-800 dark:text-red-300">NOT functional ✗</span>{% endif %}
        <span class="text-slate-500 dark:text-slate-400">· {{ c.confirmed_at|timesince }} ago</span>
      </li>
      {% empty %}<li class="text-slate-500 dark:text-slate-400">No confirmations yet.</li>{% endfor %}
    </ul>
  </div>
</div>
{{ downtime_json|json_script:"downtime-data" }}
{{ complaints_json|json_script:"complaints-data" }}
{{ devices_json|json_script:"devices-data" }}
{{ faults_json|json_script:"faults-data" }}
{% endblock %}
{% block extra_js %}
<script src="{% static 'js/chart.umd.js' %}"></script>
<script src="{% static 'js/charts.js' %}"></script>
<script>
  hemdeskChart('chart-downtime', 'downtime-data', 'bar');
  hemdeskChart('chart-complaints', 'complaints-data', 'bar');
  hemdeskChart('chart-devices', 'devices-data', 'bar-h');
  hemdeskChart('chart-faults', 'faults-data', 'doughnut');
</script>
{% endblock %}
```

- [ ] **Step 2: Rewrite `templates/reports/engineer_resolved.html`**:

```html
{% extends "base.html" %}
{% block title %}Complaints resolved — {{ engineer }}{% endblock %}
{% block page_title %}Dashboard{% endblock %}
{% block content %}
<div class="mb-5">
  <a href="{% url 'dashboard' %}" class="link text-sm">← Dashboard</a>
  <h1 class="mt-1 text-2xl font-bold">Complaints resolved by {{ engineer.get_full_name|default:engineer.username }}
    <span class="text-base font-normal text-slate-500 dark:text-slate-400">({{ engineer.employee_id }}) · {{ total }} · last 30 days</span></h1>
</div>
<div class="table-card">
  <table class="table">
    <thead><tr>
      <th>Equipment</th><th>Type</th><th>Resolved</th><th>Remarks</th></tr></thead>
    <tbody>
      {% for r in rows %}
      <tr class="row-hover">
        <td><a class="link" href="{% url 'equipment_detail' r.equipment_id %}">{{ r.equipment_name }}</a>
          <div class="text-xs text-slate-500 dark:text-slate-400">{{ r.equipment_model }} ·
            <span class="font-mono">{{ r.equipment_serial }}</span></div></td>
        <td>
          {% if r.resolution_type == 'Repaired' %}<span class="badge-working">{{ r.resolution_type }}</span>
          {% else %}<span class="badge-muted">{{ r.resolution_type }}</span>{% endif %}
        </td>
        <td class="whitespace-nowrap">{{ r.resolved_at|date:"Y-m-d H:i" }}</td>
        <td>
          {% for remark in r.remarks %}<div>“{{ remark }}”</div>{% empty %}
          <span class="text-slate-500 dark:text-slate-400">—</span>{% endfor %}</td>
      </tr>
      {% empty %}
      <tr><td colspan="4" class="p-6 text-center text-slate-500 dark:text-slate-400">
        Nothing resolved in this window.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

- [ ] **Step 3: Rebuild CSS, run tests**

Run: `bin/tailwindcss.exe -i static/css/input.css -o static/css/app.css --minify && uv run pytest -q`
Expected: full suite passes (dashboard tests included).

- [ ] **Step 4: Commit**

```bash
git add templates/reports/dashboard.html templates/reports/engineer_resolved.html static/css/app.css
git commit -m "feat: animated KPI dashboard with theme-aware charts"
```

---

### Task 14: End-to-end verification (browser walkthrough, both themes)

**Files:** none (verification only; fix regressions found, then amend-free follow-up commits).

- [ ] **Step 1: Full rebuild + full suite**

Run: `bin/tailwindcss.exe -i static/css/input.css -o static/css/app.css --minify && uv run pytest -q`
Expected: everything green.

- [ ] **Step 2: Launch the app** (dev server, port 8000):

Run: `uv run python manage.py runserver` (background). If demo data is needed, check `apps/*/management/commands/` for a seed command (e.g. `seed_demo`, covered by `tests/test_seed_demo.py`) and run it against the dev DB.

- [ ] **Step 3: Browser walkthrough** (use claude-in-chrome; light AND dark mode on each):
  1. Login page — split panel renders, form styled, bad password shows error box.
  2. Home — greeting, quick-action cards hover-lift; engineer sees 5 cards, staff 3.
  3. Equipment list — typing filters live with skeleton flash; chips filter; row click navigates; pagination if >25.
  4. Equipment detail — badges, timeline, actions.
  5. New complaint — picker searches, selection card appears, submit disabled until picked; success toast slides in on redirect.
  6. My complaints — badges, confirmation prompt row.
  7. Queue — live dot, search + chips filter, urgency tints, 10s refresh preserves filters (watch one refresh cycle).
  8. Work order — badges, actions, remarks; add a remark → toast.
  9. Dashboard — KPIs count up, trend badges, all four charts render; toggle dark mode → charts re-render with dark palette.
  10. Password change + done pages.
- [ ] **Step 4: Fix anything found, re-run suite, commit fixes** (one single-line commit per fix).

- [ ] **Step 5: Final commit if any stragglers, then report** — summarize changes; offer `superpowers:finishing-a-development-branch` (PR to main).

---

## Self-Review (done at write time)

- **Spec coverage:** design tokens/components (T1), dark mode (T1–T3), motion + reduced-motion (T1–T2), shell/sidebar/active-nav/toasts (T3), login (T4), home (T5), equipment live search + chips + skeleton (T6), detail timeline (T7), forms (T8–T9), queue filters/urgency/10s (T10), WO detail (T11), KPIs + trends, no-migration backend (T12), charts theme-aware + animated + engineer drill-down (T13), verification walkthrough (T14). Out-of-scope items respected. ✓
- **Placeholders:** the single `...` in Task 12's context dict is explicitly annotated with what to keep — acceptable as it references unchanged existing code, not new code. No TBDs. ✓
- **Type consistency:** `hemdeskChart(canvasId, scriptId, kind)` used identically in T2/T13; `countUp(target, suffix)` in T2/T13; `toasts`/`window.djangoMessages` in T2/T3; `_open_complaints_queryset(request)` matches both call sites in T10; `age_hours` property name consistent between model and template. `status_choices` produced in T6 Step 6 and consumed in T6 Step 5. ✓
