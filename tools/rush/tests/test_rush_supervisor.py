#!/usr/bin/env python3
"""Unit and fixture tests for the rush supervisor.

All external effects (git, worker subprocess, sandbox probe, provider DB, test runs)
are mocked or replaced with local fixtures. No network, no real git repo, no CCR.
Run: python3 -m unittest discover -s tools/rush/tests
"""

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

TOOLS_RUSH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_RUSH))

import rush_supervisor as rs  # noqa: E402


def make_backlog(task_status="ready", task_id="DOCK-004"):
    return {
        "schema_version": 2,
        "audit_2026_10_30": {"baseline_tests": "live-session test may fail environmentally"},
        "items": [
            {"id": task_id, "rank_2026_10_26": 4, "title": "Parabolic zoom",
             "status": task_status, "evidence_note": "x", "completed_commit": None,
             "live_verified": False, "owner": None},
            {"id": "DOCK-009", "rank_2026_10_26": 9, "title": "Badges",
             "status": "candidate", "evidence_note": "x", "completed_commit": None,
             "live_verified": False, "owner": None},
        ],
    }


class FakeGit:
    """In-memory git double with the exact surface GitRepo exposes."""

    def __init__(self, branch="feat/rush-orchestrator", head="a" * 40):
        self.branch = branch
        self.head_ = head
        self.dirty = ""
        self.commits = {head: []}  # head -> list of ancestor shas
        self.branch_tips = {branch: head}
        self.actions = []

    def current_branch(self):
        return self.branch

    def head(self):
        return self.head_

    def status_porcelain(self):
        return self.dirty

    def is_ancestor(self, sha, ref):
        tip = self.branch_tips.get(ref, ref)
        return sha == tip or sha in self.commits.get(tip, [])

    def commit_exists_on(self, sha, branch):
        return self.is_ancestor(sha, branch)

    def create_branch(self, name, start):
        self.actions.append(("create_branch", name, start))
        self.branch_tips[name] = self.branch_tips.get(start, start)
        self.branch = name
        self.head_ = self.branch_tips[name]

    def checkout(self, ref):
        self.actions.append(("checkout", ref))
        self.branch = ref
        self.head_ = self.branch_tips.get(ref, self.head_)

    def merge_no_ff(self, branch, message):
        self.actions.append(("merge", branch))
        feature_tip = self.branch_tips[branch]
        self.commits.setdefault(feature_tip, [])
        if self.head_ not in self.commits[feature_tip] and self.head_ != feature_tip:
            self.commits[feature_tip].append(self.head_)
        self.branch_tips[self.branch] = feature_tip
        self.head_ = feature_tip

    def push(self, *refs):
        self.actions.append(("push",) + refs)

    def commits_between(self, base, head):
        head_tip = self.branch_tips.get(head, head)
        chain = [head_tip] + self.commits.get(head_tip, [])
        return [c for c in chain if c != base and self.is_ancestor(base, c)]


def worker_stdout(report, notes="ok"):
    body = (
        f"work done. notes: {notes}\n\n```rush-report\n"
        + json.dumps(report)
        + "\n```"
    )
    return json.dumps({"subtype": "success", "result": body, "total_cost_usd": 0.01})


def good_report(task_id="DOCK-004", base="a" * 40, branch="feat/rush-dock-004",
                commit="b" * 40, status="done"):
    return {
        "feature_id": task_id, "status": status, "base_sha": base, "branch": branch,
        "commit": commit, "files_changed": ["modules/dock/DockItem.qml"],
        "tests": [{"name": "test_zoom", "result": "pass", "command": "python3 -m unittest"}],
        "notes": "implemented",
    }


