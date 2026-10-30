# Dock Feature Rush — source of truth and status conventions

> Initial planning snapshot: 2026-10-30. Historical reference: Dock Feature Atlas, authored 2026-10-26 15:16 Türkiye time. **Historical status columns are NOT current state.**

## Scope

This is a professional KDE Plasma 6 / KWin Wayland Bar+Dock product: **Your desktop, your layout.** Feature-first until beta, without skipping all tests. Quickshell owns presentation/configuration; KDE/KWin/Qt native public APIs and services own system-level behavior whenever supported. No fake capability or duplicate system daemons.

## Files and precedence

1. Actual code, `git` commit ancestry and tests: truth for implementation state.
2. `docs/roadmap/DOCK_BACKLOG.json`: prioritized working queue; update evidence after each task.
3. `docs/development/RUSH_PROTOCOL.md`: execution and safe stopping rules.
4. `docs/reference/DOCK_FEATURE_ATLAS_2026-10-26.txt`: historical full feature inventory and original reasoning, **not** an execution plan or a current status report.
5. UX/Architecture/KWin design docs: constraints and interfaces.

## Backlog

The ranked historical top 12 are in `DOCK_BACKLOG.json`. **Every item was reconciled against the repo on 2026-10-30** (see the `audit_2026_10_30` block there): DOCK-001/002/005/006/007 implemented, DOCK-003 beta_candidate, DOCK-008 partial, DOCK-004/009/010/011/012 confirmed missing. Do not reimplement what exists. Layout Presets is **completed** as a separate non-Atlas feature: `feat/beta-layout-presets` at `a47e333`. Its GUI interaction on live hardware remains unverified; do not reimplement it.

Next candidate: **DOCK-004 parabolic zoom** (status `ready`), then DOCK-008 Meta+1..9 completion and the remaining `candidate` items by value/dependencies. Starting a task requires an assigned rush session and a clean base; see `docs/development/RUSH_PROTOCOL.md` and the supervisor boundary in `docs/development/EVREN_GLM53_CCR_ADAPTER.md`.

## Completion evidence

For each task log the feature ID, base SHA, branch, changed files, tests (pass/fail/skip), runtime proof, known limitations, final commit and push URL. `done` must never mean that hardware/session verification was done when it wasn't. `beta_candidate` explicitly retains a manual hardware test debt.

## Release policy

Do not merge automatically into `main`; don't deploy to user's active session. A clean isolated test run is necessary for progression, and a separate integration/release gate checks the full branch. Publishable beta requires manual acceptance of hardware/Wayland risks.
