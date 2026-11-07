#!/usr/bin/env python3
"""quickshell-kde arena installer — secure transactional per-user installer.

Installs a frozen release of quickshell-kde from a local checkout or a
tar archive into versioned directories under
``$XDG_DATA_HOME/quickshell-kde/releases/<version>/`` and maintains an
atomic ``current`` symlink plus a small launcher at
``~/.local/bin/quickshell-kde``.

Design rules (see installer/README.md for the full contract):

* Transactional: content is staged in ``releases/.staging-*`` and only
  activated with atomic renames. The symlink swap is the commit point;
  any failure before it rolls the new release back and leaves the
  previously working release intact.
* Ownership-tracked: a JSON manifest records every path the installer
  owns. Uninstall removes only those paths, after re-validating each
  one. User configuration (``~/.config/quickshell-kde``) is never
  touched.
* No privilege, no network, no remote scripts. Missing dependencies are
  reported with actionable diagnostics (``doctor``).

Python 3.9+, standard library only.
"""

from __future__ import annotations

import argparse
import errno
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid

APP_NAME = "quickshell-kde"
SCHEMA_VERSION = 1
RELEASE_MARKER = ".quickshell-kde-release"
MANIFEST_NAME = "manifest.json"
LOCK_NAME = ".lock"
STAGING_PREFIX = ".staging-"
TRASH_DIR = ".trash"
CURRENT_NAME = "current"
LAUNCHER_NAME = "quickshell-kde"
AUTOSTART_NAME = "quickshell-kde.desktop"
INSTALLER_TAG = "arena-installer-v1"

# Directories/files never copied from a source checkout (VCS and
# developer-session noise; none of them are needed at runtime).
SOURCE_EXCLUDES = {".git", "__pycache__", ".rig"}

VERSION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,63}")

# Exit codes
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_SAFETY = 2
EXIT_DOCTOR = 3


class InstallerError(Exception):
    """Fatal, user-facing error. `code` is the process exit status."""

    def __init__(self, message: str, code: int = EXIT_ERROR):
        super().__init__(message)
        self.code = code


class SafetyError(InstallerError):
    """A request was rejected by a safety check."""

    def __init__(self, message: str):
        super().__init__(message, code=EXIT_SAFETY)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


class Paths:
    """Resolved, validated installation paths for one environment."""

    def __init__(self, env: dict):
        home = env.get("HOME") or ""
        if not home:
            raise InstallerError("HOME is not set; cannot install per-user.")
        home = os.path.abspath(home)
        if home == os.path.abspath(os.sep):
            raise SafetyError("HOME points at the filesystem root; refusing.")

        data_home = env.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share")
        if not os.path.isabs(data_home):
            raise SafetyError(
                f"XDG_DATA_HOME={data_home!r} is not an absolute path; refusing."
            )
        data_home = os.path.abspath(data_home)
        if data_home == os.path.abspath(os.sep):
            raise SafetyError("XDG_DATA_HOME points at the filesystem root; refusing.")

        self.home = home
        self.data_home = data_home
        self.data_root = os.path.join(data_home, APP_NAME)
        self.releases_dir = os.path.join(self.data_root, "releases")
        self.trash_dir = os.path.join(self.data_root, TRASH_DIR)
        self.current = os.path.join(self.data_root, CURRENT_NAME)
        self.manifest = os.path.join(self.data_root, MANIFEST_NAME)
        self.lock = os.path.join(self.data_root, LOCK_NAME)
        self.bin_dir = os.path.join(home, ".local", "bin")
        self.launcher = os.path.join(self.bin_dir, LAUNCHER_NAME)

        config_home = env.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")
        if not os.path.isabs(config_home):
            config_home = os.path.join(home, ".config")
        self.config_home = os.path.abspath(config_home)
        self.user_config_dir = os.path.join(self.config_home, APP_NAME)
        self.autostart_dir = os.path.join(self.config_home, "autostart")
        self.autostart = os.path.join(self.autostart_dir, AUTOSTART_NAME)

        if self.data_root in (home, data_home):
            raise SafetyError(
                f"installation root {self.data_root} collides with HOME or "
                "XDG_DATA_HOME; refusing."
            )
        self._reject_managed_symlinks()

    def _reject_managed_symlinks(self) -> None:
        """The managed tree must not be reachable through symlinks placed
        at the paths we own: that is how a deletion could escape the
        installation root. `current` is exempt — it is our own symlink —
        unless it points somewhere outside releases/."""
        for path in (self.data_root, self.releases_dir):
            if os.path.islink(path):
                raise SafetyError(
                    f"{path} is a symlink; the installer refuses to manage "
                    "paths it does not fully own. Remove the symlink manually "
                    "if it was not created by the arena installer."
                )
        if os.path.islink(self.current):
            target = os.readlink(self.current)
            if not target.startswith("releases" + os.sep):
                raise SafetyError(
                    f"{self.current} is a symlink to {target!r}, which is not "
                    "an installer-managed release; refusing."
                )

    def release_path(self, version: str) -> str:
        return os.path.join(self.releases_dir, version)

    def source_inside_installation(self, source_dir: str) -> bool:
        root = os.path.realpath(self.data_root)
        real = os.path.realpath(source_dir)
        return real == root or real.startswith(root + os.sep)


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


