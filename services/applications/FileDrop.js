.pragma library

// DOCK-010: pure logic for external file drops onto dock icons.
//
// Two concerns live here so they can be unit-tested under node (vm):
//   1. URI filtering: turning a dropped URI list (file:// URIs from other
//      applications, e.g. Dolphin) into clean local file paths. Non-file
//      URIs (http, ftp, ...) and malformed input are rejected; a rejected
//      URI is a visible no-op, never an argument we pass on.
//   2. Launch-argument building: choosing the sanctioned launch mechanism
//      for "open these files with this application", mirroring the
//      priorities of ApplicationService.launch():
//        a. gio launch <desktop-file> <files...>  (desktop file resolvable)
//        b. gtk-launch <app-id> <files...>         (desktop id, no Exec)
//        c. pre-tokenized Exec argv + <files...>   (caller-parsed, safe)
//      Everything is returned as an argv array; callers pass it to
//      Quickshell.execDetached verbatim. No shell, no shell -c string, no
//      string concatenation into a command line, ever.

// Split a text/uri-list (or any newline-separated URI text) into entries.
// Blank lines and '#' comment lines are ignored per RFC 2483.
function uriListFromText(text) {
    if (!text || typeof text !== "string") return [];
    const out = [];
    const lines = text.split(/\r\n|\n|\r/);
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        if (line.length > 0 && line.charAt(0) !== "#") out.push(line);
    }
    return out;
}

// One URI -> local file path ("" when not a local file).
// Accepts file:// URIs (percent-decoded; only empty/localhost authority)
// and plain absolute paths. Rejects every other scheme, remote file
// targets, relative paths and malformed percent escapes.
function localPathFromUri(uri) {
    const s = String(uri || "").trim();
    if (s.length === 0) return "";
    if (s.indexOf("file:") !== 0) {
        // Plain local path (no scheme): accepted as-is, never decoded.
        return s.charAt(0) === "/" ? s : "";
    }
    let rest = s.slice(5);
    if (rest.indexOf("//") === 0) {
        rest = rest.slice(2);
        const slash = rest.indexOf("/");
        if (slash === -1) return "";
        const authority = rest.slice(0, slash);
        // Remote file targets (file://host/...) are not local: reject.
        if (authority.length > 0 && authority.toLowerCase() !== "localhost") return "";
        rest = rest.slice(slash);
    }
    if (rest.charAt(0) !== "/") return "";
    try {
        return decodeURIComponent(rest);
    } catch (e) {
        return "";
    }
}

// Filter a URI list down to deduplicated local paths, order preserved.
function localPathsFromUrls(urls) {
    const out = [];
    if (!urls || typeof urls !== "object" || typeof urls.length !== "number") return out;
    for (let i = 0; i < urls.length; i++) {
        const p = localPathFromUri(urls[i]);
        if (p.length > 0 && out.indexOf(p) === -1) out.push(p);
    }
    return out;
}

// Build the launch argv for `app` opening `paths` (already-sanitized local
// paths from localPathsFromUrls), or null when no safe mechanism exists.
//
// `tokenizedExecArgs` is the caller-resolved, safely tokenized Exec
// argument array (pre-scanned app.execArgs, or ApplicationService.
// parseExecArguments output). It is only ever used as an argv and copied
// before mutation; raw exec strings are never interpolated.
function buildLaunchCommand(app, paths, tokenizedExecArgs) {
    if (!app || !Array.isArray(paths) || paths.length === 0) return null;
    for (let i = 0; i < paths.length; i++) {
        if (typeof paths[i] !== "string" || paths[i].length === 0) return null;
    }
    const desktopFile = String(app.desktopFile || "").trim();
    if (desktopFile.length > 0) {
        // (a) Preferred: gio launch resolves the desktop entry itself and
        // honors its Exec/field codes - the Exec string is never parsed here.
        return ["gio", "launch", desktopFile].concat(paths);
    }
    const id = String(app.id || "").trim();
    const hasExec = app.exec && String(app.exec).trim().length > 0;
    if (id.length > 0 && !hasExec) {
        // (b) gtk-launch fallback (same tool ApplicationService.launch
        // uses) resolves the desktop entry and accepts file arguments.
        return ["gtk-launch", id].concat(paths);
    }
    if (Array.isArray(tokenizedExecArgs) && tokenizedExecArgs.length > 0 &&
        typeof tokenizedExecArgs[0] === "string" && tokenizedExecArgs[0].trim().length > 0) {
        // (c) Pre-tokenized Exec argv (field codes already expanded by the
        // scanner/parser) with all files appended in one invocation.
        return tokenizedExecArgs.slice().concat(paths);
    }
    if (id.length > 0) {
        return ["gtk-launch", id].concat(paths);
    }
    return null;
}
