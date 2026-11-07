# quickshell-kde Arena Installer

A secure, transactional, per-user installer and uninstaller for
quickshell-kde. It installs frozen releases into versioned directories,
keeps an atomic `current` pointer, and never touches your configuration,
your Plasma session, or other Quickshell installations.

```
usage: arena_installer.py COMMAND ...

commands:
  install    install a release from a checkout directory or tar archive
  update     install a release over an existing installation
  rollback   switch 'current' back to the previous release
  uninstall  remove everything the installer owns
  list       list installed releases
  doctor     check runtime dependencies and installation health
```

Every mutating command accepts `--dry-run` (print the plan, change
nothing). `install`/`update` accept `--version ID` and
`--enable-autostart` (autostart is **off** by default).

## Install layout

```
$XDG_DATA_HOME/quickshell-kde/          (default: ~/.local/share/quickshell-kde)
├── releases/<version>/                 frozen release trees (immutable once activated)
│   └── .quickshell-kde-release         release marker (ownership proof)
├── releases/.staging-<id>/             transient staging (cleaned by the next install)
├── current -> releases/<version>       atomic pointer, swapped with rename(2)
├── .trash/                             rollback safety during re-installs
├── manifest.json                       installation manifest (owned paths)
└── .lock                               flock(2) against concurrent installs

~/.local/bin/quickshell-kde             generated sh launcher (exec quickshell -p …/current/shell.qml)
~/.config/autostart/quickshell-kde.desktop   only with --enable-autostart
```

Your user configuration lives in `~/.config/quickshell-kde/` and is read
by the shell itself; the installer never reads, writes or deletes it.
Uninstall preserves it and tells you where it is.

## How a transaction works

1. The source (checkout directory or tar archive) is scanned. Symlinks,
   special files, `.git/`, `__pycache__/` and `.rig/` are rejected or
   skipped; a tree without `shell.qml` is refused.
2. Content is copied into `releases/.staging-<id>/` and re-verified
   (file count, `shell.qml`, marker) while the old release is still the
   active one.
3. The launcher (and autostart entry, if requested) is written via
   `tmp + rename`. If the target already exists and is not ours, the
   install is refused — pre-existing user files are never overwritten.
4. The staging directory is renamed to `releases/<version>` and the
   `current` symlink is swapped atomically. **This symlink swap is the
   commit point.** Any failure before it rolls the new release back out
   and leaves the previously working release active.
5. The manifest is updated atomically (`tmp + rename` + `fsync`).

An interrupted install therefore leaves either the old release active
(clean failure) or, at worst, ignorable leftovers (`releases/.staging-*`,
`current.tmp-*`), which the next `install` removes and `doctor` reports.

## Version selection

`--version` wins; otherwise `release.json` (`{"version": "…"}`) in the
source root; otherwise `git describe --tags --always --dirty` if the
source is a git checkout; otherwise a `vYYYYMMDD-HHMMSS` timestamp.
Versions must match `[A-Za-z0-9][A-Za-z0-9._+-]{0,63}`.

## Typical session

```bash
# from a checkout or an archive, into your user account:
python3 installer/arena_installer.py install ~/Projects/quickshell-kde
python3 installer/arena_installer.py doctor
~/.local/bin/quickshell-kde          # start the shell
~/.local/bin/quickshell-kde kill     # stop it

# upgrade, then decide you do not like it:
python3 installer/arena_installer.py update quickshell-kde-0.2.tar.gz
python3 installer/arena_installer.py rollback

# leave:
python3 installer/arena_installer.py uninstall --dry-run
python3 installer/arena_installer.py uninstall
```

Dependencies are never installed automatically — no sudo, no pacman,
no paru, no remote scripts. `doctor` lists what is missing and which
package provides it (Arch package names; adapt for your distribution).

## Safety model

- **Ownership**: only paths recorded in `manifest.json` are ever
  deleted, and each one is re-validated at uninstall time (release
  directories must sit under `releases/`, be real directories, and
  carry a matching marker; the launcher and autostart files must carry
  the installer tag; nothing is followed through symlinks).
- **No symlink escapes**: sources containing symlinks are rejected;
  archive members that are symlinks/hardlinks or contain `..`/absolute
  paths are rejected before extraction; a `~/.local/share/quickshell-kde`
  that is itself a symlink is refused.
- **No unsafe roots**: `HOME=/`, non-absolute `XDG_DATA_HOME`, or an
  installation root colliding with `HOME`/`XDG_DATA_HOME` are refused.
- **Concurrency**: an flock on `.lock` serializes installs; a second
  concurrent installer exits with an error instead of racing.
- **Compiled KWin bridge is optional**: if the source contains the
  built `libkwineventbridgeplugin.so`, it is shipped along; without it
  the shell keeps its documented snapshot-based fallback. `doctor`
  reports which state is active.
- **Autostart off by default**: nothing is added to
  `~/.config/autostart` unless `--enable-autostart` is passed.

## Recovery

| Symptom | Recovery |
| :--- | :--- |
| install was interrupted (SIGKILL/power loss) | run `install` again — stale `.staging-*`/`current.tmp-*` leftovers are cleaned first; `doctor` lists them |
| `current` is dangling after a crash | `doctor` reports it; run `install` (same or new version) or `rollback` |
| release dir exists but not in manifest | `doctor` flags it as an orphan; `uninstall` will **not** delete it; installing the same version takes it over |
| wrong release active | `rollback` (ping-pongs `current`/`previous`), or `install --version <id>` any listed version |
| locked out by `.lock` | only if another installer is truly running; otherwise delete the stale `~/.local/share/quickshell-kde/.lock` |
| launcher broken/missing | re-run `install`; the launcher is regenerated on every install/update |

Manual repair of last resort: `manifest.json` is plain JSON — the
`releases/` trees are self-contained, so `quickshell -p
<releases-dir>/shell.qml` runs any of them directly.

## Supported platforms

- Linux, KDE Plasma 6 / KWin Wayland (the shell's own requirement).
- Python **3.9+**, standard library only, for the installer itself.
- Runtime dependencies of the *shell* (Quickshell 0.3.2+, qdbus6,
  kdotool, gio, dbus-monitor, wpctl, loginctl, …) are listed and
  diagnosed by `doctor`; see the dependency table in the repository
  `README.md`. Arch package names are used as hints.
- Per-user only: everything lives under `$XDG_DATA_HOME`,
  `$XDG_CONFIG_HOME` and `~/.local/bin`. No root, ever.

## Security limitations (be honest about these)

- The installer copies whatever the source contains; it validates
  *structure* (no symlinks, no special files, `shell.qml` present), not
  *content*. Install only from sources you trust — the shell executes
  QML/JS and spawns helper processes.
- The manifest is not signed or tamper-proof. An attacker who can write
  to your `~/.local/share` can already replace the shell itself; the
  marker/tag re-validation at uninstall time defends against *accidents*
  (and naive scripts), not against a hostile local user.
- Advisory flock only protects against other *arena installer*
  processes, not against manual edits to the managed tree.
- The crash window between the symlink swap and the manifest save (one
  rename) is not journaled; `doctor` detects the inconsistency and
  re-install or `rollback` repairs it.
- `--enable-autostart` writes one `.desktop` file; it does not
  integrate with systemd user units or Plasma's session restore.
