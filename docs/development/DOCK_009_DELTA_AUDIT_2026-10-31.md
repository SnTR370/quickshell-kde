# DOCK-009 delta audit (2026-10-31)

Independent post-audit remediation review of d4719cb (feat(dock): DOCK-009
notification, urgency and progress indicators), which the earlier MiMo audit
did not cover. Base for this audit: fix/post-audit-remediation @ 4b2558e.

## Reviewed

- `services/notifications/NotificationBadges.js` (pure helpers)
- `services/notifications/NotificationService.qml` (lifecycle wiring)
- `modules/dock/DockItem.qml` (badge/urgency/progress rendering, attention)
- `modules/notifications/NotificationCard.qml`, `ToastHost.qml`
- `tests/test_dock_notification_badges.py` (18 tests, all green at review
  time, 77s including the private-D-Bus E2E against the real server)
- API surface cross-checked against the installed Quickshell 0.3.2
  `quickshell-service-notifications.qmltypes`: `tracked`, `closed(reason)`,
  `hintsChanged`, `urgencyChanged`, `expireTimeoutChanged`, `dismiss()`,
  `expire()`, `keepOnReload` all exist as used.

## Verdict

The implementation matches its claims. No release-blocking defect found.
Counts/urgency/progress are exact server state as documented; close paths
(user dismiss / client expiry / client withdrawal / attention) are all
routed through the native object; transient and -1/0 timeout semantics
follow the documented rules; app matching never guesses.

## Confirmed defect found (adjacent, pre-existing DOCK-011)

- `modules/dock/DockItem.qml` member-count Badge: the `count:` binding
  evaluated `root.stack.appIds` without a null guard, throwing
  `TypeError: Cannot read property 'appIds' of null` for every non-stack
  dock item (observed in the isolated full-shell startup rig logs).
  Fixed in this branch (one-line guard) with a static regression contract
  in `tests/test_dock_stacks.py::test_dock_item_stack_bindings_null_safe`.

## Remaining limitations (documented, not defects)

1. **Reload desync**: `keepOnReload: true` keeps tracked notifications
   alive across a Quickshell config reload, but the fresh engine does not
   re-attach them to `activeNotifications` (the server's
   `trackedNotifications` list is not enumerated on startup). Badges for
   notifications that survive a reload therefore vanish; they never go
   stale or wrong. Re-attachment would be an enhancement, not a fix.
2. **History retention**: `notificationsHistory` items keep the `raw`
   Notification object reference after close (dangling once the object is
   destroyed). Nothing dereferences it — pure memory retention, bounded by
   `maxHistory` (50).
3. **Toast linger on disable**: turning `notificationsEnabled` off clears
   `activeNotifications` but not `activeToasts`; visible toasts remain
   until their auto-hide timer or manual dismissal.
4. **Progress tie-break**: with two same-app progress notifications
   updated within the same millisecond, the badge winner is arbitrary
   (`>=` timestamp comparison). Cosmetic only.

## False positives from the feature description (checked, not real)

- "Sweeper could close never-expiring notifications": `expiredIds` only
  honors strictly positive `expireTimeout` values; -1 and 0 are excluded.
- "Replacements could double-count": `upsertActive` updates in place by
  id; the E2E covers live progress replacement.
- "Transient notifications could badge": `buildBadges` skips them.