class SupervisorHarness(unittest.TestCase):
    """Builds a supervisor with all external effects faked."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        self.backlog_path = self.repo / "docs/roadmap/DOCK_BACKLOG.json"
        self.backlog_path.parent.mkdir(parents=True)
        self.backlog = make_backlog()
        self.backlog_path.write_text(json.dumps(self.backlog))
        self.fake_git = FakeGit()
        self.worker_calls = []
        self.worker_results = []  # scripted (exit, stdout, stderr); empty -> auto-succeed
        self.worker_hooks = []    # one-shot callables run after a scripted worker result
        self.sandbox_result = {"isolated": True, "home_write": "blocked",
                               "external_network": "blocked", "seccomp": "2"}
        self.route_result = {"ok": True, "providers": ["EVREN"],
                             "models": ["zai/glm-5.3-fp8"], "status_codes": [200],
                             "events": 3}
        self.test_run_result = subprocess.CompletedProcess(
            [], 0, "", "Ran 158 tests in 1s\n\nOK\n")
        supervisor = rs.RushSupervisor(
            repo=self.repo, backlog_path=self.backlog_path,
            ccr_bin="/usr/bin/ccr", ccr_profile="EVREN - QS KDE",
            orchestrator_branch="feat/rush-orchestrator",
            run_worker=self._run_worker,
            sandbox_probe=lambda repo: dict(self.sandbox_result),
            provider_route=lambda db, since: dict(self.route_result)
            if self.route_result else None,
            dry_run=False,
        )
        supervisor.git = self.fake_git
        self.supervisor = supervisor

    def tearDown(self):
        self.tmp.cleanup()

    def _run_worker(self, argv, timeout):
        """Fake worker: pops a scripted result if present, otherwise simulates a
        well-behaved worker that implements the assigned feature and commits on
        the checked-out feature branch."""
        self.worker_calls.append(list(argv))
        prompt = argv[-1]
        if self.worker_results:
            exit_code, stdout, stderr = self.worker_results.pop(0)
            while self.worker_hooks:
                self.worker_hooks.pop(0)()
            return exit_code, stdout, stderr
        import re
        fid = re.search(r"feature (DOCK-\d+)", prompt).group(1)
        branch = re.search(r"branch only: ([\w/-]+)", prompt).group(1)
        base = self.fake_git.head()
        commit = uuid.uuid4().hex
        # simulate the worker committing on the feature branch
        self.fake_git.branch_tips[branch] = commit
        self.fake_git.commits[commit] = [base]
        self.fake_git.head_ = commit
        report = good_report(task_id=fid, base=base, branch=branch, commit=commit)
        return 0, worker_stdout(report), ""

    def _patch_tests(self):
        return mock.patch.object(rs.subprocess, "run", return_value=self.test_run_result)


class TestScrub(unittest.TestCase):
    def test_scrubs_common_credentials(self):
        text = "key sk-abcdef1234567890 and Bearer abcdef123456 and api_key = supersecret123"
        out = rs.scrub(text)
        self.assertNotIn("sk-abcdef1234567890", out)
        self.assertNotIn("Bearer abcdef123456", out)
        self.assertNotIn("supersecret123", out)

    def test_scrub_keeps_normal_text(self):
        text = "test_04 passed with 12 assertions"
        self.assertEqual(rs.scrub(text), text)


class TestParsing(unittest.TestCase):
    def test_parse_worker_report_extracts_last_block(self):
        report = good_report()
        result, envelope = rs.parse_claude_json(worker_stdout(report))
        self.assertIn("rush-report", result)
        parsed = rs.parse_worker_report(result)
        self.assertEqual(parsed["feature_id"], "DOCK-004")

    def test_parse_worker_report_rejects_missing_block(self):
        self.assertIsNone(rs.parse_worker_report("no report here"))
        self.assertIsNone(rs.parse_worker_report("```rush-report\n{not json}\n```"))

    def test_parse_claude_json_fallback(self):
        result, envelope = rs.parse_claude_json("plain text not json")
        self.assertEqual(result, "plain text not json")
        self.assertIsNone(envelope)


class TestWorkerArgv(SupervisorHarness):
    def test_argument_array_contract(self):
        task = self.backlog["items"][0]
        argv = self.supervisor.worker_argv(task, "feat/rush-dock-004")
        # subprocess argument array, not a shell string
        self.assertIsInstance(argv, list)
        self.assertTrue(all(isinstance(a, str) for a in argv))
        # reuses configured CCR named profile, forwards after --
        self.assertEqual(argv[:4], ["/usr/bin/ccr", "EVREN - QS KDE", "cli", "--"])
        # fresh print-mode session with structured output and safe permission mode
        self.assertIn("-p", argv)
        self.assertIn("--output-format", argv)
        self.assertIn("acceptEdits", argv)
        # never bypasses permissions, never forces Anthropic model aliases
        self.assertNotIn("--dangerously-skip-permissions", argv)
        self.assertNotIn("--model", " ".join(argv[:8]))
        # prompt names the assigned feature and the report contract
        prompt = argv[-1]
        self.assertIn("DOCK-004", prompt)
        self.assertIn("rush-report", prompt)
        self.assertIn("feat/rush-dock-004", prompt)


class TestGates(SupervisorHarness):
    def test_gate_base_rejects_dirty_tree(self):
        self.fake_git.dirty = " M modules/dock/Dock.qml"
        with self.assertRaises(rs.GateFailure):
            self.supervisor.gate_base(None)

    def test_gate_base_allows_rush_inbox_only(self):
        self.fake_git.dirty = "?? .rush-inbox/"
        self.supervisor.gate_base(None)  # must not raise

    def test_gate_base_allows_supervisor_own_lock(self):
        # the lock file is acquired before gate_base runs; it must not self-block
        self.fake_git.dirty = "?? .rush-inbox/\n?? .rush-supervisor-lock.json"
        self.supervisor.gate_base(None)  # must not raise

    def test_gate_base_allows_supervisor_run_logs(self):
        # scrubbed run logs are the supervisor's own evidence trail
        self.fake_git.dirty = "?? tools/rush/runs/20261030T034000Z-DOCK-004.json"
        self.supervisor.gate_base(None)  # must not raise

    def test_gate_base_rejects_dirty_plus_inbox(self):
        self.fake_git.dirty = "?? .rush-inbox/\n M modules/dock/Dock.qml"
        with self.assertRaises(rs.GateFailure):
            self.supervisor.gate_base(None)

    def test_gate_base_rejects_wrong_branch(self):
        self.fake_git.branch = "main"
        with self.assertRaises(rs.GateFailure):
            self.supervisor.gate_base(None)

    def test_gate_base_rejects_wrong_ancestry(self):
        with self.assertRaises(rs.GateFailure):
            self.supervisor.gate_base("f" * 40)

    def test_gate_sandbox_refuses_real_run_when_unsandboxed(self):
        self.sandbox_result = {"isolated": False, "home_write": "allowed",
                               "external_network": "allowed"}
        with self.assertRaises(rs.GateFailure) as ctx:
            self.supervisor.gate_sandbox()
        self.assertIn("NO EFFECTIVE SANDBOX", str(ctx.exception))

    def test_gate_sandbox_dry_run_records_but_does_not_stop(self):
        self.sandbox_result = {"isolated": False, "home_write": "allowed",
                               "external_network": "allowed"}
        self.supervisor.dry_run = True
        probe = self.supervisor.gate_sandbox()
        self.assertFalse(probe["isolated"])

    def test_gate_provider_route_ok(self):
        route = self.supervisor.gate_provider_route("2026-10-30T00:00:00+00:00")
        self.assertTrue(route["ok"])

    def test_gate_provider_route_stops_on_model_change(self):
        self.route_result = {"ok": False, "providers": ["EVREN"],
                             "models": ["claude-opus-5-5"], "status_codes": [200],
                             "events": 1}
        with self.assertRaises(rs.GateFailure):
            self.supervisor.gate_provider_route("x")

    def test_gate_provider_route_stops_when_unverifiable(self):
        self.route_result = None
        with self.assertRaises(rs.GateFailure):
            self.supervisor.gate_provider_route("x")

    def test_gate_worker_report_validations(self):
        task = self.backlog["items"][0]
        base, branch = "a" * 40, "feat/rush-dock-004"
        ok = good_report(base=base, branch=branch)
        self.supervisor.gate_worker_report(ok, task, base, branch)
        bad = dict(ok); del bad["tests"]
        with self.assertRaises(rs.GateFailure):
            self.supervisor.gate_worker_report(bad, task, base, branch)
        bad = good_report(base=base, branch=branch, task_id="DOCK-999")
        with self.assertRaises(rs.GateFailure):
            self.supervisor.gate_worker_report(bad, task, base, branch)
        bad = good_report(base=base, branch=branch)
        bad["status"] = "done"
        bad["tests"] = [{"name": "t", "result": "fail", "command": "x"}]
        with self.assertRaises(rs.GateFailure):
            self.supervisor.gate_worker_report(bad, task, base, branch)
        bad = good_report(base="c" * 40, branch=branch)
        with self.assertRaises(rs.GateFailure):
            self.supervisor.gate_worker_report(bad, task, base, branch)

    def test_gate_commit_rejects_foreign_commit(self):
        report = good_report(commit="b" * 40)
        self.fake_git.branch_tips["feat/rush-dock-004"] = "a" * 40
        with self.assertRaises(rs.GateFailure):
            self.supervisor.gate_commit(report, "a" * 40, "feat/rush-dock-004")

    def test_gate_commit_rejects_malformed_sha(self):
        report = good_report(commit="HEAD; rm -rf /")
        with self.assertRaises(rs.GateFailure):
            self.supervisor.gate_commit(report, "a" * 40, "feat/rush-dock-004")

    def test_gate_test_evidence_tolerates_documented_env_failure(self):
        self.test_run_result = subprocess.CompletedProcess(
            [], 1, "",
            "FAIL: test_12_live_kwin_running_apps_enumeration "
            "(test_runtime_ux.TestDesktopUX.test_12_live_kwin_running_apps_enumeration)\n"
            "Ran 158 tests\n\nFAILED (failures=1)")
        with self._patch_tests():
            summary = self.supervisor.gate_test_evidence(self.backlog)
        self.assertIn("tolerated_environmental", summary)

    def test_gate_test_evidence_stops_on_real_failure(self):
        self.test_run_result = subprocess.CompletedProcess(
            [], 1, "",
            "FAIL: test_zoom_broken (test_dock_blitz.TestDockBlitz.test_zoom_broken)\n"
            "Ran 158 tests\n\nFAILED (failures=1)")
        with self._patch_tests():
            with self.assertRaises(rs.GateFailure):
                self.supervisor.gate_test_evidence(self.backlog)


class TestExecuteTask(SupervisorHarness):
    def test_success_flow_lifecycle(self):
        task = self.backlog["items"][0]
        with self._patch_tests():
            outcome = self.supervisor.execute_task(task, self.backlog)
        self.assertEqual(outcome.status, "done")
        self.assertEqual(outcome.feature_id, "DOCK-004")
        self.assertIsNotNone(outcome.commit)
        self.assertNotEqual(outcome.commit, "a" * 40)
        self.assertEqual(outcome.attempts, 1)
        # branch created from base, then returned to orchestrator branch
        self.assertIn(("create_branch", "feat/rush-dock-004", "a" * 40), self.fake_git.actions)
        self.assertEqual(self.fake_git.actions[-1], ("checkout", "feat/rush-orchestrator"))
        # supervisor independently re-ran the test suite and appended evidence
        self.assertTrue(any(t["name"] == "supervisor-independent-unittest" for t in outcome.tests))
        self.assertIsNotNone(outcome.provider_route)

    def test_transient_failure_retries_once_then_succeeds(self):
        self.worker_results.append((1, "", "gateway 503 bad gateway timeout"))
        task = self.backlog["items"][0]
        with self._patch_tests():
            outcome = self.supervisor.execute_task(task, self.backlog)
        self.assertEqual(outcome.status, "done")
        self.assertEqual(outcome.attempts, 2)
        self.assertEqual(len(self.worker_calls), 2)

    def test_hard_failure_stops_without_retry(self):
        self.worker_results.append((1, "", "worker refused: permission denied by user"))
        task = self.backlog["items"][0]
        with self._patch_tests():
            with self.assertRaises(rs.GateFailure) as ctx:
                self.supervisor.execute_task(task, self.backlog)
        self.assertIn("kind=hard", str(ctx.exception))
        self.assertEqual(len(self.worker_calls), 1)

    def test_transient_with_side_effects_never_retries(self):
        self.worker_results.append((1, "", "gateway timeout"))
        # the failed worker left uncommitted changes behind
        self.worker_hooks.append(lambda: setattr(
            self.fake_git, "dirty", " M modules/dock/DockItem.qml"))
        task = self.backlog["items"][0]
        with self._patch_tests():
            with self.assertRaises(rs.GateFailure) as ctx:
                self.supervisor.execute_task(task, self.backlog)
        self.assertIn("side_effects=True", str(ctx.exception))
        self.assertEqual(len(self.worker_calls), 1)

    def test_malformed_output_retries_then_stops(self):
        self.worker_results.append((0, "garbage not json", ""))
        self.worker_results.append((0, "garbage not json", ""))
        task = self.backlog["items"][0]
        with self._patch_tests():
            with self.assertRaises(rs.GateFailure):
                self.supervisor.execute_task(task, self.backlog)
        self.assertEqual(len(self.worker_calls), 2)  # 1 attempt + 1 bounded retry

    def test_missing_test_evidence_in_report_stops(self):
        report = good_report()
        report["tests"] = []
        self.worker_results.append((0, worker_stdout(report), ""))
        task = self.backlog["items"][0]
        with self._patch_tests():
            with self.assertRaises(rs.GateFailure):
                self.supervisor.execute_task(task, self.backlog)

    def test_dry_run_never_spawns_worker(self):
        self.supervisor.dry_run = True
        task = self.backlog["items"][0]
        outcome = self.supervisor.execute_task(task, self.backlog)
        self.assertEqual(outcome.status, "dry_run")
        self.assertEqual(self.worker_calls, [])
        planned = json.loads(outcome.detail)
        self.assertEqual(planned["feature_branch"], "feat/rush-dock-004")


class TestRunLoop(SupervisorHarness):
    def test_run_updates_backlog_and_merges_on_done(self):
        with self._patch_tests():
            completed = self.supervisor.run("DOCK-004", "a" * 40)
        self.assertEqual(len(completed), 2)  # DOCK-004 then DOCK-009
        outcomes = [o for o, _ in completed]
        self.assertEqual([o.feature_id for o in outcomes], ["DOCK-004", "DOCK-009"])
        self.assertTrue(all(o.status == "done" for o in outcomes))
        updated = json.loads(self.backlog_path.read_text())
        by_id = {i["id"]: i for i in updated["items"]}
        self.assertEqual(by_id["DOCK-004"]["status"], "implemented")
        self.assertEqual(by_id["DOCK-009"]["status"], "implemented")
        self.assertIn("RUSH ", by_id["DOCK-004"]["evidence_note"])
        # feature branch merged into orchestrator branch and both pushed
        self.assertTrue(any(a[0] == "merge" for a in self.fake_git.actions))
        pushes = [a for a in self.fake_git.actions if a[0] == "push"]
        self.assertTrue(all("main" not in p for p in pushes))
        # run logs written, scrubbed
        runs = list((self.repo / "tools/rush/runs").glob("*.json"))
        self.assertEqual(len(runs), 2)

    def test_run_stops_after_non_done_outcome(self):
        self.worker_results.append((0, worker_stdout(good_report(status="blocked", commit=None)), ""))
        with self._patch_tests():
            completed = self.supervisor.run("DOCK-004", "a" * 40)
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0][0].status, "blocked")
        updated = json.loads(self.backlog_path.read_text())
        self.assertEqual(updated["items"][0]["status"], "blocked")

    def test_run_refuses_when_sandbox_missing(self):
        self.sandbox_result = {"isolated": False}
        with self.assertRaises(rs.GateFailure) as ctx:
            self.supervisor.run(None, None)
        self.assertIn("NO EFFECTIVE SANDBOX", str(ctx.exception))
        self.assertEqual(self.worker_calls, [])

    def test_run_dry_run_plans_without_spawning(self):
        self.supervisor.dry_run = True
        self.sandbox_result = {"isolated": False}  # unsandboxed host: still fine for dry-run
        completed = self.supervisor.run("DOCK-004", "a" * 40)
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0][0].status, "dry_run")
        self.assertEqual(self.worker_calls, [])
        # backlog untouched apart from in_progress marker? dry-run must not fake success
        updated = json.loads(self.backlog_path.read_text())
        self.assertNotEqual(updated["items"][0]["status"], "implemented")


class TestWorktreeLock(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_lock_and_unlock(self):
        lock = rs.WorktreeLock(self.repo)
        lock.acquire()
        self.assertTrue((self.repo / rs.LOCK_FILE).exists())
        second = rs.WorktreeLock(self.repo)
        with self.assertRaises(rs.GateFailure):
            second.acquire()
        lock.release()
        second.acquire()  # now free
        second.release()

    def test_stale_lock_from_dead_pid_is_reclaimed(self):
        stale = self.repo / rs.LOCK_FILE
        stale.write_text(json.dumps({"pid": 999999999, "started_epoch": 0, "started": "old"}))
        lock = rs.WorktreeLock(self.repo)
        lock.acquire()  # must not raise
        lock.release()


class TestProviderRouteFixture(unittest.TestCase):
    """Exercises the real sqlite reading code against a local fixture DB."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "usage.sqlite"
        con = sqlite3.connect(self.db)
        con.execute("""CREATE TABLE usage_events (
            id INTEGER PRIMARY KEY, created_at TEXT, provider TEXT, model TEXT,
            status_code INTEGER)""")
        con.executemany(
            "INSERT INTO usage_events (created_at, provider, model, status_code) VALUES (?,?,?,?)",
            [("2026-10-30T03:00:00+00:00", "EVREN", "zai/glm-5.3-fp8", 200),
             ("2026-10-30T03:01:00+00:00", "EVREN", "zai/glm-5.3-fp8", 200)])
        con.commit()
        con.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_ok_route(self):
        route = rs.default_provider_route(self.db, "2026-10-30T02:00:00+00:00")
        self.assertIsNotNone(route)
        self.assertTrue(route["ok"])
        self.assertEqual(route["providers"], ["EVREN"])

    def test_wrong_model_detected(self):
        con = sqlite3.connect(self.db)
        con.execute("INSERT INTO usage_events (created_at, provider, model, status_code) "
                    "VALUES ('2026-10-30T03:02:00+00:00','EVREN','claude-opus-5-5',200)")
        con.commit()
        con.close()
        route = rs.default_provider_route(self.db, "2026-10-30T02:00:00+00:00")
        self.assertFalse(route["ok"])

    def test_non_200_detected(self):
        con = sqlite3.connect(self.db)
        con.execute("INSERT INTO usage_events (created_at, provider, model, status_code) "
                    "VALUES ('2026-10-30T03:02:00+00:00','EVREN','zai/glm-5.3-fp8',429)")
        con.commit()
        con.close()
        route = rs.default_provider_route(self.db, "2026-10-30T02:00:00+00:00")
        self.assertFalse(route["ok"])

    def test_missing_db_returns_none(self):
        self.assertIsNone(rs.default_provider_route(Path("/nonexistent/x.sqlite"), "x"))


class TestSecretScrubInLogs(SupervisorHarness):
    def test_run_log_contains_no_worker_secrets(self):
        report = good_report()
        report["notes"] = "accidentally pasted token sk-abcdef1234567890xyz"
        self.worker_results.append((0, worker_stdout(report), ""))
        # simulate the worker commit so the success gates can pass
        self.worker_hooks.append(self._fake_commit_from_report)
        with self._patch_tests():
            self.supervisor.run("DOCK-004", "a" * 40)
        for log in (self.repo / "tools/rush/runs").glob("*.json"):
            content = log.read_text()
            self.assertNotIn("sk-abcdef1234567890xyz", content)

    def _fake_commit_from_report(self):
        commit = "b" * 40
        self.fake_git.branch_tips["feat/rush-dock-004"] = commit
        self.fake_git.commits[commit] = ["a" * 40]
        self.fake_git.head_ = commit


if __name__ == "__main__":
    unittest.main()
