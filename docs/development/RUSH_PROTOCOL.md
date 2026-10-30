# Agent Feature Rush Protocol

## Goal

Maximize independently verified features without corrupting the repo, user session or data. Not an infinite monologue. Use **one feature per agent session**, with optional external supervisor launching the next fresh session after validation. A single markdown instruction file cannot relaunch a terminated process.

## Preflight (read-only first)

1. `pwd`, `git status --short --branch`, `git log -1`, worktree check, current test baseline. Verify correct base and that another active agent is not editing this tree.
2. Read `CLAUDE.md`, `DOCK_FEATURE_RUSH.md`, `DOCK_BACKLOG.json`, architecture and feature-specific source. Historical atlas is reference only.
3. Inspect code/tests for each selected item. If already present, update evidence instead of duplicating it.
4. Never infer an unverified local branch's state from GitHub alone.

## Feature transaction

1. Pick a single unblocked task; record `in_progress`, base SHA and target branch in the working backlog.
2. Implement only that item; prefer KDE/Qt-native mechanisms. Do not touch another agent's worktree. No broad refactors.
3. Write focused tests and run relevant suites, qmllint, applicable isolated Wayland smoke/E2E checks.
4. If tests are red: repair relevant defect or mark `blocked`, preserve WIP and **STOP** progression. Never normalize broken baseline as success.
5. Inspect security, install scripts, dependency additions, new background processes, and git diff; prevent secrets and generated binaries from leaking.
6. Commit + push only the feature branch. Update backlog with exact SHA, test outcomes, limitations and evidence, in the same feature branch or a clearly linked follow-up commit. Never announce success before commit verification.
7. Supervisor may advance to next feature only after all hard gates passed and branch lineage is known. Never auto-merge or force-push `main`.

## Stop conditions (mandatory)

Stop and produce an exact BLOCKED/WIP checkpoint when any of these occur: failing relevant tests not repaired, unclear feature scope, unknown native API/Wayland support, data-loss or user-session risk, destructive git request, new dependencies needing security review, another agent concurrently editing the same worktree, unresolved merge conflicts, resource/quota failure, unexpectedly unclean base, or missing build/repro instructions.

## GLM-5.3 / CCR invocation requirements

This setup uses Claude Code as a **client/tool harness**, CCR as the profile/router and **EVREN GLM-5.3 as the actual inference model**. Read `EVREN_GLM53_CCR_ADAPTER.md` for launch, route verification, failure categories and compatibility requirements. Do not silently switch to Anthropic models. Before any unattended run, verify the configured CCR profile and inspect at least one real provider/model request log; record the route in the task report. The runner must treat missing gateway, timeouts, quotas, malformed output and unexplained model fallback as STOP or bounded retry conditions. No infinite retry/recovery loops.

## Context management

Use fresh sessions for new features. Keep the authoritative state in the repo, not in chat memory. Checkpoint at an early safe milestone (ideally before the session reaches roughly 70–80% of its context, when that metric is visible); do not wait for 90% exhaustion. The number is an operational heuristic, not a fixed GLM-5.3 context capacity or token cap. Prefer an external orchestrator with bounded attempts, JSON result checks and stop-on-red gates; do NOT use unrestricted self-recursive commands on user's normal desktop.

## Host safety

No sudo, destructive Git, changes to `~/.config/quickshell/sena`, user Plasma files, active Wayland session, other users' homes, or unrelated projects. Code instructions are **not** OS security enforcement. `--dangerously-skip-permissions` requires real isolation (separate VM/container plus filesystem/network limits), not merely a Git worktree. Without isolation use acceptEdits with narrow command permissions.

## Final report format

STATUS: DONE / PARTIAL / BLOCKED
FEATURE ID:
BASE / BRANCH:
IMPLEMENTATION:
TESTS: pass / fail / skip with commands
ISOLATED RUNTIME:
LIVE HARDWARE STATUS:
KNOWN LIMITATIONS:
COMMIT SHA / PUSH URL:
NEXT CANDIDATE:

The report's `NEXT CANDIDATE` is informational: moving to the next feature is the supervisor's decision after validation.
