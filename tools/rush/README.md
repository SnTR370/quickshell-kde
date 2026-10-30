# Rush Supervisor

Bounded, repo-backed orchestrator for the quickshell-kde feature rush. Implements the
supervisor boundary required by `docs/development/RUSH_PROTOCOL.md` and
`docs/development/EVREN_GLM53_CCR_ADAPTER.md`: one fresh `claude -p` worker session per
backlog task, launched through the configured CCR profile, with hard gates and bounded
retries. Python 3 stdlib only; no dependencies.

## Invocation

```bash
# Plan only: evaluates all read-only gates, prints the exact worker invocation,
# spawns NOTHING. Always safe, works on an unsandboxed host.
python3 tools/rush/rush_supervisor.py --dry-run --task DOCK-004

# Real pilot (REFUSED unless an OS-level sandbox is detected):
python3 tools/rush/rush_supervisor.py --task DOCK-004 --base <expected-base-sha>
```

Useful flags: `--repo` (default: repo containing this file), `--backlog`
(default `docs/roadmap/DOCK_BACKLOG.json`), `--max-tasks` (default 3, hard pilot cap),
`--ccr-bin` / `--ccr-profile` (defaults: the `EVREN - QS KDE` CCR profile),
`--orchestrator-branch`, `--worker-timeout` (seconds, default 3600).

Exit codes: `0` success/dry-run, `2` supervisor stop (a gate failed — read stderr).

## What it does per task

1. **Base gates** (before anything side-effectful): working tree clean (`.rush-inbox/`
   untracked is allowed), current branch is the orchestrator branch, HEAD descends from
   the expected base. Acquires an O_EXCL worktree lock so two agents never edit this
   worktree concurrently (stale locks from dead PIDs are reclaimed).
2. **Sandbox gate**: probes for real OS-level isolation (out-of-repo home write must
   fail AND external network must fail). Without isolation, real runs are refused
   outright — a git worktree or prompt text is not isolation. Dry-runs always allowed.
3. Creates feature branch `feat/rush-<id>` from the base, then spawns ONE fresh worker:
   `ccr "EVREN - QS KDE" cli -- claude -p --output-format json --permission-mode
   acceptEdits <scoped prompt>` — as a subprocess **argument array** (no shell), never
   `--model`, never `--dangerously-skip-permissions`.
4. Parses the worker's structured `rush-report` JSON block and enforces: report
   completeness, correct feature/base/branch, non-empty test evidence, no failing tests
   on a `done` claim, commit exists on the feature branch and descends from the base.
5. **Provider route gate**: reads the local CCR usage DB (read-only, no credentials) and
   requires that requests during the worker run routed to EVREN GLM-5.3 with HTTP 200.
6. **Independent test evidence**: re-runs `python3 -m unittest discover -s tests` itself.
   Only failures documented as environmental in the backlog's baseline record
   (the live-session Spotify enumeration test) are tolerated.
7. On `done`: merges the feature branch into the orchestrator branch (`--no-ff`, never
   `main`), pushes both, updates `DOCK_BACKLOG.json` with status + evidence, writes a
   scrubbed run log to `tools/rush/runs/`.
8. Advances to the next `ready`/`candidate` task, up to `--max-tasks` (default 3).

## Stop conditions (never bypassed)

Dirty base, unexpected branch, missing sandbox (real runs), unverifiable or changed
provider route, malformed/missing worker report, claimed commit not on the feature
branch, failed independent tests, worker hard failure. Transient provider failures
(gateway 5xx/429/timeouts, malformed model output) get exactly ONE bounded retry — and
only if the failed attempt left no side effects (no dirty tree, no new commits). Every
stop leaves the feature branch and a run log as a checkpoint.

## Logs and secrets

Run logs (`tools/rush/runs/<timestamp>-<id>.json`) record task, base SHA, branch,
provider route, attempts, tests and outcome. All text passes through a best-effort
credential scrubber (API keys, bearer tokens, JWTs) before being written. Commit run
logs alongside the backlog updates — they are the durable evidence trail.

## Tests

```bash
python3 -m unittest discover -s tools/rush/tests   # 39 tests, all mocked/local
```

Covers: worker argv contract, all gates (positive and negative), process lifecycle,
bounded retry semantics, side-effect-aware retry refusal, dry-run never spawning,
worktree locking, provider-route fixture DB, secret scrubbing, backlog updates.
