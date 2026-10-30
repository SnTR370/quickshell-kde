# QuickShell KDE — agent working rules

**RUNTIME IDENTITY:** The agent runs inside the Claude Code CLIENT, routed through CCR (profile `EVREN - QS KDE`) to **EVREN GLM-5.3**. Do not describe the underlying model as Anthropic Claude. Verify the real provider/model route with CCR request logs (`~/.claude-code-router/app-data/usage.sqlite`, `usage_events` table); a client banner or model alias alone is not evidence. Read `docs/development/EVREN_GLM53_CCR_ADAPTER.md` before building or running any orchestrator.

Product: professional KDE Plasma 6 / KWin Wayland shell. Motto: **Your desktop, your layout.** Quickshell = UI/composition/config. KDE/Qt/native public API = platform behavior. Never fake unsupported compositor capabilities or duplicate KDE services/daemons.

**MANDATORY START:** read `docs/roadmap/DOCK_FEATURE_RUSH.md`, `docs/roadmap/DOCK_BACKLOG.json`, `docs/development/RUSH_PROTOCOL.md`, and feature-specific architecture/tests. Inspect Git status first. The 2026-10-26 Atlas (`docs/reference/DOCK_FEATURE_ATLAS_2026-10-26.txt`) is HISTORICAL research: its ✓/— flags are NOT current code status. The backlog's `audit_2026_10_30` block is the latest reconciliation.

**GLM-5.3 EXECUTION:** Keep one scoped feature per fresh context; persist discoveries and decisions in Git files before context is saturated. Use tightly scoped subagents only when they demonstrably help. Treat `auto` permission-classifier timeouts, gateway outages, invalid JSON/tool-call output and rate limits as bounded, reportable failures, never reasons for unbounded retries. Use the actual CCR profile; do not force `--model sonnet` or `opus`.

**ONE FEATURE PER SESSION:** inspect existing implementation, select the highest valuable unblocked task only if the user/orchestrator assigned a rush task, implement, test, commit, push feature branch, checkpoint, STOP. Do not treat this file as blanket authorization to start tasks autonomously outside an assigned coding session.

**QUALITY GATES:** focused tests + relevant regressions + qmllint + isolated Wayland runtime where needed; never invent results. No automatic merge to `main`. Record exact commit and verification evidence. Failing gates stop progression.

**SAFETY:** Do not touch running Plasma, `~/.config/quickshell/sena`, unrelated Git worktrees, user data; no sudo/force push/destructive git/install without source & script review. Instructions do not enforce OS isolation; if no sandbox, do not use `--dangerously-skip-permissions` for unattended work.
