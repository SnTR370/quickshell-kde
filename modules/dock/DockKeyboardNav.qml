import QtQuick

// Deterministic keyboard focus order for one Dock layout.
// Order = visual layout order: launcher, pinned apps, unpinned running apps, settings.
// Separators and hidden/disabled items are never focusable. No timers, no polling:
// the list is computed on demand from the active layout when a key is pressed.
QtObject {
    id: root

    // Active (visible) RowLayout/ColumnLayout that owns the focusable dock items.
    property Item layout: null
    // Last item that held keyboard focus (auto-nulls if the delegate is destroyed).
    property Item lastItem: null

    function items() {
        const res = [];
        const kids = root.layout ? root.layout.children : [];
        for (let i = 0; i < kids.length; i++) {
            const c = kids[i];
            if (c && c.visible && c.enabled && c.activeFocusOnTab === true) {
                res.push(c);
            }
        }
        return res;
    }

    // Wrapping step used by arrow keys.
    function move(from, step) {
        const list = root.items();
        if (list.length === 0) return false;
        const idx = list.indexOf(from);
        const next = idx >= 0
            ? ((idx + step + list.length) % list.length)
            : (step >= 0 ? 0 : list.length - 1);
        const target = list[next];
        if (!target || target === from) return false;
        target.forceActiveFocus();
        return true;
    }

    // Non-wrapping step used by Tab / Shift+Tab. Returns false at either end so the
    // caller can leave the Dock instead of trapping focus.
    function tabStep(from, delta) {
        const list = root.items();
        const idx = list.indexOf(from);
        if (idx < 0) return false;
        const next = idx + delta;
        if (next < 0 || next >= list.length) return false;
        list[next].forceActiveFocus();
        return true;
    }

    function boundary(last) {
        const list = root.items();
        if (list.length === 0) return false;
        const target = list[last ? list.length - 1 : 0];
        target.forceActiveFocus();
        return true;
    }

    // Entry point: restore the previous item when still valid, otherwise first item.
    function focusInitial() {
        const list = root.items();
        if (list.length === 0) return false;
        const target = (root.lastItem && list.indexOf(root.lastItem) >= 0) ? root.lastItem : list[0];
        target.forceActiveFocus();
        return true;
    }
}
