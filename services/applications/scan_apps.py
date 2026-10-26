#!/usr/bin/env python3
import os
import sys
import json
import glob
import re
import shlex

def extract_exec_binary(exec_str, try_exec=''):
    raw = try_exec or exec_str or ''
    if not raw:
        return ''
    # Strip env vars
    clean = re.sub(r'^[A-Za-z0-9_]+=[^\s]+\s+', '', raw)
    # Check flatpak command
    m = re.search(r'--command=([^\s]+)', clean)
    if m:
        return m.group(1).lower()
    # Check general exec
    parts = clean.split()
    if not parts:
        return ''
    exe = os.path.basename(parts[0])
    # If flatpak
    if exe == 'flatpak' and len(parts) > 1:
        for p in parts[1:]:
            if not p.startswith('-') and '.' in p:
                return p.split('.')[-1].lower()
            elif not p.startswith('-'):
                return p.lower()
    # AppImage name cleaning (e.g. helium-0.10.9.1-x86_64.AppImage -> helium)
    if 'appimage' in exe.lower():
        clean_name = re.sub(r'-[0-9].*$', '', exe)
        clean_name = clean_name.replace('.appimage', '').replace('.AppImage', '')
        return clean_name.lower()
    return exe.lower()

def generate_aliases(app_id, name, generic_name, icon, startup_wm_class, exec_binary):
    aliases = set()
    if app_id:
        aid = app_id.lower().replace('.desktop', '')
        aliases.add(aid)
        if '.' in aid:
            aliases.add(aid.split('.')[-1])
        if aid.startswith('appimagekit_'):
            clean = re.sub(r'^appimagekit_[0-9a-f]+-', '', aid)
            aliases.add(clean)
    if name:
        clean_name = re.sub(r'\s*\([^)]*\)', '', name).strip().lower()
        if clean_name:
            aliases.add(clean_name)
    if generic_name:
        aliases.add(generic_name.strip().lower())
    if startup_wm_class:
        aliases.add(startup_wm_class.strip().lower())
    if icon:
        clean_icon = icon.lower().replace('.desktop', '')
        aliases.add(clean_icon)
        if clean_icon.startswith('appimagekit_'):
            clean = re.sub(r'^appimagekit_[0-9a-f]+_', '', clean_icon)
            aliases.add(clean)
    # Only add exec_binary if no specific crx_/pwa startup_wm_class
    if exec_binary and not (startup_wm_class and startup_wm_class.startswith('crx_')):
        aliases.add(exec_binary.lower())
    return sorted(list(aliases))

def get_locale_candidates(locale_override=None):
    raw = locale_override if locale_override is not None else (
        os.environ.get('LC_ALL') or os.environ.get('LC_MESSAGES') or os.environ.get('LANG') or ''
    )
    raw = str(raw).strip()
    if not raw or raw in ('C', 'POSIX') or raw.startswith('C.'):
        return []
    no_enc = raw.split('.', 1)[0]
    base_part = no_enc.split('@', 1)[0]
    modifier = no_enc.split('@', 1)[1] if '@' in no_enc else ''
    candidates = []
    if modifier and '_' in base_part:
        lang = base_part.split('_', 1)[0]
        candidates.append(f"{base_part}@{modifier}")
        candidates.append(base_part)
        candidates.append(f"{lang}@{modifier}")
        candidates.append(lang)
    elif modifier:
        candidates.append(f"{base_part}@{modifier}")
        candidates.append(base_part)
    elif '_' in base_part:
        lang = base_part.split('_', 1)[0]
        candidates.append(base_part)
        candidates.append(lang)
    else:
        candidates.append(base_part)
    seen = set()
    res = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            res.append(c)
    return res

def resolve_localized_value(section_data, key, locale_candidates):
    for loc in locale_candidates:
        loc_key = f"{key}[{loc}]"
        val = section_data.get(loc_key, '').strip()
        if val:
            return val
    return section_data.get(key, '').strip()

def sanitize_and_tokenize_exec(exec_cmd, icon='', name='', desktop_file=''):
    if not exec_cmd or not str(exec_cmd).strip():
        return '', []
    try:
        raw_tokens = shlex.split(str(exec_cmd), posix=True)
    except ValueError:
        return '', []
    if not raw_tokens:
        return '', []

    final_tokens = []
    for tok in raw_tokens:
        if tok == '%i':
            if icon:
                final_tokens.extend(['--icon', icon])
            continue
        if tok in ('%f', '%F', '%u', '%U', '%d', '%D', '%n', '%N', '%v', '%m'):
            continue
        if tok == '%c':
            if name:
                final_tokens.append(name)
            continue
        if tok == '%k':
            if desktop_file:
                final_tokens.append(desktop_file)
            continue

        # Handle embedded field codes and literal %% escapes
        placeholder = '\x00LITERAL_PERCENT\x00'
        s = tok.replace('%%', placeholder)
        s = s.replace('%c', name or '')
        s = s.replace('%k', desktop_file or '')
        s = re.sub(r'%[a-zA-Z]', '', s)
        s = s.replace(placeholder, '%')
        if s != '' or tok == '':
            final_tokens.append(s)

    # Strip leading bare VAR=val assignments if not preceded by `env`
    while final_tokens and re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', final_tokens[0]):
        final_tokens.pop(0)

    if not final_tokens or not final_tokens[0].strip():
        return '', []

    clean_str = ' '.join(shlex.quote(t) if (' ' in t or '\t' in t or '"' in t or "'" in t) else t for t in final_tokens)
    return clean_str, final_tokens

