import json
import os

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
SETTINGS_PATH = os.path.join(DATA_DIR, "bot_settings.json")

DEFAULTS = {
    "whois_daily_limit": 10,
    "video_daily_limit": 1,
    "max_video_duration": 8,
    "image_daily_limit_default": 1,
    "bot_enabled": True,
    "extra_admins": [],
}

def _load():
    if os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = DEFAULTS.copy()
        merged.update(data)
        return merged
    return DEFAULTS.copy()

def _save(settings):
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

def get_setting(key):
    return _load().get(key, DEFAULTS.get(key))

def set_setting(key, value):
    settings = _load()
    settings[key] = value
    _save(settings)