def new_manifest() -> dict:
    return {
        "schema": SCHEMA_VERSION,
        "app": APP_NAME,
        "installer": INSTALLER_TAG,
        "current": None,
        "previous": None,
        "releases": {},
        "owned": {},
    }


def load_manifest(paths: Paths) -> dict:
    try:
        with open(paths.manifest, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        raise InstallerError(
            f"no installation manifest at {paths.manifest}; nothing is "
            "installed (or the installation is corrupt). Run 'install' first."
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallerError(f"cannot read manifest {paths.manifest}: {exc}")
    if not isinstance(data, dict) or data.get("app") != APP_NAME:
        raise InstallerError(
            f"{paths.manifest} is not a quickshell-kde installer manifest."
        )
    if data.get("schema") != SCHEMA_VERSION:
        raise InstallerError(
            f"manifest schema {data.get('schema')!r} is not supported "
            f"(expected {SCHEMA_VERSION})."
        )
    data.setdefault("releases", {})
    data.setdefault("owned", {})
    return data


def save_manifest(paths: Paths, manifest: dict) -> None:
    manifest["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    tmp = f"{paths.manifest}.tmp-{uuid.uuid4().hex[:8]}"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, paths.manifest)
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise InstallerError(f"cannot write manifest {paths.manifest}: {exc}")


# ---------------------------------------------------------------------------
# Locking
# ---------------------------------------------------------------------------


class InstallerLock:
    """Exclusive, advisory whole-installation lock (flock)."""

    def __init__(self, paths: Paths):
        self.paths = paths
        self.fd = None

    def __enter__(self) -> "InstallerLock":
        try:
            os.makedirs(self.paths.data_root, exist_ok=True)
        except OSError as exc:
            raise InstallerError(
                f"cannot create installation root {self.paths.data_root}: {exc}"
            )
        try:
            self.fd = os.open(self.paths.lock, os.O_CREAT | os.O_RDWR, 0o600)
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if self.fd is not None:
                os.close(self.fd)
                self.fd = None
            if exc.errno in (errno.EACCES, errno.EAGAIN):
                raise InstallerError(
                    "another arena installer process is already running "
                    f"(lock held on {self.paths.lock})."
                )
            raise InstallerError(f"cannot acquire installer lock: {exc}")
        return self

    def __exit__(self, *exc) -> None:
        if self.fd is not None:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_UN)
            finally:
                os.close(self.fd)
                self.fd = None


# ---------------------------------------------------------------------------
# Source handling
# ---------------------------------------------------------------------------


def sanitize_version(version: str) -> str:
    if not VERSION_RE.fullmatch(version):
        raise SafetyError(
            f"invalid version {version!r}: must match "
            "[A-Za-z0-9][A-Za-z0-9._+-]{0,63} (no slashes, no leading dot)."
        )
    return version


def detect_version(source_dir: str, explicit: "str | None") -> str:
    """Version precedence: --version, source release.json, git describe,
    timestamped fallback."""
    if explicit:
        return sanitize_version(explicit)
    release_json = os.path.join(source_dir, "release.json")
    if os.path.isfile(release_json) and not os.path.islink(release_json):
        try:
            with open(release_json, "r", encoding="utf-8") as fh:
                value = json.load(fh).get("version")
            if isinstance(value, str) and value:
                return sanitize_version(value)
        except (OSError, json.JSONDecodeError):
            pass
    if os.path.exists(os.path.join(source_dir, ".git")):
        try:
            proc = subprocess.run(
                ["git", "-C", source_dir, "describe", "--tags", "--always", "--dirty"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if proc.returncode == 0:
                candidate = proc.stdout.strip()
                if candidate:
                    return sanitize_version(candidate)
        except (OSError, subprocess.SubprocessError):
            pass
    return time.strftime("v%Y%m%d-%H%M%S")


def scan_source(source_dir: str) -> list:
    """Walk the source tree and return [(abs_source_path, rel_path)].

    Rejects symlinks and special files anywhere in the tree, and skips
    the documented exclusion set (.git, __pycache__, .rig).
    """
    source_dir = os.path.realpath(source_dir)
    if not os.path.isdir(source_dir):
        raise InstallerError(f"source {source_dir} is not a directory.")
    files = []
    for root, dirs, names in os.walk(source_dir, followlinks=False):
        for name in list(dirs):
            full = os.path.join(root, name)
            if name in SOURCE_EXCLUDES:
                dirs.remove(name)
                continue
            if os.path.islink(full):
                raise SafetyError(
                    f"source contains symlink {os.path.relpath(full, source_dir)!r}; "
                    "symlinks are rejected to prevent path escapes."
                )
        for name in names:
            if name in SOURCE_EXCLUDES:
                continue
            full = os.path.join(root, name)
            if os.path.islink(full):
                raise SafetyError(
                    f"source contains symlink {os.path.relpath(full, source_dir)!r}; "
                    "symlinks are rejected to prevent path escapes."
                )
            if not os.path.isfile(full):
                raise SafetyError(
                    f"source contains special file "
                    f"{os.path.relpath(full, source_dir)!r} "
                    "(device/socket/fifo); refusing."
                )
            files.append((full, os.path.relpath(full, source_dir)))
    return files


def extract_archive(archive_path: str, dest: str) -> str:
    """Validate and extract a tar archive into a fresh empty directory.

    Every member must be a regular file or a directory with a relative,
    non-escaping path. Symlinks, hardlinks and special files are rejected
    before anything is written. Returns the directory that contains the
    release (descending into a single wrapping directory if present).
    """
    dest = os.path.realpath(dest)
    if os.listdir(dest):
        raise SafetyError(f"extraction directory {dest} is not empty.")
    try:
        with tarfile.open(archive_path, "r:*") as tf:
            for member in tf.getmembers():
                if not (member.isreg() or member.isdir()):
                    raise SafetyError(
                        f"archive member {member.name!r} is a symlink or "
                        "special file; refusing."
                    )
                parts = member.name.split("/")
                if member.name.startswith("/") or ".." in parts or not parts[0]:
                    raise SafetyError(
                        f"archive member {member.name!r} escapes the archive "
                        "root; refusing."
                    )
            try:
                tf.extractall(dest, filter="data")
            except TypeError:  # Python < 3.12: manual validation above applies
                tf.extractall(dest)
    except (tarfile.TarError, EOFError, OSError) as exc:
        raise InstallerError(
            f"cannot read archive {archive_path}: {exc}. The archive is "
            "corrupt or not a tar file."
        )
    entries = [e for e in os.listdir(dest) if e != "."]
    if len(entries) == 1:
        only = os.path.join(dest, entries[0])
        if os.path.isdir(only) and not os.path.islink(only):
            return only
    return dest


def resolve_source(source: str) -> "tuple[str, str | None]":
    """Turn a CLI source argument into (source_dir, cleanup_dir|None).

    Archives are extracted into a private system temp directory that the
    caller must remove; it never lands inside the managed tree."""
    if not os.path.exists(source):
        raise InstallerError(f"source {source} does not exist.")
    if os.path.islink(source):
        raise SafetyError(f"source {source} is a symlink; refusing.")
    if os.path.isdir(source):
        return os.path.realpath(source), None
    if os.path.isfile(source):
        lower = os.path.basename(source).lower()
        if lower.endswith((".tar", ".tar.gz", ".tgz", ".tar.xz", ".tar.bz2")):
            dest = tempfile.mkdtemp(prefix="qskde-archive-")
            return extract_archive(source, dest), dest
        raise InstallerError(
            f"source {source} is a file but not a tar archive "
            "(expected .tar / .tar.gz / .tgz / .tar.xz / .tar.bz2)."
        )
    raise InstallerError(f"source {source} is not a file or directory.")


def find_shell_root(source_dir: str) -> str:
    """Return the directory that contains shell.qml, descending into a
    single wrapping directory if needed."""
    if os.path.isfile(os.path.join(source_dir, "shell.qml")):
        return source_dir
    entries = [e for e in os.listdir(source_dir) if not e.startswith(".")]
    if len(entries) == 1:
        only = os.path.join(source_dir, entries[0])
        if os.path.isdir(only) and not os.path.islink(only):
            if os.path.isfile(os.path.join(only, "shell.qml")):
                return only
    raise InstallerError(
        f"{source_dir} does not contain shell.qml (looked at the root and "
        "inside a single wrapping directory); not a quickshell-kde release."
    )


# ---------------------------------------------------------------------------
# Release marker / integrity
# ---------------------------------------------------------------------------


def write_release_marker(release_dir: str, version: str) -> None:
    marker = os.path.join(release_dir, RELEASE_MARKER)
    payload = {
        "schema": SCHEMA_VERSION,
        "app": APP_NAME,
        "version": version,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "installer": INSTALLER_TAG,
    }
    with open(marker, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")


def read_release_marker(release_dir: str, version: "str | None" = None) -> dict:
    marker = os.path.join(release_dir, RELEASE_MARKER)
    if os.path.islink(marker) or not os.path.isfile(marker):
        raise InstallerError(
            f"{release_dir} has no valid {RELEASE_MARKER} marker; refusing "
            "to treat it as an installer-owned release."
        )
    try:
        with open(marker, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallerError(f"cannot read release marker in {release_dir}: {exc}")
    if data.get("app") != APP_NAME or data.get("schema") != SCHEMA_VERSION:
        raise InstallerError(
            f"release marker in {release_dir} is not owned by this installer."
        )
    if version is not None and data.get("version") != version:
        raise InstallerError(
            f"release marker in {release_dir} names version "
            f"{data.get('version')!r}, expected {version!r}; refusing."
        )
    return data


# ---------------------------------------------------------------------------
# Deletion safety
# ---------------------------------------------------------------------------


def read_head(path: str, limit: int = 4096) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read(limit)
    except OSError:
        return ""


def safe_rmtree(path: str, expect_parent: str, version: "str | None" = None) -> None:
    """Delete a directory tree only when it is a real directory strictly
    inside expect_parent and carries a valid release marker."""
    path = os.path.abspath(path)
    parent = os.path.abspath(expect_parent)
    if path == parent or not path.startswith(parent + os.sep):
        raise SafetyError(f"refusing to delete {path}: it is not inside {parent}.")
    if os.path.islink(path):
        raise SafetyError(f"refusing to delete {path}: it is a symlink.")
    if not os.path.isdir(path):
        raise SafetyError(f"refusing to delete {path}: it is not a directory.")
    read_release_marker(path, version)
    shutil.rmtree(path)


def safe_rmfile(path: str, expect_parent: str) -> None:
    """Delete a file only when it is a regular, non-symlink file strictly
    inside expect_parent whose content carries our installer tag."""
    path = os.path.abspath(path)
    parent = os.path.abspath(expect_parent)
    if path == parent or not path.startswith(parent + os.sep):
        raise SafetyError(f"refusing to delete {path}: it is not inside {parent}.")
    if os.path.islink(path):
        raise SafetyError(f"refusing to delete {path}: it is a symlink.")
    if not os.path.isfile(path):
        raise SafetyError(f"refusing to delete {path}: it is not a regular file.")
    if INSTALLER_TAG not in read_head(path):
        raise SafetyError(
            f"refusing to delete {path}: it does not look like a file "
            "generated by the arena installer."
        )
    os.unlink(path)


# ---------------------------------------------------------------------------
# Launcher / autostart
# ---------------------------------------------------------------------------

LAUNCHER_TEMPLATE = """#!/bin/sh
# Generated by quickshell-kde {tag}. Do not edit; reinstall or uninstall
# with the arena installer instead.
QS_KDE_ROOT={data_root}
if [ ! -f "$QS_KDE_ROOT/current/shell.qml" ]; then
    echo "quickshell-kde: no active release under $QS_KDE_ROOT/current" >&2
    echo "quickshell-kde: (re)install a release, or run the installer's" >&2
    echo "  doctor command for diagnostics." >&2
    exit 1
fi
if [ "$1" = "kill" ]; then
    exec quickshell kill
fi
exec quickshell -p "$QS_KDE_ROOT/current/shell.qml" "$@"
"""

AUTOSTART_TEMPLATE = """[Desktop Entry]
# Managed by quickshell-kde {tag}; remove via the installer's uninstall.
Type=Application
Name=quickshell-kde
Comment=Quickshell KDE desktop shell (arena-installer managed)
Exec="{launcher}"
Terminal=false
"""


def sh_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def refuse_foreign_target(path: str) -> None:
    """Refuse to replace an existing path that is not ours."""
    if os.path.islink(path):
        raise SafetyError(
            f"{path} is a symlink; refusing to replace it. Remove it "
            "manually if you want the arena-installer file there."
        )
    if os.path.exists(path) and INSTALLER_TAG not in read_head(path):
        raise SafetyError(
            f"{path} already exists and was not created by the arena "
            "installer; refusing to overwrite it. Move it aside first if "
            "you want the arena-installer file there."
        )


def atomic_write_text(path: str, content: str, mode: int) -> None:
    tmp = f"{path}.tmp-{uuid.uuid4().hex[:8]}"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise InstallerError(f"cannot write {path}: {exc}")


def write_launcher(paths: Paths) -> None:
    refuse_foreign_target(paths.launcher)
    content = LAUNCHER_TEMPLATE.format(
        tag=INSTALLER_TAG, data_root=sh_quote(paths.data_root)
    )
    try:
        os.makedirs(paths.bin_dir, exist_ok=True)
    except OSError as exc:
        raise InstallerError(f"cannot create {paths.bin_dir}: {exc}")
    atomic_write_text(paths.launcher, content, 0o755)


def write_autostart(paths: Paths) -> None:
    refuse_foreign_target(paths.autostart)
    try:
        os.makedirs(paths.autostart_dir, exist_ok=True)
    except OSError as exc:
        raise InstallerError(f"cannot create {paths.autostart_dir}: {exc}")
    content = AUTOSTART_TEMPLATE.format(
        tag=INSTALLER_TAG, launcher=paths.launcher.replace('"', '\\"')
    )
    atomic_write_text(paths.autostart, content, 0o644)


def remove_if_ours(path: str) -> None:
    """Best-effort removal of a file we wrote during a failed run (only
    when it carries our tag and is not a symlink)."""
    try:
        if os.path.isfile(path) and not os.path.islink(path):
            if INSTALLER_TAG in read_head(path):
                os.unlink(path)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Staging / activation
# ---------------------------------------------------------------------------


def clean_stale_staging(paths: Paths) -> list:
    """Remove leftovers from interrupted runs. Only safe under the
    installer lock: .staging-* directories under releases/ and
    half-swapped current.tmp-* symlinks under the data root."""
    removed = []
    if os.path.isdir(paths.releases_dir):
        for name in os.listdir(paths.releases_dir):
            if not name.startswith(STAGING_PREFIX):
                continue
            full = os.path.join(paths.releases_dir, name)
            if os.path.islink(full):
                print(f"warning: ignoring symlink {full}; remove it manually")
                continue
            if os.path.isdir(full):
                shutil.rmtree(full, ignore_errors=True)
                removed.append(full)
    if os.path.isdir(paths.data_root):
        for name in os.listdir(paths.data_root):
            if name.startswith(CURRENT_NAME + ".tmp-"):
                full = os.path.join(paths.data_root, name)
                if os.path.islink(full):
                    os.unlink(full)
                    removed.append(full)
    return removed


def stage_release(paths: Paths, files: list, version: str) -> str:
    """Copy the scanned source into a fresh staging directory and verify
    the copy before anything is activated."""
    staging = os.path.join(
        paths.releases_dir, f"{STAGING_PREFIX}{uuid.uuid4().hex[:12]}"
    )
    try:
        os.makedirs(staging)
        for src, rel in files:
            dest = os.path.join(staging, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(src, dest)
        write_release_marker(staging, version)
        staged = scan_source(staging)
        if len(staged) != len(files) + 1:  # +1: the marker we just wrote
            raise InstallerError(
                "staged tree failed verification: "
                f"expected {len(files) + 1} files, found {len(staged)}."
            )
        if not os.path.isfile(os.path.join(staging, "shell.qml")):
            raise InstallerError("staged tree is missing shell.qml.")
        read_release_marker(staging, version)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return staging


def activate(paths: Paths, manifest: dict, staging: str, version: str) -> None:
    """Atomically activate a staged release. The symlink swap at the end
    is the commit point; anything failing before it rolls the new
    release back and leaves the previous release untouched."""
    target = paths.release_path(version)
    trash_target = None
    moved_old = False
    try:
        os.makedirs(paths.trash_dir, exist_ok=True)
        if os.path.lexists(target):
            # Re-install of an existing version: move the old tree aside
            # so the rename below stays atomic within one directory.
            trash_target = os.path.join(
                paths.trash_dir, f"{version}-{uuid.uuid4().hex[:8]}"
            )
            os.rename(target, trash_target)
            moved_old = True
        os.rename(staging, target)
    except OSError as exc:
        if moved_old and trash_target and not os.path.lexists(target):
            try:
                os.rename(trash_target, target)
            except OSError:
                pass
        shutil.rmtree(staging, ignore_errors=True)
        raise InstallerError(f"cannot activate release {version}: {exc}")

    # Commit point: swap the current symlink atomically.
    old_current = manifest.get("current")
    tmp_link = f"{paths.current}.tmp-{uuid.uuid4().hex[:8]}"
    try:
        os.symlink(os.path.join("releases", version), tmp_link)
        os.replace(tmp_link, paths.current)
    except OSError as exc:
        rollback_dir = os.path.join(paths.trash_dir, uuid.uuid4().hex[:8])
        try:
            os.rename(target, rollback_dir)
            shutil.rmtree(rollback_dir, ignore_errors=True)
        except OSError:
            pass
        if moved_old and trash_target:
            try:
                os.rename(trash_target, target)
            except OSError:
                pass
        raise InstallerError(f"cannot activate symlink for {version}: {exc}")

    if old_current != version:
        manifest["previous"] = old_current
    manifest["current"] = version
    manifest["releases"][version] = {
        "activated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "files": len(files_count(target)),
    }
    manifest["owned"][target] = {"kind": "release-dir", "version": version}
    if trash_target:
        shutil.rmtree(trash_target, ignore_errors=True)


def files_count(release_dir: str) -> list:
    """All entries (files and dirs) directly inside a release dir."""
    try:
        return os.listdir(release_dir)
    except OSError:
        return []


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def ensure_dirs(paths: Paths) -> None:
    for d in (paths.data_root, paths.releases_dir):
        if os.path.islink(d):
            raise SafetyError(f"{d} is a symlink; refusing to manage it.")
        os.makedirs(d, exist_ok=True)
    if os.path.exists(paths.current) and not os.path.islink(paths.current):
        raise SafetyError(
            f"{paths.current} exists but is not a symlink; refusing to "
            "manage this installation."
        )


def cmd_install(args, paths: Paths) -> int:
    # Phase 1: read-only validation. Nothing in the managed tree is
    # created or modified here, so failed validation (and --dry-run)
    # leave no trace at all.
    source_dir, cleanup_dir = resolve_source(args.source)
    try:
        if paths.source_inside_installation(source_dir):
            raise SafetyError(
                f"source {source_dir} is inside the installation root "
                f"{paths.data_root}; refusing."
            )
        shell_root = find_shell_root(source_dir)
        version = detect_version(shell_root, args.version)
        files = scan_source(shell_root)

        if args.command == "update" and not os.path.exists(paths.manifest):
            raise InstallerError(
                "update requires an existing installation; "
                "use 'install' first."
            )

        print(f"source:      {shell_root}")
        print(f"files:       {len(files)}")
        print(f"version:     {version}")
        print(f"target:      {paths.release_path(version)}")
        print(
            f"autostart:   "
            f"{paths.autostart if args.enable_autostart else 'disabled (default)'}"
        )
        if args.dry_run:
            print(f"launcher:    {paths.launcher} (not written)")
            print("[dry-run] no changes were made.")
            return EXIT_OK

        # Phase 2: the transaction, serialized by the installer lock.
        with InstallerLock(paths):
            ensure_dirs(paths)
            manifest = (
                load_manifest(paths) if os.path.exists(paths.manifest)
                else new_manifest()
            )
            for path in clean_stale_staging(paths):
                print(f"cleaned interrupted-install leftover: {path}")

            staging = stage_release(paths, files, version)
            try:
                # Launcher and autostart are written before the commit
                # point so a failure here leaves nothing activated.
                write_launcher(paths)
                if args.enable_autostart:
                    write_autostart(paths)
                activate(paths, manifest, staging, version)
            except Exception:
                shutil.rmtree(staging, ignore_errors=True)
                # Roll back files this run created that were not owned
                # before (first-install failure must leave no trace).
                if paths.launcher not in manifest["owned"]:
                    remove_if_ours(paths.launcher)
                if paths.autostart not in manifest["owned"]:
                    remove_if_ours(paths.autostart)
                raise
            manifest["owned"][paths.launcher] = {"kind": "launcher"}
            if args.enable_autostart:
                manifest["owned"][paths.autostart] = {"kind": "autostart"}
            save_manifest(paths, manifest)
    finally:
        if cleanup_dir:
            shutil.rmtree(cleanup_dir, ignore_errors=True)

    print(f"installed quickshell-kde {version}")
    print(f"launcher:    {paths.launcher}")
    print(f"active:      {paths.current} -> releases/{version}")
    if not args.enable_autostart:
        print(
            "note: autostart is disabled (default); start the shell with "
            f"'{paths.launcher}' or pass --enable-autostart."
        )
    return EXIT_OK


def cmd_rollback(args, paths: Paths) -> int:
    with InstallerLock(paths):
        manifest = load_manifest(paths)
        current = manifest.get("current")
        previous = manifest.get("previous")
        if not current or not previous:
            raise InstallerError(
                "no previous release to roll back to "
                f"(current={current!r}, previous={previous!r})."
            )
        prev_dir = paths.release_path(previous)
        read_release_marker(prev_dir, previous)  # must exist and be valid
        if args.dry_run:
            print(f"[dry-run] would roll back current: {current} -> {previous}")
            return EXIT_OK
        tmp_link = f"{paths.current}.tmp-{uuid.uuid4().hex[:8]}"
        try:
            os.symlink(os.path.join("releases", previous), tmp_link)
            os.replace(tmp_link, paths.current)
        except OSError as exc:
            try:
                os.unlink(tmp_link)
            except OSError:
                pass
            raise InstallerError(f"cannot swap 'current' to {previous}: {exc}")
        manifest["current"] = previous
        manifest["previous"] = current
        save_manifest(paths, manifest)
    print(f"rolled back: current release is now {previous} (was {current})")
    return EXIT_OK


def cmd_uninstall(args, paths: Paths) -> int:
    with InstallerLock(paths):
        manifest = load_manifest(paths)
        print("removing installer-owned paths:")
        for path, meta in sorted(manifest["owned"].items()):
            print(f"  {meta.get('kind', '?'):12} {path}")
        if os.path.islink(paths.current):
            print(f"  {'symlink':12} {paths.current}")
        print(f"  {'manifest':12} {paths.manifest}")
        if os.path.isdir(paths.user_config_dir):
            print(f"  (preserved)  {paths.user_config_dir}")
        if args.dry_run:
            print("[dry-run] no changes were made.")
            return EXIT_OK

        failures = []
        # Plain files first, then release directories.
        ordered = sorted(
            manifest["owned"].items(),
            key=lambda kv: 1 if kv[1].get("kind") == "release-dir" else 0,
        )
        for path, meta in ordered:
            kind = meta.get("kind")
            try:
                if kind == "release-dir":
                    safe_rmtree(path, paths.releases_dir, meta.get("version"))
                elif kind == "launcher":
                    safe_rmfile(path, paths.bin_dir)
                elif kind == "autostart":
                    safe_rmfile(path, paths.autostart_dir)
                else:
                    print(
                        f"warning: unknown owned entry {path!r} ({kind!r}); "
                        "skipping"
                    )
            except InstallerError as exc:
                failures.append(str(exc))
                print(f"warning: {exc}")

        if os.path.islink(paths.current):
            link_target = os.readlink(paths.current)
            if link_target.startswith("releases" + os.sep):
                os.unlink(paths.current)
            else:
                failures.append(f"{paths.current} points outside releases/")
                print(
                    f"warning: {paths.current} -> {link_target} is not ours; "
                    "left in place"
                )
        elif os.path.exists(paths.current):
            failures.append(f"{paths.current} is not a symlink; left in place")
            print(f"warning: {paths.current} exists but is not a symlink; left in place")

        try:
            os.unlink(paths.manifest)
        except OSError as exc:
            failures.append(f"cannot remove manifest: {exc}")

        # Drop the lock file, then remove the directories we own when and
        # only when they are empty; anything the user parked next to our
        # files stays untouched.
        try:
            os.unlink(paths.lock)
        except OSError:
            pass
        for d in (paths.trash_dir, paths.releases_dir, paths.data_root):
            try:
                os.rmdir(d)  # ENOTEMPTY if foreign files remain
            except OSError as exc:
                if exc.errno != errno.ENOTEMPTY:
                    failures.append(f"cannot remove {d}: {exc}")
                else:
                    print(f"note: {d} kept (not empty)")

        if failures:
            print("uninstall completed with warnings:")
            for failure in failures:
                print(f"  - {failure}")
            return EXIT_ERROR
    print("quickshell-kde uninstalled.")
    if os.path.isdir(paths.user_config_dir):
        print(
            f"your configuration was preserved at {paths.user_config_dir} "
            "(remove it manually if you no longer need it)."
        )
    return EXIT_OK


def cmd_list(args, paths: Paths) -> int:
    if not os.path.exists(paths.manifest):
        print("no installation found.")
        return EXIT_OK
    manifest = load_manifest(paths)
    print(f"installation root: {paths.data_root}")
    current = manifest.get("current")
    previous = manifest.get("previous")
    for version in sorted(manifest.get("releases", {})):
        rel = manifest["releases"][version]
        exists = os.path.isdir(paths.release_path(version))
        marks = []
        if version == current:
            marks.append("current")
        if version == previous:
            marks.append("previous")
        status = " ".join(marks) or "-"
        print(
            f"  {version:40} {status:18} "
            f"files={rel.get('files', '?')} activated={rel.get('activated', '?')} "
            f"ondisk={'yes' if exists else 'NO'}"
        )
    if current and not os.path.isdir(paths.current):
        print("warning: 'current' symlink is missing or dangling")
    return EXIT_OK


# ---------------------------------------------------------------------------
# Doctor
# ---------------------------------------------------------------------------

REQUIRED_TOOLS = [
    ("quickshell", "Wayland layer-shell QML host", "quickshell (upstream release / AUR quickshell-git)"),
    ("qdbus6", "D-Bus IPC for KWin workspace, window and brightness calls", "qt6-tools"),
    ("kdotool", "active-window query and KWin script actions", "kdotool (AUR)"),
    ("gio", "application launching and URI opening", "glib2"),
    ("python3", "XDG desktop-entry parser and display discovery helpers", "python"),
    ("dbus-monitor", "brightness change signals", "dbus"),
    ("wpctl", "PipeWire/WirePlumber audio control", "wireplumber"),
    ("loginctl", "session lock from the power menu", "systemd"),
]

RECOMMENDED_TOOLS = [
    ("kcmshell6", "opening KDE control modules", "kde-cli-tools"),
    ("systemsettings", "opening KDE system settings", "systemsettings"),
    ("upower", "battery percentage and AC state", "upower"),
    ("fc-list", "font family checks (Noto Sans / Hack)", "fontconfig"),
]


def _consistency_problems(paths: Paths, manifest: dict) -> "tuple[list, list]":
    """Cross-check manifest against the on-disk state.

    Returns (problems, warnings): problems make doctor fail (the shell
    cannot run from this installation), warnings are cosmetic."""
    problems = []
    warnings = []
    current = manifest.get("current")
    if current:
        if not os.path.islink(paths.current):
            problems.append(f"'current' symlink missing (manifest says {current})")
        else:
            target = os.readlink(paths.current)
            expected = os.path.join("releases", current)
            if target != expected:
                problems.append(
                    f"'current' -> {target} but manifest says {expected}"
                )
    for version in manifest.get("releases", {}):
        release_dir = paths.release_path(version)
        if not os.path.isdir(release_dir):
            problems.append(f"release {version} is in the manifest but missing on disk")
    if os.path.isdir(paths.releases_dir):
        known = {v for v in manifest.get("releases", {})}
        for name in os.listdir(paths.releases_dir):
            if name.startswith(".") or name in known:
                continue
            warnings.append(
                f"release directory {name!r} is on disk but not in the "
                "manifest (orphan; it will NOT be removed by uninstall)"
            )
    return problems, warnings


def cmd_doctor(args, paths: Paths) -> int:
    print(f"installation root: {paths.data_root}")
    problems = []
    warnings = []

    print("\nRequired runtime tools:")
    for name, role, package in REQUIRED_TOOLS:
        found = shutil.which(name)
        if found:
            print(f"  [ok]      {name:16} {found}")
        else:
            print(f"  [MISSING] {name:16} {role}")
            print(f"            install: {package} (Arch names; adapt for your distro)")
            problems.append(name)

    print("\nRecommended tools:")
    for name, role, package in RECOMMENDED_TOOLS:
        found = shutil.which(name)
        if found:
            print(f"  [ok]      {name:16} {found}")
        else:
            print(f"  [absent]  {name:16} {role} (install: {package})")
            warnings.append(name)

    if shutil.which("fc-list"):
        try:
            result = subprocess.run(
                ["fc-list", ":", "family"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            families = set(result.stdout.split())
            for font in ("Noto", "Hack"):
                hit = any(f.startswith(font) for f in families)
                print(f"  [{'ok' if hit else 'absent'}]     font family {font}")
        except subprocess.SubprocessError:
            print("  [unknown] font check failed to run fc-list")

    print("\nInstallation health:")
    if os.path.exists(paths.manifest):
        try:
            manifest = load_manifest(paths)
            current = manifest.get("current")
            print(f"  [ok]      manifest {paths.manifest}")
            if current:
                current_dir = paths.release_path(current)
                try:
                    read_release_marker(current_dir, current)
                    print(f"  [ok]      current release {current} (marker valid)")
                except InstallerError as exc:
                    print(f"  [BROKEN]  current release: {exc}")
                    problems.append("current-release")
                bridge = os.path.join(
                    current_dir, "services", "kwin", "bridge", "libkwineventbridgeplugin.so"
                )
                if os.path.isdir(os.path.dirname(bridge)):
                    label = "ok" if os.path.isfile(bridge) else "absent (optional, fallback used)"
                    print(f"  [{label}] compiled KWin event bridge")
            else:
                print("  [note]    no release activated yet")
            consistency_problems, consistency_warnings = _consistency_problems(
                paths, manifest
            )
            for problem in consistency_problems:
                print(f"  [BROKEN]  {problem}")
                problems.append("consistency")
            for warning in consistency_warnings:
                print(f"  [note]    {warning}")
                warnings.append("orphan")
        except InstallerError as exc:
            print(f"  [BROKEN]  {exc}")
            problems.append("manifest")
    else:
        print("  [note]    not installed (no manifest)")

    if os.path.islink(paths.current) and not os.path.exists(paths.current):
        print(f"  [BROKEN]  {paths.current} is dangling")
        problems.append("current-symlink")

    stale = []
    if os.path.isdir(paths.releases_dir):
        stale = [
            os.path.join(paths.releases_dir, n)
            for n in os.listdir(paths.releases_dir)
            if n.startswith(STAGING_PREFIX)
        ]
    if stale:
        print("  [note]    interrupted-install leftovers (cleaned by the next install):")
        for path in stale:
            print(f"            {path}")
    else:
        print("  [ok]      no staging leftovers")

    if os.path.isdir(paths.user_config_dir):
        print(
            f"  [ok]      user configuration present at {paths.user_config_dir} "
            "(preserved by uninstall)"
        )
    else:
        print(f"  [note]    no user configuration yet at {paths.user_config_dir}")

    if os.path.isfile(paths.autostart):
        print(f"  [ok]      autostart enabled ({paths.autostart})")
    else:
        print("  [note]    autostart disabled (default)")

    print()
    if problems:
        print(f"doctor: {len(problems)} problem(s): {', '.join(problems)}")
        print("Fix the missing required tools, then re-run doctor.")
        return EXIT_DOCTOR
    if warnings:
        print(f"doctor: OK; {len(warnings)} optional tool(s) missing.")
        return EXIT_OK
    print("doctor: all checks passed.")
    return EXIT_OK


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="arena_installer",
        description=(
            "Secure, transactional, per-user installer for quickshell-kde. "
            "Installs versioned releases under the app's data root, keeps an "
            "atomic 'current' symlink and a launcher in ~/.local/bin, and "
            "never touches your configuration or other Quickshell installs."
        ),
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    for name in ("install", "update"):
        p = sub.add_parser(
            name,
            help=(
                "install a release from a checkout directory or tar archive "
                "(update: requires an existing installation)"
            ),
        )
        p.add_argument(
            "source", help="source checkout directory or .tar(.gz/.xz/.bz2) archive"
        )
        p.add_argument(
            "--version",
            help="explicit release id (default: git describe / release.json / timestamp)",
        )
        p.add_argument(
            "--enable-autostart",
            action="store_true",
            help="create ~/.config/autostart/quickshell-kde.desktop (off by default)",
        )
        p.add_argument(
            "--dry-run", action="store_true", help="print the plan, change nothing"
        )
        p.set_defaults(func=cmd_install)

    p = sub.add_parser(
        "rollback", help="switch 'current' back to the previous release"
    )
    p.add_argument("--dry-run", action="store_true", help="print the plan, change nothing")
    p.set_defaults(func=cmd_rollback)

    p = sub.add_parser("uninstall", help="remove everything the installer owns")
    p.add_argument("--dry-run", action="store_true", help="print the plan, change nothing")
    p.set_defaults(func=cmd_uninstall)

    p = sub.add_parser("list", help="list installed releases")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser(
        "doctor", help="check runtime dependencies and installation health"
    )
    p.set_defaults(func=cmd_doctor)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        paths = Paths(dict(os.environ))
        return args.func(args, paths)
    except InstallerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.code
    except KeyboardInterrupt:
        print(
            "\ninterrupted; run the doctor command to check installation health.",
            file=sys.stderr,
        )
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
