# EVREN GLM-5.3 through Claude Code Router — runner adapter

## Identity and compatibility

- **Client / agent tools:** Native Claude Code CLI (last user-confirmed v2.1.308). This is a client, **not the foundation model**.
- **Router:** `@musistudio/claude-code-router` (CCR; last confirmed v3.1.3), locally installed under `~/.local/share/evren-cli/node_modules/.bin/ccr`.
- **CCR profile:** `EVREN - QS KDE`.
- **Intended actual provider/model:** EVREN **GLM-5.3**. Verify with real CCR request logs, especially after restart, upgrade or fallback.
- **Known gateway:** `http://127.0.0.1:3456`; management UI may start at `http://127.0.0.1:3458`. Port and authentication can vary. **Never commit management tokens, API keys, live profile/config databases or credential-bearing URLs.**
- These are last known project environment details, not claims that the current machine or profile was probed by this package.

## Interactive launch (fish)

```fish
set -l ccr "$HOME/.local/share/evren-cli/node_modules/.bin/ccr"
$ccr start
$ccr ui
cd ~/Projects/quickshell-kde-layout-presets
$ccr "EVREN - QS KDE" cli -- --permission-mode acceptEdits
```

Use the appropriate task worktree instead of the example path. `ccr ui` can open authenticated management UI; don't paste its URL into committed logs. Verify that a real request routes to **EVREN / GLM-5.3** in CCR. Do not pass `--model opus`, `--model sonnet` or other Anthropic aliases simply because the client is named Claude Code.

## Non-interactive invocation contract (first verify manually)

CCR forwards arguments following `--` to the client. Claude Code supports print mode (`-p`) and `--output-format json`. Illustrative **read-only preflight probe**:

```fish
set -l ccr "$HOME/.local/share/evren-cli/node_modules/.bin/ccr"
$ccr start
$ccr "EVREN - QS KDE" cli -- -p --output-format json --permission-mode plan "Read CLAUDE.md and report the current Git branch and HEAD without editing any file."
```

This is a documented syntax example, **not a proven successful run against Sena's current CCR/GLM setup**. Validate the actual argv forwarding, exit status, JSON output, provider route, Quickshell tools and permissions in the target environment before writing an orchestrator. A successful response must not be inferred from exit code alone.

An unattended feature runner requires a proper **OS-level sandbox** and a controlled, scoped repository workspace before any permission bypass. A Git worktree and instructions in this file do not isolate `$HOME`, the active Plasma session or credentials. The sandbox must reach the explicitly authorized CCR gateway without exposing the host broadly; `127.0.0.1` on the host might not be reachable from a container network namespace. No self-recursive uncontrolled command loops. Do not configure privileged installs or automatically merge to `main`.

## GLM-5.3-specific operating discipline

1. **Context:** one assigned feature per fresh CLI session; checkpoint design, exact changed paths, tests and blockers before ~70–80% context utilization if visible. Do not guess the provider's context window. No token budgets are imposed by this document, but avoid repeated exhaustive scans without new evidence.
2. **Permission classifier:** the current CCR + EVREN route has previously exhibited Claude Code `auto` classifier timeouts. Prefer `acceptEdits` for supervised host sessions. In a hardened isolated environment only, consider bypass after an explicit security review. Never retry the same denied/destructive operation blindly.
3. **Provider/model routing:** record whether CCR actually used EVREN GLM-5.3. If route changes, stop and report rather than silently continuing under a different LLM. Subagents, if used, must not be assumed to share the same route automatically.
4. **Tool-call reliability:** preserve full, local failure diagnostics without secrets. For malformed tool results or transient 429/5xx, retry at most a bounded number of times (for example 2), then checkpoint and stop; avoid duplicate side-effecting writes, commits or pushes on retry.
5. **Evaluation:** only source diff + focused tests + regression + isolated runtime evidence establishes DONE. If a plugin, binary or native KWin API lacks portability/runtime proof, mark it partial or blocked.
6. **Quota:** the previously reported daily quota and free-use window are *historical*, not guaranteed at runtime. Treat exhausted quota or gateway outage as an ordinary checkpoint/STOP condition, not a reason to switch providers without explicit authorization.
7. **State:** keep durable feature ID, expected Git ancestry, latest commit, test results, route validation and next-task recommendation in the repository. Do not rely on agent chat memory across sessions.

## Supervisor boundary

Do not claim an autonomous runner exists just because these documents are present. Before a 3-feature pilot, implement and demonstrate a supervisor that starts an isolated fresh session for each feature, validates JSON/report structure, records the provider, verifies Git HEAD and test evidence, and only proceeds when hard gates pass. Each pass must close the old process cleanly. All subprocess and gateway failures must have a maximum bounded retry count. The runner must be explicitly started by the project owner.

## References

- CCR official CLI: `https://github.com/musistudio/claude-code-router/blob/main/docs/src/content/docs/en/guides/cli.md`
- Claude Code CLI reference: `https://code.claude.com/docs/en/cli-reference`
- Claude Code permissions: `https://code.claude.com/docs/en/permissions`
