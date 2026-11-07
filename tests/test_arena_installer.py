"""Adversarial tests for the quickshell-kde arena installer.

Every test drives the real installer CLI as a subprocess against a
disposable temporary HOME / XDG_DATA_HOME / XDG_CONFIG_HOME. The host
user's actual HOME is never touched. All temporary homes deliberately
contain spaces to cover path-quoting behavior everywhere.

Run:  python3 -m unittest tests.test_arena_installer -v
"""

from __future__ import annotations

import fcntl
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALLER = os.path.join(REPO_ROOT, "installer", "arena_installer.py")

TIMEOUT = 90


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class InstallerHarness(unittest.TestCase):
    """Base fixture: disposable env with spaces in every path."""

    def setUp(self):
        self._tmp_parent = tempfile.mkdtemp(prefix="qskde-installer-test-")
        # Spaces on purpose: every path the installer manages must
        # survive them.
        self.home = os.path.join(self._tmp_parent, "home dir")
        self.data_home = os.path.join(self.home, ".local", "share")
        self.config_home = os.path.join(self.home, ".config")
        os.makedirs(self.home)

        self.source = self.make_source("src fixture")
        # A stub PATH directory the tests control.
        self.bin_dir = os.path.join(self._tmp_parent, "stubbin")
        os.makedirs(self.bin_dir)
        for tool in (
            "quickshell", "qdbus6", "kdotool", "gio", "python3",
            "dbus-monitor", "wpctl", "loginctl", "fc-list",
            "kcmshell6", "systemsettings", "upower",
        ):
            self.make_stub(tool)

    def tearDown(self):
        shutil.rmtree(self._tmp_parent, ignore_errors=True)

    # -- environment -------------------------------------------------------

    def env(self, path=None):
        env = dict(os.environ)
        env.update(
            {
                "HOME": self.home,
                "XDG_DATA_HOME": self.data_home,
                "XDG_CONFIG_HOME": self.config_home,
                "PATH": path if path is not None else self.bin_dir,
            }
        )
        return env

    def run_installer(self, *args, path=None, timeout=TIMEOUT):
        proc = subprocess.run(
            [sys.executable, INSTALLER, *args],
            env=self.env(path),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc

    # -- fixtures ----------------------------------------------------------

    def make_source(self, marker="fixture", extra_files=None):
        """A minimal quickshell-kde-like source tree."""
        src = tempfile.mkdtemp(prefix="qskde-src-", dir=self._tmp_parent)
        with open(os.path.join(src, "shell.qml"), "w") as fh:
            fh.write(f"// shell {marker}\n")
        os.makedirs(os.path.join(src, "config"))
        with open(os.path.join(src, "config", "dock_config.json"), "w") as fh:
            fh.write(json.dumps({"marker": marker}))
        os.makedirs(os.path.join(src, "modules", "dock"))
        with open(os.path.join(src, "modules", "dock", "Dock.qml"), "w") as fh:
            fh.write(f"// dock {marker}\n")
        # A file with spaces in the name, copied through every install.
        with open(os.path.join(src, "a file with spaces.txt"), "w") as fh:
            fh.write(marker)
        for rel in extra_files or []:
            target = os.path.join(src, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w") as fh:
                fh.write(rel)
        return src

    def make_stub(self, name):
        path = os.path.join(self.bin_dir, name)
        with open(path, "w") as fh:
            fh.write("#!/bin/sh\nexit 0\n")
        os.chmod(path, 0o755)

    # -- assertions --------------------------------------------------------

    @property
    def data_root(self):
        return os.path.join(self.data_home, "quickshell-kde")

    @property
    def releases_dir(self):
        return os.path.join(self.data_root, "releases")

    @property
    def launcher_path(self):
        return os.path.join(self.home, ".local", "bin", "quickshell-kde")

    @property
    def user_config_dir(self):
        return os.path.join(self.config_home, "quickshell-kde")

    def release(self, version):
        return os.path.join(self.releases_dir, version)

    def current_target(self):
        current = os.path.join(self.data_root, "current")
        return os.readlink(current) if os.path.islink(current) else None

    def manifest(self):
        with open(os.path.join(self.data_root, "manifest.json")) as fh:
            return json.load(fh)

    def assertInstalled(self, version, marker=None):
        """The release is active, complete and owns its files."""
        release = self.release(version)
        self.assertTrue(os.path.isdir(release), f"{release} missing")
        self.assertTrue(
            os.path.isfile(os.path.join(release, "shell.qml")),
            "shell.qml missing in release",
        )
        self.assertTrue(
            os.path.isfile(os.path.join(release, ".quickshell-kde-release")),
            "release marker missing",
        )
        current = os.path.join(self.data_root, "current")
        self.assertTrue(os.path.islink(current), "current is not a symlink")
        self.assertEqual(self.current_target(), os.path.join("releases", version))
        # Resolving current must reach the release content.
        resolved = os.path.join(self.data_root, self.current_target())
        if marker is not None:
            with open(os.path.join(resolved, "shell.qml")) as fh:
                self.assertIn(marker, fh.read())
        self.assertTrue(os.path.isfile(self.launcher_path), "launcher missing")
        self.assertTrue(
            os.access(self.launcher_path, os.X_OK), "launcher not executable"
        )
        manifest = self.manifest()
        self.assertEqual(manifest["current"], version)
        self.assertIn(self.release(version), manifest["owned"])

    def install(self, source=None, version="v1", extra=(), expect=0):
        proc = self.run_installer(
            "install", source or self.source, "--version", version, *extra
        )
        self.assertEqual(
            proc.returncode, expect,
            f"install {version} rc={proc.returncode}\nstdout:{proc.stdout}\nstderr:{proc.stderr}"
        )
        return proc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHelpAndCLI(InstallerHarness):
    def test_help_exits_zero_and_documents_commands(self):
        proc = self.run_installer("--help")
        self.assertEqual(proc.returncode, 0)
        for command in ("install", "update", "rollback", "uninstall", "doctor"):
            self.assertIn(command, proc.stdout)

    def test_unknown_command_fails(self):
        proc = self.run_installer("frobnicate")
        self.assertNotEqual(proc.returncode, 0)


class TestCleanInstall(InstallerHarness):
    def test_clean_install_from_directory(self):
        proc = self.install(version="v1")
        self.assertIn("installed quickshell-kde v1", proc.stdout)
        self.assertInstalled("v1", marker="shell src fixture")
        # The launcher references the resolved data root and passes the
        # shell.qml through current.
        with open(self.launcher_path) as fh:
            content = fh.read()
        self.assertIn(self.data_root, content)
        self.assertIn("current/shell.qml", content)

    def test_clean_install_from_real_checkout(self):
        """The actual repository worktree installs and ships no VCS data."""
        proc = self.run_installer(
            "install", REPO_ROOT, "--version", "real-checkout"
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        release = self.release("real-checkout")
        self.assertTrue(os.path.isfile(os.path.join(release, "shell.qml")))
        self.assertFalse(
            os.path.exists(os.path.join(release, ".git")),
            ".git must not be shipped into releases",
        )
        self.assertTrue(
            os.path.isfile(os.path.join(release, "config", "dock_config.json"))
        )

    def test_install_from_archive(self):
        archive = os.path.join(self._tmp_parent, "release.tar.gz")
        with tarfile.open(archive, "w:gz") as tf:
            tf.add(self.source, arcname="quickshell-kde-1.0")
        proc = self.run_installer("install", archive, "--version", "arch1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertInstalled("arch1")
        # The wrapping directory is descended into automatically.
        self.assertTrue(
            os.path.isfile(self.release("arch1") + "/shell.qml")
        )

    def test_dry_run_touches_nothing(self):
        proc = self.install(version="v1", extra=("--dry-run",))
        self.assertIn("dry-run", proc.stdout)
        self.assertFalse(os.path.exists(self.data_root), "data root was created")
        self.assertFalse(os.path.exists(self.launcher_path))

    def test_autostart_off_by_default(self):
        self.install()
        autostart = os.path.join(
            self.config_home, "autostart", "quickshell-kde.desktop"
        )
        self.assertFalse(os.path.exists(autostart))

    def test_autostart_opt_in(self):
        self.install(extra=("--enable-autostart",))
        autostart = os.path.join(
            self.config_home, "autostart", "quickshell-kde.desktop"
        )
        self.assertTrue(os.path.isfile(autostart))
        with open(autostart) as fh:
            content = fh.read()
        self.assertIn("Type=Application", content)
        self.assertIn(self.launcher_path, content)
        self.assertIn(self.release("v1"), self.manifest()["owned"])


class TestRepeatedInstallAndUpgrade(InstallerHarness):
    def test_repeated_install_replaces_same_version(self):
        self.install(version="v1")
        src2 = self.make_source("second copy")
        proc = self.run_installer("install", src2, "--version", "v1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertInstalled("v1", marker="second copy")
        # Exactly one v1 release directory exists afterwards.
        self.assertEqual(
            [n for n in os.listdir(self.releases_dir) if n == "v1"], ["v1"]
        )
        # Re-installing the same version must not make it its own
        # rollback target.
        self.assertNotEqual(self.manifest()["previous"], "v1")

    def test_upgrade_and_rollback(self):
        self.install(version="v1")
        src2 = self.make_source("upgraded")
        proc = self.run_installer("update", src2, "--version", "v2")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertInstalled("v2", marker="upgraded")
        manifest = self.manifest()
        self.assertEqual(manifest["previous"], "v1")

        # Rollback returns to v1 with old content intact.
        proc = self.run_installer("rollback")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertInstalled("v1", marker="src fixture")

        # Rolling back again swaps back (current<->previous ping-pong).
        proc = self.run_installer("rollback")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertInstalled("v2", marker="upgraded")

    def test_rollback_without_previous_fails(self):
        self.install()
        proc = self.run_installer("rollback")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("previous", proc.stderr)

    def test_update_requires_existing_install(self):
        src2 = self.make_source("update source")
        proc = self.run_installer("update", src2, "--version", "v2")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("install", proc.stderr)
        self.assertFalse(os.path.exists(self.data_root))

    def test_failed_upgrade_leaves_previous_release_intact(self):
        self.install(version="v1")
        bad_source = tempfile.mkdtemp(prefix="qskde-bad-", dir=self._tmp_parent)
        with open(os.path.join(bad_source, "not-a-shell.txt"), "w") as fh:
            fh.write("nope")
        proc = self.run_installer("update", bad_source, "--version", "v2")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("shell.qml", proc.stderr)
        self.assertInstalled("v1")
        self.assertFalse(os.path.exists(self.release("v2")))

    def test_failure_before_commit_leaves_no_trace(self):
        """A launcher that cannot be written aborts before the commit
        point; the previous release stays active and no new release
        remains on disk."""
        self.install(version="v1")
        # Replace the launcher target with a directory: it cannot be
        # overwritten by our file write.
        launcher_dir = self.launcher_path
        os.remove(launcher_dir)
        os.makedirs(launcher_dir)
        src2 = self.make_source("doomed")
        proc = self.run_installer("update", src2, "--version", "v2")
        self.assertNotEqual(proc.returncode, 0)
        self.assertTrue(os.path.isdir(launcher_dir))
        # The old release is still active and consistent.
        manifest = self.manifest()
        self.assertEqual(manifest["current"], "v1")
        self.assertEqual(self.current_target(), "releases/v1")
        # The failed v2 release must not linger as an activated release.
        self.assertFalse(os.path.exists(self.release("v2")))


class TestUninstall(InstallerHarness):
    def test_uninstall_removes_only_owned_paths(self):
        self.install()
        # User configuration and unrelated files must survive.
        os.makedirs(self.user_config_dir)
        with open(os.path.join(self.user_config_dir, "dock_config.json"), "w") as fh:
            fh.write('{"user": true}')
        unrelated = os.path.join(self.data_root, "unrelated-user-file.txt")
        with open(unrelated, "w") as fh:
            fh.write("not ours")
        # An unrelated Quickshell installation must survive too.
        other_shell_config = os.path.join(self.config_home, "quickshell")
        os.makedirs(other_shell_config)
        with open(os.path.join(other_shell_config, "config.qml"), "w") as fh:
            fh.write("// other install")

        proc = self.run_installer("uninstall")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertFalse(os.path.exists(self.releases_dir))
        self.assertFalse(os.path.exists(os.path.join(self.data_root, "current")))
        self.assertFalse(os.path.exists(self.launcher_path))
        self.assertTrue(os.path.isfile(unrelated), "unrelated file was deleted")
        self.assertTrue(
            os.path.isfile(os.path.join(self.user_config_dir, "dock_config.json")),
            "user configuration was deleted",
        )
        self.assertTrue(
            os.path.isfile(os.path.join(other_shell_config, "config.qml")),
            "unrelated quickshell config was deleted",
        )
        self.assertIn("preserved", proc.stdout)

    def test_uninstall_dry_run_changes_nothing(self):
        self.install()
        proc = self.run_installer("uninstall", "--dry-run")
        self.assertEqual(proc.returncode, 0)
        self.assertInstalled("v1")

    def test_uninstall_without_install_fails(self):
        proc = self.run_installer("uninstall")
        self.assertNotEqual(proc.returncode, 0)

    def test_uninstall_refuses_unowned_launcher(self):
        """If the launcher location was replaced by a foreign file after
        install, uninstall refuses to delete it (and says so)."""
        self.install()
        with open(self.launcher_path, "w") as fh:
            fh.write("#!/bin/sh\n# user's own launcher, no arena tag\n")
        proc = self.run_installer("uninstall")
        self.assertNotEqual(proc.returncode, 0)
        self.assertTrue(os.path.isfile(self.launcher_path), "foreign launcher deleted")
        self.assertIn("refusing", proc.stdout)

    def test_uninstall_preserves_autostart_when_foreign(self):
        self.install(extra=("--enable-autostart",))
        autostart = os.path.join(
            self.config_home, "autostart", "quickshell-kde.desktop"
        )
        with open(autostart, "w") as fh:
            fh.write("[Desktop Entry]\nType=Application\nName=users own\n")
        proc = self.run_installer("uninstall")
        self.assertNotEqual(proc.returncode, 0)
        self.assertTrue(os.path.isfile(autostart))


class TestPreExistingUserFiles(InstallerHarness):
    def test_install_refuses_to_overwrite_foreign_launcher(self):
        os.makedirs(os.path.dirname(self.launcher_path), exist_ok=True)
        with open(self.launcher_path, "w") as fh:
            fh.write("#!/bin/sh\nexec my-own-thing\n")
        os.chmod(self.launcher_path, 0o755)
        proc = self.run_installer("install", self.source, "--version", "v1")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("refusing", proc.stderr)
        with open(self.launcher_path) as fh:
            self.assertEqual(fh.read(), "#!/bin/sh\nexec my-own-thing\n")

    def test_install_refuses_foreign_autostart_entry(self):
        autostart_dir = os.path.join(self.config_home, "autostart")
        os.makedirs(autostart_dir)
        autostart = os.path.join(autostart_dir, "quickshell-kde.desktop")
        with open(autostart, "w") as fh:
            fh.write("[Desktop Entry]\nType=Application\nName=mine\n")
        proc = self.run_installer(
            "install", self.source, "--version", "v1", "--enable-autostart"
        )
        self.assertNotEqual(proc.returncode, 0)
        with open(autostart) as fh:
            self.assertIn("mine", fh.read())


class TestUnsafeInputs(InstallerHarness):
    def test_home_root_rejected(self):
        proc = subprocess.run(
            [sys.executable, INSTALLER, "list"],
            env={**self.env(), "HOME": "/"},
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("refusing", proc.stderr)

    def test_relative_xdg_data_home_rejected(self):
        proc = subprocess.run(
            [sys.executable, INSTALLER, "list"],
            env={**self.env(), "XDG_DATA_HOME": "relative/path"},
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )
        self.assertEqual(proc.returncode, 2)

    def test_version_slash_rejected(self):
        proc = self.run_installer("install", self.source, "--version", "a/b")
        self.assertEqual(proc.returncode, 2)
        self.assertFalse(os.path.exists(self.data_root))

    def test_version_dotdot_rejected(self):
        proc = self.run_installer("install", self.source, "--version", "..")
        self.assertEqual(proc.returncode, 2)

    def test_source_inside_installation_rejected(self):
        self.install(version="v1")
        proc = self.run_installer(
            "install", self.release("v1"), "--version", "v2"
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("inside the installation root", proc.stderr)

    def test_data_root_symlink_escape_rejected(self):
        victim = os.path.join(self._tmp_parent, "escape-target")
        os.makedirs(victim)
        os.makedirs(self.data_home)
        os.symlink(victim, self.data_root)
        proc = self.run_installer("install", self.source, "--version", "v1")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("symlink", proc.stderr)
        self.assertEqual(os.listdir(victim), [])

    def test_source_with_symlink_rejected(self):
        with open(os.path.join(self.source, "innocent.txt"), "w") as fh:
            fh.write("x")
        os.symlink(
            os.path.join(self.source, "innocent.txt"),
            os.path.join(self.source, "alias.qml"),
        )
        proc = self.run_installer("install", self.source, "--version", "v1")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("symlink", proc.stderr)

    def test_source_with_symlink_escape_rejected(self):
        os.symlink("/etc/passwd", os.path.join(self.source, "evil.qml"))
        proc = self.run_installer("install", self.source, "--version", "v1")
        self.assertEqual(proc.returncode, 2)

    def test_release_marker_required_for_deletion(self):
        """A release directory whose marker was tampered with is not
        deleted by uninstall."""
        self.install(version="v1")
        os.unlink(os.path.join(self.release("v1"), ".quickshell-kde-release"))
        proc = self.run_installer("uninstall")
        self.assertNotEqual(proc.returncode, 0)
        self.assertTrue(os.path.isdir(self.release("v1")), "tampered release deleted")


class TestArchives(InstallerHarness):
    def make_archive(self, members, mode="w:gz"):
        archive = os.path.join(self._tmp_parent, "archive.tar.gz")
        with tarfile.open(archive, mode) as tf:
            for name, data in members:
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
        return archive

    def test_corrupt_archive_rejected(self):
        archive = os.path.join(self._tmp_parent, "garbage.tar.gz")
        with open(archive, "wb") as fh:
            fh.write(b"this is not a tar archive at all, just noise")
        proc = self.run_installer("install", archive, "--version", "v1")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("cannot read archive", proc.stderr)
        self.assertFalse(os.path.exists(self.data_root))

    def test_truncated_archive_rejected(self):
        archive = os.path.join(self._tmp_parent, "release.tar.gz")
        with tarfile.open(archive, "w:gz") as tf:
            payload = b"// shell" * 64
            info = tarfile.TarInfo("shell.qml")
            info.size = len(payload)
            tf.addfile(info, io.BytesIO(payload))
        with open(archive, "rb") as fh:
            raw = fh.read()
        with open(archive, "wb") as fh:
            fh.write(raw[: len(raw) // 2])
        proc = self.run_installer("install", archive, "--version", "v1")
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(os.path.exists(self.data_root))

    def test_archive_with_symlink_member_rejected(self):
        archive = os.path.join(self._tmp_parent, "evil.tar.gz")
        with tarfile.open(archive, "w:gz") as tf:
            info = tarfile.TarInfo("evil.qml")
            info.type = tarfile.SYMTYPE
            info.linkname = "/etc/passwd"
            tf.addfile(info)
            payload = b"// shell"
            info2 = tarfile.TarInfo("shell.qml")
            info2.size = len(payload)
            tf.addfile(info2, io.BytesIO(payload))
        proc = self.run_installer("install", archive, "--version", "v1")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("symlink", proc.stderr)

    def test_archive_with_path_traversal_rejected(self):
        archive = os.path.join(self._tmp_parent, "traverse.tar.gz")
        with tarfile.open(archive, "w:gz") as tf:
            payload = b"pwned"
            info = tarfile.TarInfo("../escape.txt")
            info.size = len(payload)
            tf.addfile(info, io.BytesIO(payload))
        proc = self.run_installer("install", archive, "--version", "v1")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("escapes", proc.stderr)
        self.assertFalse(
            os.path.exists(os.path.join(self._tmp_parent, "escape.txt")),
            "traversal file was written outside the extraction dir",
        )

    def test_non_archive_file_rejected(self):
        plain = os.path.join(self._tmp_parent, "not-an-archive.txt")
        with open(plain, "w") as fh:
            fh.write("hello")
        proc = self.run_installer("install", plain, "--version", "v1")
        self.assertNotEqual(proc.returncode, 0)


class TestInterruptedInstallation(InstallerHarness):
    def test_stale_staging_leftovers_are_ignored_and_cleaned(self):
        """Simulate an interrupted run: partial staging dir and a
        half-swapped current symlink. The previous release stays intact
        and the next install cleans everything up."""
        self.install(version="v1")

        staging = os.path.join(self.releases_dir, ".staging-interrupted")
        os.makedirs(os.path.join(staging, "modules"))
        with open(os.path.join(staging, "shell.qml"), "w") as fh:
            fh.write("// partial copy")
        tmp_link = os.path.join(self.data_root, "current.tmp-deadbeef")
        os.symlink("releases/v2", tmp_link)

        # The active release is untouched by the leftover state.
        self.assertInstalled("v1")

        src2 = self.make_source("after recovery")
        proc = self.run_installer("update", src2, "--version", "v2")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertInstalled("v2", marker="after recovery")
        self.assertFalse(os.path.exists(staging), "stale staging not cleaned")
        self.assertFalse(os.path.exists(tmp_link), "stale tmp symlink not cleaned")

    def test_orphan_release_not_in_manifest_is_detected(self):
        self.install(version="v1")
        orphan = self.release("orphan")
        os.makedirs(orphan)
        with open(os.path.join(orphan, "shell.qml"), "w") as fh:
            fh.write("// orphan")
        proc = self.run_installer("doctor")
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("orphan", proc.stdout)
        # Uninstall must not remove the orphan; it is not owned. The
        # uninstall itself still succeeds (exit 0) and leaves it behind.
        proc = self.run_installer("uninstall")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(os.path.isdir(orphan), "orphan release deleted by uninstall")

    def test_interrupted_between_rename_and_symlink(self):
        """A release dir on disk without an activated symlink: doctor
        flags the inconsistency, install takes the version over."""
        self.install(version="v1")
        # Simulate: v2 was renamed into place but the process died
        # before the symlink swap.
        v2 = self.release("v2")
        shutil.copytree(self.release("v1"), v2)
        with open(os.path.join(v2, ".quickshell-kde-release")) as fh:
            marker = json.load(fh)
        marker["version"] = "v2"
        with open(os.path.join(v2, ".quickshell-kde-release"), "w") as fh:
            json.dump(marker, fh)
        self.assertEqual(self.current_target(), "releases/v1")

        proc = self.run_installer("doctor")
        self.assertIn("not in the manifest", proc.stdout)

        # Installing v2 again must take the orphan over safely.
        src2 = self.make_source("recovered v2")
        proc = self.run_installer("install", src2, "--version", "v2")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertInstalled("v2", marker="recovered v2")
        manifest = self.manifest()
        self.assertEqual(manifest["previous"], "v1")

    def test_lock_prevents_concurrent_installs(self):
        self.install(version="v1")
        lock_path = os.path.join(self.data_root, ".lock")
        fd = os.open(lock_path, os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            src2 = self.make_source("concurrent")
            proc = self.run_installer("update", src2, "--version", "v2")
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("already running", proc.stderr)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)


class TestPermissionFailures(InstallerHarness):
    def setUp(self):
        super().setUp()
        self._stashed_modes = []

    def tearDown(self):
        for path, mode in self._stashed_modes:
            try:
                os.chmod(path, mode)
            except OSError:
                pass
        super().tearDown()

    def stash_mode(self, path):
        self._stashed_modes.append((path, os.stat(path).st_mode & 0o777))

    def test_unwritable_data_root_reports_actionable_error(self):
        os.makedirs(self.data_home)
        self.stash_mode(self.data_home)
        os.chmod(self.data_home, 0o555)
        try:
            proc = self.run_installer("install", self.source, "--version", "v1")
            self.assertNotEqual(proc.returncode, 0)
            self.assertRegex(proc.stderr, r"cannot (create|acquire|write)")
        finally:
            os.chmod(self.data_home, 0o755)

    def test_unwritable_releases_dir_fails_before_activation(self):
        self.install(version="v1")
        self.stash_mode(self.releases_dir)
        os.chmod(self.releases_dir, 0o555)
        try:
            src2 = self.make_source("blocked update")
            proc = self.run_installer("update", src2, "--version", "v2")
            self.assertNotEqual(proc.returncode, 0)
        finally:
            os.chmod(self.releases_dir, 0o755)
        # The previous release is intact and still active.
        self.assertInstalled("v1")
        self.assertFalse(os.path.exists(self.release("v2")))


class TestDoctor(InstallerHarness):
    def test_doctor_healthy_with_stub_tools(self):
        self.install()
        proc = self.run_installer("doctor")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("all checks passed", proc.stdout)
        self.assertIn("no staging leftovers", proc.stdout)

    def test_doctor_reports_missing_required_tools(self):
        empty_bin = os.path.join(self._tmp_parent, "emptybin")
        os.makedirs(empty_bin)
        self.install()
        proc = self.run_installer("doctor", path=empty_bin)
        self.assertEqual(proc.returncode, 3)
        for tool in ("quickshell", "qdbus6", "kdotool", "wpctl"):
            self.assertIn(tool, proc.stdout)
        self.assertIn("install:", proc.stdout)  # actionable hint

    def test_doctor_reports_dangling_current(self):
        self.install(version="v1")
        shutil.rmtree(self.release("v1"))
        proc = self.run_installer("doctor")
        self.assertEqual(proc.returncode, 3)
        self.assertIn("BROKEN", proc.stdout)

    def test_doctor_detects_missing_shell_binary(self):
        # quickshell missing, everything else present.
        os.unlink(os.path.join(self.bin_dir, "quickshell"))
        proc = self.run_installer("doctor")
        self.assertEqual(proc.returncode, 3)
        self.assertIn("quickshell", proc.stdout)

    def test_list_reports_installation(self):
        self.install(version="v1")
        proc = self.run_installer("list")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("v1", proc.stdout)
        self.assertIn("current", proc.stdout)


class TestSpacesEverywhere(InstallerHarness):
    """The harness already puts spaces in HOME; this class adds spaces
    to the source directory and release versions as well."""

    def test_spaces_in_source_and_version(self):
        src = os.path.join(self._tmp_parent, "source dir with spaces")
        os.makedirs(src)
        with open(os.path.join(src, "shell.qml"), "w") as fh:
            fh.write("// spaced")
        proc = self.run_installer(
            "install", src, "--version", "v1-spaced.2026"
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertInstalled("v1-spaced.2026")
        with open(self.launcher_path) as fh:
            content = fh.read()
        self.assertIn(f"'{self.data_root}'", content)
        # The launcher must be valid sh even with spaces everywhere.
        check = subprocess.run(
            ["sh", "-n", self.launcher_path], capture_output=True, text=True
        )
        self.assertEqual(check.returncode, 0, check.stderr)


if __name__ == "__main__":
    unittest.main()
