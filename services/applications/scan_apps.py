#!/usr/bin/env python3
import os
import sys
import json
import glob
import re

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

def parse_desktop_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except Exception:
        return None

    in_main_section = False
    data = {}
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('[') and line.endswith(']'):
            if line == '[Desktop Entry]':
                in_main_section = True
            else:
                in_main_section = False
            continue
        
        if in_main_section and '=' in line:
            key, val = line.split('=', 1)
            key = key.strip()
            val = val.strip()
            if key not in data:
                data[key] = val

    if data.get('Type') != 'Application':
        return None
    if data.get('NoDisplay', '').lower() == 'true':
        return None
    if data.get('Hidden', '').lower() == 'true':
        return None

    exec_cmd = data.get('Exec', '')
    try_exec = data.get('TryExec', '')
    # Strip XDG field codes (%f, %F, %u, %U, %i, %c, %k, %v, %m, %d, %D, %n, %N)
    exec_clean = re.sub(r'\s%[a-zA-Z]', '', exec_cmd).strip()

    name = data.get('Name', '')
    if not name:
        return None

    icon = data.get('Icon', '')
    startup_wm_class = data.get('StartupWMClass', '')
    exec_binary = extract_exec_binary(exec_clean, try_exec)
    categories = [c.strip() for c in data.get('Categories', '').split(';') if c.strip()]
    keywords = [k.strip() for k in data.get('Keywords', '').split(';') if k.strip()]
    comment = data.get('Comment', '')
    generic_name = data.get('GenericName', '')
    app_id = os.path.splitext(os.path.basename(filepath))[0]

    aliases = generate_aliases(app_id, name, generic_name, icon, startup_wm_class, exec_binary)

    return {
        'id': app_id,
        'name': name,
        'genericName': generic_name,
        'comment': comment,
        'icon': icon,
        'exec': exec_clean,
        'desktopFile': filepath,
        'startupWMClass': startup_wm_class,
        'execBinary': exec_binary,
        'aliases': aliases,
        'categories': categories,
        'keywords': keywords,
        'terminal': data.get('Terminal', '').lower() == 'true'
    }

def scan_all():
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
        for desktop_file in glob.glob(os.path.join(sdir, '**/*.desktop'), recursive=True):
            app = parse_desktop_file(desktop_file)
            if app and app['id'] not in seen_ids:
                seen_ids.add(app['id'])
                apps.append(app)

    # Sort alphabetically by name
    apps.sort(key=lambda x: x['name'].lower())
    return apps

if __name__ == '__main__':
    result = scan_all()
    print(json.dumps(result))
