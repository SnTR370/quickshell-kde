#!/usr/bin/env python3
import os
import sys
import json
import glob
import re

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
    # Strip XDG field codes (%f, %F, %u, %U, %i, %c, %k)
    exec_clean = re.sub(r'\s%[a-zA-Z]', '', exec_cmd).strip()

    name = data.get('Name', '')
    if not name:
        return None

    icon = data.get('Icon', '')
    categories = [c.strip() for c in data.get('Categories', '').split(';') if c.strip()]
    keywords = [k.strip() for k in data.get('Keywords', '').split(';') if k.strip()]
    comment = data.get('Comment', '')
    generic_name = data.get('GenericName', '')
    app_id = os.path.splitext(os.path.basename(filepath))[0]

    return {
        'id': app_id,
        'name': name,
        'genericName': generic_name,
        'comment': comment,
        'icon': icon,
        'exec': exec_clean,
        'desktopFile': filepath,
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
