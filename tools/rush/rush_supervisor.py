#!/usr/bin/env python3
"""Rush supervisor — bounded, repo-backed orchestrator for one-feature-per-session rush tasks.

Design contract (see docs/development/RUSH_PROTOCOL.md and
docs/development/EVREN_GLM53_CCR_ADAPTER.md):

- One fresh ``ccr "<profile>" cli -- claude -p`` subprocess per task, invoked with an
  argument ARRAY (no shell), ``--output-format json`` and ``--permission-mode acceptEdits``.
  It never passes ``--model`` and never uses ``--dangerously-skip-permissions``.
- Hard gates before/after each task: clean base, expected branch, sandbox probe (real runs
  are refused outright when no OS-level isolation is detected), provider-route verification
  against the local CCR usage database, worker report structure, commit/branch lineage and
  independently re-run test evidence.
- Bounded retries: exactly ONE retry, only for transient provider failures, and only when
  no side effects (commits/dirty tree) appeared. Everything else stops the run.
- All logs are scrubbed of obvious credential material before being written to disk.

This file is intentionally stdlib-only (Python >= 3.10).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

REPO_DEFAULT = Path(__file__).resolve().parents[2]
BACKLOG_DEFAULT = "docs/roadmap/DOCK_BACKLOG.json"
RUNS_DIR = "tools/rush/runs"
LOCK_FILE = ".rush-supervisor-lock.json"
KNOWN_TRANSIENT_PATTERNS = (
    "timeout", "timed out", "econnrefused", "connection refused", "connection reset",
    "429", "rate limit", "502", "503", "504", "bad gateway", "service unavailable",
    "overloaded", "internal server error",
)
EXPECTED_PROVIDER = "EVREN"
EXPECTED_MODEL_PREFIX = "glm-5.3"
MAX_TASKS = 3
TRANSIENT_RETRIES = 1

_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{8,}"),
    re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
    re.compile(r"(?i)(api[_\-]?key|token|password|secret)[\"'\s:=]+([^\s\"',;}]{8,})"),
]


def scrub(text: str) -> str:
    """Best-effort credential scrubbing for anything that ends up in logs."""
    for pat in _SECRET_PATTERNS:
        if pat.groups:
            text = pat.sub(lambda m: f"{m.group(1)}=<redacted>", text)
        else:
            text = pat.sub("<redacted>", text)
    return text


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class TaskOutcome:
    feature_id: str
    status: str  # done | partial | blocked | retry | supervisor_stop
    detail: str
    base_sha: Optional[str] = None
    branch: Optional[str] = None
    commit: Optional[str] = None
    files_changed: list = field(default_factory=list)
    tests: list = field(default_factory=list)
    provider_route: Optional[dict] = None
    attempts: int = 0
    error_kind: Optional[str] = None


class GateFailure(Exception):
    """A hard gate failed; the supervisor must stop (never bypass, never retry blindly)."""


class WorktreeLock:
    """O_EXCL lockfile preventing two agents editing the same worktree concurrently."""

    def __init__(self, repo: Path, stale_seconds: int = 6 * 3600):
        self.path = repo / LOCK_FILE
        self.stale_seconds = stale_seconds

    def acquire(self) -> None:
        if self.path.exists():
            try:
                info = json.loads(self.path.read_text())
                age = time.time() - info.get("started_epoch", 0)
                if age < self.stale_seconds and self._pid_alive(info.get("pid")):
                    raise GateFailure(
                        f"another supervisor (pid {info.get('pid')}) holds the worktree lock"
                    )
            except (json.JSONDecodeError, OSError):
                pass  # corrupt/stale lock -> reclaim
            self.path.unlink(missing_ok=True)
        payload = {"pid": os.getpid(), "started": utcnow(), "started_epoch": time.time()}
        fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        with os.fdopen(fd, "w") as fh:
            json.dump(payload, fh)

    def release(self) -> None:
        self.path.unlink(missing_ok=True)

    @staticmethod
    def _pid_alive(pid) -> bool:
        try:
            os.kill(int(pid), 0)
            return True
        except (OSError, ValueError, TypeError):
            return False


class GitRepo:
    """Thin, shell-free git wrapper. All output is text; callers scrub before logging."""

    def __init__(self, repo: Path):
        self.repo = repo

    def _git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-C", str(self.repo), *args],
            capture_output=True, text=True, timeout=120,
        ) if not check else subprocess.run(
            ["git", "-C", str(self.repo), *args],
            capture_output=True, text=True, timeout=120, check=True,
        )

    def current_branch(self) -> str:
        return self._git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()

    def head(self) -> str:
        return self._git("rev-parse", "HEAD").stdout.strip()

    def status_porcelain(self) -> str:
        return self._git("status", "--porcelain").stdout

    def is_ancestor(self, sha: str, ref: str) -> bool:
        proc = self._git("merge-base", "--is-ancestor", sha, ref, check=False)
        return proc.returncode == 0

    def commit_exists_on(self, sha: str, branch: str) -> bool:
        proc = self._git("merge-base", "--is-ancestor", sha, branch, check=False)
        return proc.returncode == 0

    def create_branch(self, name: str, start: str) -> None:
        self._git("checkout", "-b", name, start)

    def checkout(self, ref: str) -> None:
        self._git("checkout", ref)

    def merge_no_ff(self, branch: str, message: str) -> None:
        self._git("merge", "--no-ff", "-m", message, branch)

    def push(self, *refs: str) -> None:
        self._git("push", "origin", *refs)

    def commits_between(self, base: str, head: str) -> list:
        out = self._git("log", "--format=%H", f"{base}..{head}").stdout.split()
        return out


def default_sandbox_probe(repo: Path) -> dict:
    """Detect OS-level isolation. A git worktree or prompt text is NOT isolation.

    Isolation is only assumed when BOTH an out-of-repo home write fails AND an
    external network connection fails. Seccomp state is recorded as supporting
    evidence only (bubblewrap/namespaces need not set the same seccomp flags).
    """
    result = {"probed_at": utcnow()}
    probe_file = Path.home() / ".rush-sandbox-probe"
    try:
        probe_file.write_text("probe")
        probe_file.unlink(missing_ok=True)
        result["home_write"] = "allowed"
    except OSError:
        result["home_write"] = "blocked"
    try:
        with socket.create_connection(("example.com", 443), timeout=4):
            result["external_network"] = "allowed"
    except OSError:
        result["external_network"] = "blocked"
    try:
        status = Path("/proc/self/status").read_text()
        m = re.search(r"^Seccomp:\s+(\d+)", status, re.M)
        result["seccomp"] = m.group(1) if m else "unknown"
    except OSError:
        result["seccomp"] = "unknown"
    result["isolated"] = result["home_write"] == "blocked" and result["external_network"] == "blocked"
    return result


def default_provider_route(ccr_usage_db: Path, since_iso: str) -> Optional[dict]:
    """Verify from the local CCR usage DB that requests since `since_iso` routed to
    EVREN GLM-5.3. Read-only; never reads credentials."""
    if not ccr_usage_db.exists():
        return None
    try:
        con = sqlite3.connect(f"file:{ccr_usage_db}?mode=ro", uri=True, timeout=5)
        try:
            rows = con.execute(
                "SELECT provider, model, status_code, COUNT(*) FROM usage_events "
                "WHERE created_at >= ? GROUP BY provider, model, status_code",
                (since_iso,),
            ).fetchall()
        finally:
            con.close()
    except sqlite3.Error:
        return None
    if not rows:
        return None
    route = {
        "providers": sorted({r[0] for r in rows}),
        "models": sorted({r[1] for r in rows}),
        "status_codes": sorted({r[2] for r in rows}),
        "events": sum(r[3] for r in rows),
    }
    route["ok"] = (
        route["providers"] == [EXPECTED_PROVIDER]
        and all(m.startswith(EXPECTED_MODEL_PREFIX) or f"/{EXPECTED_MODEL_PREFIX}" in m for m in route["models"])
        and all(s == 200 for s in route["status_codes"])
    )
    return route


def default_run_worker(argv: list, timeout_s: int) -> tuple:
    """Execute the worker. Returns (exit_code, stdout, stderr). Never a shell string."""
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout_s)
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        return 124, exc.stdout or "", "supervisor timeout"
    except OSError as exc:
        return 125, "", str(exc)


WORKER_PROMPT_TEMPLATE = """You are a rush worker session for quickshell-kde (KDE Plasma 6 / KWin Wayland shell).

