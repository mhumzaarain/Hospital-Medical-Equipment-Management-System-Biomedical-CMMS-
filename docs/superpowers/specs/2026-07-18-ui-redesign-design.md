# UI Redesign — "Clinical Sky" Design System

**Date:** 2026-07-18
**Goal:** Make the HEMDESK UI interactive and polished to a professional-product standard (Linear/Notion tier) across the whole app, using the existing stack only: Django templates, Tailwind v4 (standalone CLI at `bin/tailwindcss.exe`), htmx, Alpine.js, Chart.js — no new runtime dependencies, no Node.

**Direction (user-approved):** Polished professional product · whole-app scope · "Clinical Sky" theme (evolution of current navy/sky brand) · dashboard layout A (KPI strip + 2×2 chart grid) · live search/filters, animated dashboard, toasts + micro-interactions, dark mode.

## 1. Design system (`static/css/input.css`)

Tailwind v4 `@theme` tokens:

- **Brand palette:** navy→sky ramp as `--color-brand-*` (sidebar `sky-950/900`, accents `sky-500/400`).
- **Semantic status colors:** working = emerald, in-repair = amber, condemned = red; used consistently by badges, charts, and confirmation cards.
- **Surfaces:** light = slate-100 canvas / white cards / slate-200 1px borders; dark = slate-950 canvas / slate-900 cards / slate-800 borders.
- **Type:** system UI stack (Inter-like); tabular-nums for KPI figures.
- **Radii:** cards 12px, controls 8px. One shadow scale (subtle; elevation on hover).

`@layer components` classes used by all templates:

- `.card` — surface, border, radius, shadow, hover elevation where interactive.
- `.btn`, `.btn-primary`, `.btn-danger`, `.btn-ghost` — press feedback (active scale), focus rings.
- `.badge` + status variants — pill with colored dot.
- `.field` — styles inputs/selects/textareas globally (fixes unstyled Django widgets).
- `.table` — styled sticky thead, row hover, comfortable density.
- `.skeleton` — shimmer placeholder for htmx loading states.

**Dark mode:** `@custom-variant dark` keyed off `.dark` on `<html>`. Toggle in sidebar footer (sun/moon), persisted in `localStorage`, applied by an inline `<head>` script before paint (no flash). Every token has a dark value.

**Motion:** 150–200ms transitions on interactive elements; subtle content fade/slide-in on page load; `prefers-reduced-motion: reduce` disables non-essential animation (including chart entry and count-ups).

## 2. Shell (`templates/base.html`)

- Sidebar: navy gradient surface; nav items with inline-SVG Lucide-style icons; **active-page highlighting** driven by `request.path`/url-name comparison; grouped sections — Operations (Equipment, New Complaint, My Complaints), Insights (Queue, Dashboard — engineer/admin), Admin (staff); user card at bottom with avatar initials; dark-mode toggle.
- Header: slim top bar — page title slot (block) left, hospital name right.
- **Toasts:** replace `partials/_messages.html` banner with Alpine toast stack — top-right, slide-in, auto-dismiss with progress bar, color-coded by Django message level, dismiss button.

## 3. Pages

- **Login** (`registration/login.html`): split screen — left brand panel (navy gradient, logo, tagline, subtle decorative pattern; hidden on small screens), right form card with floating labels and inline error states.
- **Home** (`home.html`): time-of-day greeting with user's name; 3–4 quick-action cards (Report a fault, Browse equipment, My complaints; Queue/Dashboard for engineers) with hover lift and icons.
- **Equipment list**: live search — htmx on `keyup changed delay:300ms` + filter as status chips (replaces dropdown+button); skeleton rows during swap; status badge pills; amber ★ for critical; whole row clickable.
- **Equipment detail**: header block with large status badge; details as definition grid in cards; status history as vertical timeline (dots + line); work orders as cards with outcome badges.
- **Queue**: keeps 10s htmx auto-refresh; adds text search + state filter chips; age-based urgency tint on waiting complaints; state badges; smooth htmx settle transitions.
- **Forms** (complaint new/close, equipment form/condemn, workorder complete, password change): shared `.field` styling, clear label/help/error hierarchy; sticky action bar on long forms.
- **Dashboard** (layout A): 4 KPI tiles — Repairs completed, Open work orders, **% equipment working (new)**, **Critical downtime hours (new)** — with count-up animation and trend arrow vs. previous 30-day window where computable; 2×2 chart grid; delayed-repairs, engineer leaderboard, confirmations cards restyled (confirmations use semantic status colors).
- **My complaints / engineer resolved / password done:** restyled with the same components (cards, badges, tables).

## 4. Interactivity plumbing

- htmx: equipment live search endpoint (reuse `_search_results.html` partial pattern), queue refresh (existing), skeleton indicators via `htmx-indicator`.
- Alpine: toasts, dark-mode store, KPI count-up, any dropdowns.
- Backend changes are minimal: two new KPI aggregates + trend values in the dashboard view, htmx partial response for equipment list search/filter, active-nav context (template-side or context processor). **No model or migration changes.**

## 5. Charts

One `static/js/charts.js` helper wrapping Chart.js: theme-aware palette read from CSS custom properties; re-render on dark-mode toggle (custom event); rounded bars, soft gridlines, styled tooltips; 800ms ease-out entry animation (disabled under reduced motion). Dashboard page passes data via existing `json_script` blocks.

## 6. Verification

- `pytest` suite stays green throughout; template-dependent tests updated only where markup assertions break.
- CSS rebuilt with `bin/tailwindcss.exe -i static/css/input.css -o static/css/app.css --minify`.
- Browser walkthrough of every page (login → home → equipment list/detail/form → complaint flow → queue → work order → dashboard → password pages) in light **and** dark mode, checking live search, toasts, chart theming, and responsive behavior at narrow widths.

## Out of scope

- No SPA/framework rebuild, no component library, no new runtime dependencies.
- No data-model changes; no new report types beyond the two KPI aggregates.
- No offline/PWA, no real-time WebSocket features (queue polling stays htmx).