def is_shown_in_kde(section_data):
    only_show = [x.strip() for x in section_data.get('OnlyShowIn', '').split(';') if x.strip()]
    if only_show and 'KDE' not in only_show:
        return False
    not_show = [x.strip() for x in section_data.get('NotShowIn', '').split(';') if x.strip()]
    if not_show and 'KDE' in not_show:
        return False
    return True

def parse_desktop_file(filepath, locale=None):
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except Exception:
        return None

    current_section = None
    data = {}
    action_groups = {}

    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('[') and line.endswith(']'):
            if line == '[Desktop Entry]':
                current_section = 'main'
            elif line.startswith('[Desktop Action ') and len(line) > len('[Desktop Action ]'):
                act_id = line[len('[Desktop Action '):-1].strip()
                if act_id and re.match(r'^[A-Za-z0-9._-]+$', act_id) and act_id not in action_groups:
                    action_groups[act_id] = {}
                    current_section = ('action', act_id)
                else:
                    current_section = None
            else:
                current_section = None
            continue

        if current_section is not None and '=' in line:
            key, val = line.split('=', 1)
            key = key.strip()
            val = val.strip()
            if current_section == 'main':
                if key not in data:
                    data[key] = val
            elif isinstance(current_section, tuple) and current_section[0] == 'action':
                act_dict = action_groups[current_section[1]]
                if key not in act_dict:
                    act_dict[key] = val

    if data.get('Type') != 'Application':
        return None
    if data.get('NoDisplay', '').lower() == 'true':
        return None
    if data.get('Hidden', '').lower() == 'true':
        return None

    locale_candidates = get_locale_candidates(locale)
    name = data.get('Name', '').strip()
    if not name:
        name = resolve_localized_value(data, 'Name', locale_candidates)
    if not name:
        return None

    icon = data.get('Icon', '').strip()
    exec_cmd = data.get('Exec', '')
    try_exec = data.get('TryExec', '')
    exec_clean, exec_args = sanitize_and_tokenize_exec(exec_cmd, icon=icon, name=name, desktop_file=filepath)
    if not exec_clean and exec_cmd:
        exec_clean = re.sub(r'\s%[a-zA-Z]', '', exec_cmd).strip()

    startup_wm_class = data.get('StartupWMClass', '')
    exec_binary = extract_exec_binary(exec_clean, try_exec)
    categories = [c.strip() for c in data.get('Categories', '').split(';') if c.strip()]
    keywords = [k.strip() for k in data.get('Keywords', '').split(';') if k.strip()]
    comment = data.get('Comment', '')
    generic_name = data.get('GenericName', '')
    app_id = os.path.splitext(os.path.basename(filepath))[0]

    # Action commands are never added to application identity aliases
    aliases = generate_aliases(app_id, name, generic_name, icon, startup_wm_class, exec_binary)

    # Parse quick actions in exact declared Actions= order
    declared_action_ids = []
    seen_action_ids = set()
    for raw_aid in data.get('Actions', '').split(';'):
        aid = raw_aid.strip()
        if aid and re.match(r'^[A-Za-z0-9._-]+$', aid) and aid not in seen_action_ids:
            seen_action_ids.add(aid)
            declared_action_ids.append(aid)

    actions = []
    for aid in declared_action_ids:
        act_data = action_groups.get(aid)
        if not act_data:
            continue
        if not is_shown_in_kde(act_data):
            continue
        act_name = resolve_localized_value(act_data, 'Name', locale_candidates)
        if not act_name:
            continue
        act_icon = act_data.get('Icon', '').strip()
        act_exec_raw = act_data.get('Exec', '').strip()
        if not act_exec_raw:
            continue
        act_exec_clean, act_exec_args = sanitize_and_tokenize_exec(
            act_exec_raw,
            icon=act_icon or icon,
            name=act_name,
            desktop_file=filepath
        )
        if not act_exec_args:
            continue
        actions.append({
            'id': aid,
            'name': act_name,
            'icon': act_icon,
            'exec': act_exec_clean,
            'execArgs': act_exec_args
        })

    return {
        'id': app_id,
        'name': name,
        'genericName': generic_name,
        'comment': comment,
        'icon': icon,
        'exec': exec_clean,
        'execArgs': exec_args,
        'desktopFile': filepath,
        'startupWMClass': startup_wm_class,
        'execBinary': exec_binary,
        'aliases': aliases,
        'categories': categories,
        'keywords': keywords,
        'terminal': data.get('Terminal', '').lower() == 'true',
        'actions': actions
    }

def scan_all(extra_dirs=None, locale=None):
    if extra_dirs is not None:
        search_dirs = list(extra_dirs)
    else:
        xdg_data_dirs = os.environ.get('XDG_DATA_DIRS', '/usr/local/share:/usr/share').split(':')
        home_data = os.path.expanduser('~/.local/share')
        search_dirs = [os.path.join(home_data, 'applications')]

        for d in xdg_data_dirs:
            if d:
                search_dirs.append(os.path.join(d, 'applications'))

        # Flatpak system & user
        search_dirs.append('/var/lib/flatpak/exports/share/applications')
        search_dirs.append(os.path.expanduser('~/.local/share/flatpak/exports/share/applications'))

    seen_ids = set()
    apps = []

    for sdir in search_dirs:
        if not os.path.isdir(sdir):
            continue
        for desktop_file in sorted(glob.glob(os.path.join(sdir, '**/*.desktop'), recursive=True)):
            app = parse_desktop_file(desktop_file, locale=locale)
            if app and app['id'] not in seen_ids:
                seen_ids.add(app['id'])
                apps.append(app)

    # Sort alphabetically by name
    apps.sort(key=lambda x: x['name'].lower())
    return apps

if __name__ == '__main__':
    result = scan_all()
    print(json.dumps(result))