First read, in this order: CLAUDE.md, docs/roadmap/DOCK_BACKLOG.json (item "{feature_id}"),
docs/development/RUSH_PROTOCOL.md, and the feature-specific source/tests.

Your ONLY assignment: implement feature {feature_id}: {title}.

Rules:
- Work on the currently checked-out branch only: {branch}. Never merge into main, never
  force-push, never touch other worktrees, the active Plasma session, or
  ~/.config/quickshell/sena. No sudo, no new dependencies without review.
- Inspect the existing implementation first; do not reimplement what exists.
- Implement the feature with focused tests. Run the focused tests AND
  `python3 -m unittest discover -s tests` and `qmllint` on changed QML files.
  The live-session test test_12_live_kwin_running_apps_enumeration may fail for
  environmental reasons; if it is the ONLY failure, note that explicitly.
- Commit your work on the current branch with a descriptive message.
- Do NOT push; the supervisor verifies and pushes.

End your reply with EXACTLY one fenced block of the form:

```rush-report
{{"feature_id": "{feature_id}", "status": "done|partial|blocked", "base_sha": "<sha you started from>", "branch": "{branch}", "commit": "<your commit sha or null>", "files_changed": ["..."], "tests": [{{"name": "...", "result": "pass|fail|skip", "command": "..."}}], "notes": "..."}}
```
"""


REPORT_RE = re.compile(r"```rush-report\s*\n(.*?)\n\s*```", re.S)


def parse_worker_report(raw_output: str) -> Optional[dict]:
    """Extract the structured rush-report block from worker output."""
    matches = REPORT_RE.findall(raw_output)
    if not matches:
        return None
    try:
        report = json.loads(matches[-1])
    except json.JSONDecodeError:
        return None
    if not isinstance(report, dict):
        return None
    return report


def parse_claude_json(stdout: str) -> tuple:
    """Handle `claude -p --output-format json` envelope; fall back to raw text."""
    try:
        envelope = json.loads(stdout)
        if isinstance(envelope, dict) and "result" in envelope:
            return envelope["result"], envelope
        return stdout, envelope
    except json.JSONDecodeError:
        return stdout, None


class RushSupervisor:
    def __init__(
        self,
        repo: Path,
        backlog_path: Path,
        ccr_bin: str,
        ccr_profile: str,
        orchestrator_branch: str,
        run_worker: Callable = default_run_worker,
        sandbox_probe: Callable = default_sandbox_probe,
        provider_route: Callable = default_provider_route,
        ccr_usage_db: Optional[Path] = None,
        worker_timeout_s: int = 3600,
        dry_run: bool = False,
        max_tasks: int = MAX_TASKS,
    ):
        self.repo = repo
        self.git = GitRepo(repo)
        self.backlog_path = backlog_path
        self.ccr_bin = ccr_bin
        self.ccr_profile = ccr_profile
        self.orchestrator_branch = orchestrator_branch
        self.run_worker = run_worker
        self.sandbox_probe = sandbox_probe
        self.provider_route = provider_route
        self.ccr_usage_db = ccr_usage_db or (
            Path.home() / ".claude-code-router/app-data/usage.sqlite"
        )
        self.worker_timeout_s = worker_timeout_s
        self.dry_run = dry_run
        self.max_tasks = max_tasks
        self.runs_dir = repo / RUNS_DIR

    # ------------------------------------------------------------- backlog

    def load_backlog(self) -> dict:
        return json.loads(self.backlog_path.read_text())

    def save_backlog(self, backlog: dict) -> None:
        self.backlog_path.write_text(json.dumps(backlog, indent=2, ensure_ascii=False) + "\n")

    def pick_task(self, backlog: dict, task_id: Optional[str]) -> Optional[dict]:
        items = backlog["items"]
        if task_id:
            for item in items:
                if item["id"] == task_id:
                    return item
            raise GateFailure(f"task {task_id} not found in backlog")
        for item in items:
            if item["status"] == "ready":
                return item
        for item in items:
            if item["status"] == "candidate":
                return item
        return None

    # ---------------------------------------------------------------- gates

    def gate_base(self, expected_base: Optional[str]) -> str:
        dirty = self.git.status_porcelain().strip()
        # Allowed untracked entries: the bootstrap staging inbox, this supervisor's own
        # artifacts (lock file acquired before this gate runs; scrubbed run logs) and a
        # possible /sandbox settings leftover. Anything else is an unexpected dirty
        # base -> stop.
        allowed_names = (".rush-inbox/", ".rush-supervisor-lock.json",
                         ".claude/settings.local.json")

        def _allowed(line: str) -> bool:
            name = line[3:].strip()
            return name in allowed_names or name.startswith("tools/rush/runs/")

        allowed = [l for l in dirty.splitlines() if l.startswith("?? ") and _allowed(l)]
        if len(dirty.splitlines()) > len(allowed):
            raise GateFailure(f"dirty base (uncommitted changes): {scrub(dirty)}")
        branch = self.git.current_branch()
        if branch != self.orchestrator_branch:
            raise GateFailure(f"unexpected branch {branch!r}, expected {self.orchestrator_branch!r}")
        head = self.git.head()
        if expected_base and head != expected_base and not self.git.is_ancestor(expected_base, head):
            raise GateFailure(f"HEAD {head} does not descend from expected base {expected_base}")
        return head

    def gate_sandbox(self) -> dict:
        probe = self.sandbox_probe(self.repo)
        if not self.dry_run and not probe.get("isolated"):
            raise GateFailure(
                "NO EFFECTIVE SANDBOX: supervisor refuses to launch unattended real worker "
                f"sessions on an unsandboxed host (probe: {probe}). Documentation/dry-run only."
            )
        return probe

    def gate_provider_route(self, since_iso: str) -> dict:
        route = self.provider_route(self.ccr_usage_db, since_iso)
        if route is None:
            raise GateFailure("cannot verify CCR provider route (no usage records or DB unreadable)")
        if not route["ok"]:
            raise GateFailure(f"provider route changed or unhealthy: {route}")
        return route

    def gate_worker_report(self, report: dict, task: dict, base_sha: str, branch: str) -> None:
        required = ("feature_id", "status", "base_sha", "branch", "tests")
        missing = [k for k in required if k not in report]
        if missing:
            raise GateFailure(f"worker report missing fields: {missing}")
        if report["feature_id"] != task["id"]:
            raise GateFailure(f"report feature {report['feature_id']!r} != assigned {task['id']!r}")
        if report["status"] not in ("done", "partial", "blocked"):
            raise GateFailure(f"invalid report status {report['status']!r}")
        if report["base_sha"] != base_sha:
            raise GateFailure(f"report base_sha {report['base_sha']} != expected {base_sha}")
        if report["branch"] != branch:
            raise GateFailure(f"report branch {report['branch']!r} != expected {branch!r}")
        if not isinstance(report["tests"], list) or not report["tests"]:
            raise GateFailure("missing test evidence in worker report")
        for t in report["tests"]:
            if not isinstance(t, dict) or t.get("result") not in ("pass", "fail", "skip"):
                raise GateFailure(f"malformed test entry: {t!r}")
        if any(t["result"] == "fail" for t in report["tests"]) and report["status"] == "done":
            raise GateFailure("report claims done but lists failing tests")

    def gate_commit(self, report: dict, base_sha: str, branch: str) -> list:
        commit = report.get("commit")
        if not commit:
            if report["status"] == "done":
                raise GateFailure("report claims done but has no commit")
            return []
        if not re.fullmatch(r"[0-9a-f]{7,40}", commit):
            raise GateFailure(f"malformed commit sha {commit!r}")
        if not self.git.commit_exists_on(commit, branch):
            raise GateFailure(f"commit {commit} not found on branch {branch}")
        if not self.git.is_ancestor(base_sha, commit):
            raise GateFailure(f"commit {commit} does not descend from base {base_sha}")
        return self.git.commits_between(base_sha, self.git.head())

    def gate_test_evidence(self, backlog: dict, allow_env_failures: bool = True) -> dict:
        """Independently re-run the suite. Failures are only tolerated when they are the
        documented environmental ones from the backlog's baseline record."""
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
            cwd=self.repo, capture_output=True, text=True, timeout=900,
        )
        summary = {"exit_code": proc.returncode, "tail": scrub(proc.stderr.strip().splitlines()[-1] or "")}
        if proc.returncode != 0:
            failed = re.findall(r"^(FAIL|ERROR): (\S+)", proc.stderr, re.M)
            summary["failures"] = [f"{kind}:{name}" for kind, name in failed]
            if allow_env_failures:
                known = str(backlog.get("audit_2026_10_30", {}).get("baseline_tests", ""))
                tolerated = [f for f in summary["failures"]
                             if "test_12_live_kwin_running_apps_enumeration" in f and "live" in known]
                if len(tolerated) == len(summary["failures"]):
                    summary["tolerated_environmental"] = tolerated
                    return summary
            raise GateFailure(f"independent test run failed: {summary}")
        return summary

    # ------------------------------------------------------------- worker

    def worker_argv(self, task: dict, branch: str) -> list:
        prompt = WORKER_PROMPT_TEMPLATE.format(
            feature_id=task["id"], title=task["title"], branch=branch
        )
        return [
            self.ccr_bin, self.ccr_profile, "cli", "--",
            "-p", "--output-format", "json",
            "--permission-mode", "acceptEdits",
            prompt,
        ]

    def _classify_failure(self, exit_code: int, stdout: str, stderr: str) -> str:
        blob = f"{stderr}\n{stdout[:2000]}".lower()
        if exit_code == 0:
            # process lived but produced no usable structured output: malformed
            # provider output (adapter doc #4) -> bounded retry, never unbounded
            return "transient"
        if exit_code in (124, 125) or any(p in blob for p in KNOWN_TRANSIENT_PATTERNS):
            return "transient"
        return "hard"

    def execute_task(self, task: dict, backlog: dict) -> TaskOutcome:
        base_sha = self.gate_base(None)
        feature_branch = f"feat/rush-{task['id'].lower()}"
        argv = self.worker_argv(task, feature_branch)
        outcome = TaskOutcome(feature_id=task["id"], status="supervisor_stop",
                               detail="", base_sha=base_sha, branch=feature_branch)

        if self.dry_run:
            outcome.status = "dry_run"
            outcome.detail = json.dumps({"argv": argv[:-1] + [argv[-1][:120] + "..."],
                                         "feature_branch": feature_branch,
                                         "base_sha": base_sha}, ensure_ascii=False)
            return outcome

        probe = self.gate_sandbox()
        route_started = utcnow()
        self.git.create_branch(feature_branch, base_sha)
        try:
            attempts = 0
            while True:
                attempts += 1
                since = utcnow()
                exit_code, stdout, stderr = self.run_worker(argv, self.worker_timeout_s)
                outcome.attempts = attempts
                raw_result, envelope = parse_claude_json(stdout)
                if exit_code == 0 and envelope is not None:
                    report = parse_worker_report(raw_result if isinstance(raw_result, str) else json.dumps(raw_result))
                    if report is not None:
                        self.gate_worker_report(report, task, base_sha, feature_branch)
                        outcome.commit = report.get("commit")
                        outcome.files_changed = report.get("files_changed", [])
                        outcome.tests = report.get("tests", [])
                        outcome.status = report["status"]
                        outcome.detail = scrub(str(report.get("notes", ""))[:2000])
                        new_commits = self.gate_commit(report, base_sha, feature_branch)
                        route = self.gate_provider_route(since)
                        outcome.provider_route = route
                        test_ev = self.gate_test_evidence(backlog)
                        outcome.tests.append({"name": "supervisor-independent-unittest",
                                              "result": "pass" if test_ev["exit_code"] == 0
                                                        else "pass_env_failures_tolerated"
                                                        if "tolerated_environmental" in test_ev else "fail",
                                              "command": "python3 -m unittest discover -s tests"})
                        if outcome.status == "done" and test_ev["exit_code"] != 0 and "tolerated_environmental" not in test_ev:
                            raise GateFailure("independent test evidence failed")
                        if not new_commits and outcome.status == "done":
                            raise GateFailure("no new commits on feature branch despite done")
                        return outcome
                # worker did not produce a usable result
                failure_kind = self._classify_failure(exit_code, stdout, stderr)
                side_effects = bool(self.git.status_porcelain().strip()) or \
                    self.git.commits_between(base_sha, self.git.head())
                if failure_kind == "transient" and attempts <= TRANSIENT_RETRIES and not side_effects:
                    outcome.status, outcome.error_kind = "retry", "transient"
                    continue
                raise GateFailure(
                    f"worker failed (kind={failure_kind}, exit={exit_code}, "
                    f"side_effects={bool(side_effects)}): {scrub(stderr)[:500]}"
                )
        finally:
            # Always return to the orchestrator branch; leave the feature branch intact
            # as a checkpoint, even on failure.
            self.git.checkout(self.orchestrator_branch)

    # ---------------------------------------------------------------- main

    def update_backlog_after(self, backlog: dict, task: dict, outcome: TaskOutcome,
                             merged_commit: Optional[str]) -> None:
        task["status"] = {
            "done": "implemented", "partial": "partial", "blocked": "blocked",
        }.get(outcome.status, "blocked")
        task["completed_commit"] = merged_commit or outcome.commit or task.get("completed_commit")
        task["evidence_note"] = (
            f"RUSH {utcnow()}: {outcome.status} via supervisor on {outcome.branch}; "
            f"attempts={outcome.attempts}; tests={[(t.get('name'), t.get('result')) for t in outcome.tests][:12]}; "
            f"detail={outcome.detail[:400]}"
        )
        self.save_backlog(backlog)

    def write_run_log(self, outcome: TaskOutcome, extra: dict) -> Path:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = self.runs_dir / f"{stamp}-{outcome.feature_id}.json"
        payload = json.loads(scrub(json.dumps({
            "recorded_at": utcnow(), **extra,
            "outcome": outcome.__dict__,
        }, default=str, ensure_ascii=False)))
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        return path

    def run(self, task_id: Optional[str], expected_base: Optional[str]) -> list:
        lock = WorktreeLock(self.repo)
        lock.acquire()
        completed = []
        try:
            backlog = self.load_backlog()
            base = self.gate_base(expected_base)
            sandbox = self.gate_sandbox()  # dry-run: probe recorded, real run: enforced
            if self.dry_run:
                task = self.pick_task(backlog, task_id)
                if task is None:
                    return []
                outcome = self.execute_task(task, backlog)
                log_path = self.write_run_log(outcome, {
                    "task_title": task["title"], "sandbox_probe": sandbox,
                    "expected_base": expected_base, "dry_run": True,
                })
                return [(outcome, log_path)]
            for _ in range(self.max_tasks):
                task = self.pick_task(backlog, task_id)
                if task is None:
                    break
                task_id = None  # subsequent iterations pick next ready/candidate task
                if task["status"] not in ("ready", "candidate"):
                    raise GateFailure(f"task {task['id']} not in a startable state ({task['status']})")
                task["status"] = "in_progress"
                self.save_backlog(backlog)
                try:
                    outcome = self.execute_task(task, backlog)
                except GateFailure as exc:
                    # checkpoint the failure, then stop the whole run
                    outcome = TaskOutcome(feature_id=task["id"], status="blocked",
                                          detail=scrub(str(exc))[:2000],
                                          base_sha=base, error_kind="gate_failure")
                    self.update_backlog_after(backlog, task, outcome, None)
                    self.write_run_log(outcome, {
                        "task_title": task["title"], "sandbox_probe": sandbox,
                        "expected_base": expected_base, "dry_run": False,
                    })
                    raise
                merged = None
                if outcome.status == "done":
                    self.git.merge_no_ff(outcome.branch,
                                         f"merge(rush): {outcome.feature_id} verified feature")
                    self.git.push("origin", outcome.branch, self.orchestrator_branch)
                    merged = self.git.head()
                self.update_backlog_after(backlog, task, outcome, merged)
                log_path = self.write_run_log(outcome, {
                    "task_title": task["title"], "sandbox_probe": sandbox,
                    "expected_base": expected_base, "dry_run": False,
                })
                completed.append((outcome, log_path))
                if outcome.status != "done":
                    break
                expected_base = self.git.head()
                backlog = self.load_backlog()
            return completed
        finally:
            lock.release()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", type=Path, default=REPO_DEFAULT)
    parser.add_argument("--backlog", default=BACKLOG_DEFAULT)
    parser.add_argument("--task", default=None, help="backlog item id, e.g. DOCK-004")
    parser.add_argument("--base", default=None, help="expected base sha (default: current HEAD)")
    parser.add_argument("--dry-run", action="store_true",
                        help="plan and print actions without spawning any worker")
    parser.add_argument("--max-tasks", type=int, default=MAX_TASKS)
    parser.add_argument("--ccr-bin",
                        default=str(Path.home() / ".local/share/evren-cli/node_modules/.bin/ccr"))
    parser.add_argument("--ccr-profile", default="EVREN - QS KDE")
    parser.add_argument("--orchestrator-branch", default="feat/rush-orchestrator")
    parser.add_argument("--worker-timeout", type=int, default=3600)
    args = parser.parse_args(argv)

    repo = args.repo.resolve()
    supervisor = RushSupervisor(
        repo=repo,
        backlog_path=repo / args.backlog,
        ccr_bin=args.ccr_bin,
        ccr_profile=args.ccr_profile,
        orchestrator_branch=args.orchestrator_branch,
        worker_timeout_s=args.worker_timeout,
        dry_run=args.dry_run,
        max_tasks=args.max_tasks,
    )
    try:
        completed = supervisor.run(args.task, args.base)
    except GateFailure as exc:
        print(f"SUPERVISOR STOP: {exc}", file=sys.stderr)
        return 2
    for outcome, log_path in completed:
        print(f"{outcome.feature_id}: {outcome.status} (log: {log_path})")
    if args.dry_run:
        print("dry-run complete: no worker was spawned")
    return 0


if __name__ == "__main__":
    sys.exit(main())
