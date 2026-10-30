.pragma library

// DOCK-004: pure pointer-driven dock magnification math.
//
// Axis-generic by construction: every input is a 1-D coordinate projected
// onto the dock's layout axis (x for bottom/top edges, y for left/right
// edges), so horizontal and vertical docks share the same code path.
//
// No timers, no polling, no QML dependencies: the Dock controller feeds
// rest geometry + the pointer position taken from its HoverHandler and
// applies the resulting scales/offsets imperatively.

// Parabolic falloff bump in [0, 1]: 1 at distance 0, exactly 0 at
// |distance| >= radius. f(d) = (1 - (d/R)^2)^2 is C1-continuous at both
// d = 0 and d = R, so icons enter/leave the influence radius without
// jumps and the total layout width changes smoothly.
function bump(distance, radius) {
    if (!(radius > 0) || !isFinite(distance)) return 0;
    const t = 1 - (distance * distance) / (radius * radius);
    return t > 0 ? t * t : 0;
}

// Scale factor for a single item: 1.0 outside the influence radius,
// maxScale at distance 0. Invalid maxScale (<= 1 or non-finite) degrades
// to no magnification instead of shrinking icons.
function scaleAt(distance, radius, maxScale) {
    const m = (isFinite(maxScale) && maxScale > 1) ? maxScale : 1;
    return 1 + (m - 1) * bump(distance, radius);
}

// Resolve magnification for one layout run (the visible children of the
// active RowLayout/ColumnLayout, in visual order).
//
//   centers     rest centers along the layout axis, ascending
//   extents     rest sizes along the axis (same length as centers)
//   magnifiable true where the entry may scale (DockItems); separators,
//               launcher and settings slots keep scale 1 but still displace
//   pointer     pointer coordinate on the same axis (NaN/Infinity = inactive)
//   radius      influence radius in px (config)
//   maxScale    maximum scale at distance 0 (config)
//   spacing     layout spacing between adjacent entries
//
// Returns { scales, offsets, growth }:
//   scales[i]  per-entry scale factor
//   offsets[i] lateral displacement = packed position - rest position
//   growth     total run width delta (>= 0); the dock surface grows by this
//
// Neighbor displacement: entries are re-packed with their magnified
// extents, so magnified icons physically make room for each other instead
// of scaling in place. The packed run keeps the REST run center fixed, so
// growth is symmetric, the dock stays centered and nothing jumps when
// icons enter/leave the influence radius.
function resolve(centers, extents, magnifiable, pointer, radius, maxScale, spacing) {
    const n = centers.length;
    const scales = new Array(n);
    const offsets = new Array(n);
    const active = isFinite(pointer);
    let wRest = 0;
    let wPrime = 0;
    for (let i = 0; i < n; i++) {
        const s = (active && magnifiable && magnifiable[i])
            ? scaleAt(centers[i] - pointer, radius, maxScale)
            : 1;
        scales[i] = s;
        wRest += extents[i];
        wPrime += extents[i] * s;
    }
    const gaps = n > 1 ? spacing * (n - 1) : 0;
    const totalRest = wRest + gaps;
    const totalPrime = wPrime + gaps;
    const growth = totalPrime - totalRest;

    // Rest run center from the run's outer edges.
    const runCenter = n > 0
        ? (centers[0] - extents[0] / 2 + centers[n - 1] + extents[n - 1] / 2) / 2
        : 0;

    // Pack magnified extents from the (fixed) run center.
    let cursor = runCenter - totalPrime / 2;
    for (let i = 0; i < n; i++) {
        const half = (extents[i] * scales[i]) / 2;
        cursor += half;
        offsets[i] = cursor - centers[i];
        cursor += half + spacing;
    }
    return { scales: scales, offsets: offsets, growth: growth };
}
