#!/usr/bin/env python3
import subprocess
import json
from concurrent.futures import ThreadPoolExecutor

def get_prop(path, prop):
    try:
        return subprocess.check_output(
            ["qdbus6", "org.kde.ScreenBrightness", path, "org.kde.ScreenBrightness.Display." + prop],
            text=True,
            stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return ""

def get_display_info(name):
    path = "/org/kde/ScreenBrightness/" + name
    with ThreadPoolExecutor(max_workers=4) as ex:
        f_b = ex.submit(get_prop, path, "Brightness")
        f_m = ex.submit(get_prop, path, "MaxBrightness")
        f_i = ex.submit(get_prop, path, "IsInternal")
        f_l = ex.submit(get_prop, path, "Label")
        b_str = f_b.result()
        m_str = f_m.result()
        i_str = f_i.result()
        label = f_l.result()

    # Reject displays where required properties could not be read
    if not (b_str.isdigit() and m_str.isdigit()):
        return None

    b = int(b_str)
    m = int(m_str)
    if m <= 0:
        return None

    return {
        "dbusName": name,
        "path": path,
        "label": label or name,
        "isInternal": i_str.lower() == "true",
        "brightness": b,
        "maxBrightness": m
    }

def discover():
    try:
        out = subprocess.check_output(
            ["qdbus6", "org.kde.ScreenBrightness", "/org/kde/ScreenBrightness", "org.kde.ScreenBrightness.DisplaysDBusNames"],
            text=True,
            stderr=subprocess.DEVNULL
        ).strip()
        names = [s.strip() for s in out.splitlines() if s.strip()]
        with ThreadPoolExecutor(max_workers=max(1, len(names))) as ex:
            raw_displays = list(ex.map(get_display_info, names))
        valid_displays = [d for d in raw_displays if d is not None]
        print(json.dumps(valid_displays))
    except Exception:
        print("[]")

if __name__ == "__main__":
    discover()
