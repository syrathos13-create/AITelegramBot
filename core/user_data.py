import json
import os
from datetime import date
from core.bot_settings import get_setting

PROFILES_DIR = "profiles"
os.makedirs(PROFILES_DIR, exist_ok=True)

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
USERNAME_INDEX_PATH = os.path.join(DATA_DIR, "username_index.json")

MEMORY_LIMIT = 60
DEFAULT_MESSAGE_LIMIT = 5
MAX_SAVED_ITEMS = 50

users = {}

def get_history(user_id):
    if user_id not in users:
        users[user_id] = []
    return users[user_id]

def profile_path(user_id):
    return os.path.join(PROFILES_DIR, f"{user_id}.json")

def load_profile(user_id):
    path = profile_path(user_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_profile(user_id, profile):
    with open(profile_path(user_id), "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)

def list_all_user_ids():
    ids = []
    for filename in os.listdir(PROFILES_DIR):
        if filename.endswith(".json"):
            ids.append(filename[:-5])
    return ids

def mark_active(user_id, profile):
    profile["last_active"] = str(date.today())
    save_profile(user_id, profile)

def _load_username_index():
    if os.path.exists(USERNAME_INDEX_PATH):
        with open(USERNAME_INDEX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def _save_username_index(idx):
    with open(USERNAME_INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)

def record_username(user_id, username, first_name=None):
    idx = _load_username_index()
    changed = False
    if username:
        key = username.lower()
        if idx.get(key) != user_id:
            idx[key] = user_id
            changed = True
    if changed:
        _save_username_index(idx)

def lookup_username(username):
    idx = _load_username_index()
    return idx.get(username.lower().lstrip("@"))

message_counters = {}
FACT_CHECK_INTERVAL = 5

def should_check_facts(user_id):
    count = message_counters.get(user_id, 0) + 1
    if count >= FACT_CHECK_INTERVAL:
        message_counters[user_id] = 0
        return True
    message_counters[user_id] = count
    return False

def is_banned(profile):
    return profile.get("banned", False)

def check_rate_limit(user_id, profile):
    if profile.get("unlimited"):
        return True
    today = str(date.today())
    if profile.get("message_date") != today:
        profile["message_date"] = today
        profile["message_count"] = 0
    limit = profile.get("message_limit", DEFAULT_MESSAGE_LIMIT)
    if profile.get("message_count", 0) >= limit:
        return False
    profile["message_count"] = profile.get("message_count", 0) + 1
    save_profile(user_id, profile)
    return True

def check_image_limit(user_id, profile):
    if profile.get("unlimited"):
        return True
    today = str(date.today())
    if profile.get("image_date") != today:
        profile["image_date"] = today
        profile["image_count"] = 0
    limit = profile.get("image_limit", get_setting("image_daily_limit_default"))
    if profile.get("image_count", 0) >= limit:
        return False
    profile["image_count"] = profile.get("image_count", 0) + 1
    save_profile(user_id, profile)
    return True

def check_video_limit(user_id, profile):
    if profile.get("unlimited"):
        return True
    today = str(date.today())
    if profile.get("video_date") != today:
        profile["video_date"] = today
        profile["video_count"] = 0
    limit = profile.get("video_limit", get_setting("video_daily_limit"))
    if profile.get("video_count", 0) >= limit:
        return False
    profile["video_count"] = profile.get("video_count", 0) + 1
    save_profile(user_id, profile)
    return True

def check_whois_limit(admin_profile, daily_limit):
    today = str(date.today())
    if admin_profile.get("whois_date") != today:
        admin_profile["whois_date"] = today
        admin_profile["whois_count"] = 0
    if admin_profile.get("whois_count", 0) >= daily_limit:
        return False
    admin_profile["whois_count"] = admin_profile.get("whois_count", 0) + 1
    return True

def add_saved_media(profile, media_type, value, chat_id=None):
    saved = profile.get("saved_media", [])
    item = {"type": media_type, "value": value, "date": str(date.today())}
    if chat_id is not None:
        item["chat_id"] = chat_id
    saved.append(item)
    profile["saved_media"] = saved[-MAX_SAVED_ITEMS:]