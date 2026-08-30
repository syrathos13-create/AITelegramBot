from core.user_data import load_profile, save_profile

def _build_entry(mode, days, day_month, full_date, repeat_count, time_str, text, topic):
    return {
        "mode": mode,  # "weekly" | "yearly" | "once"
        "days": sorted(days) if days else [],
        "day_month": day_month,
        "full_date": full_date,
        "repeat_count": repeat_count,
        "sent_count": 0,
        "time": time_str,
        "text": text,
        "topic": topic,
        "enabled": True,
        "last_sent": None,
    }

def add_scheduled_message(user_id, mode, days, day_month, full_date, repeat_count, time_str, text=None, topic=None):
    profile = load_profile(user_id)
    scheduled = profile.get("scheduled_messages", [])
    scheduled.append(_build_entry(mode, days, day_month, full_date, repeat_count, time_str, text, topic))
    profile["scheduled_messages"] = scheduled
    save_profile(user_id, profile)

def update_scheduled_message(user_id, index, mode, days, day_month, full_date, repeat_count, time_str, text=None, topic=None):
    profile = load_profile(user_id)
    scheduled = profile.get("scheduled_messages", [])
    if 0 <= index < len(scheduled):
        old = scheduled[index]
        entry = _build_entry(mode, days, day_month, full_date, repeat_count, time_str, text, topic)
        entry["sent_count"] = old.get("sent_count", 0)
        entry["last_sent"] = old.get("last_sent")
        entry["enabled"] = old.get("enabled", True)
        scheduled[index] = entry
        profile["scheduled_messages"] = scheduled
        save_profile(user_id, profile)
        return True
    return False

def update_schedule_only(user_id, index, mode, days, day_month, full_date, repeat_count, time_str):
    """Меняет только дату/дни/время, не трогая содержание сообщения."""
    profile = load_profile(user_id)
    scheduled = profile.get("scheduled_messages", [])
    if 0 <= index < len(scheduled):
        entry = scheduled[index]
        entry["mode"] = mode
        entry["days"] = sorted(days) if days else []
        entry["day_month"] = day_month
        entry["full_date"] = full_date
        entry["repeat_count"] = repeat_count
        entry["time"] = time_str
        entry["sent_count"] = 0
        entry["last_sent"] = None
        entry["enabled"] = True
        profile["scheduled_messages"] = scheduled
        save_profile(user_id, profile)
        return True
    return False

def update_content_only(user_id, index, text, topic):
    """Меняет только содержание, не трогая расписание."""
    profile = load_profile(user_id)
    scheduled = profile.get("scheduled_messages", [])
    if 0 <= index < len(scheduled):
        scheduled[index]["text"] = text
        scheduled[index]["topic"] = topic
        profile["scheduled_messages"] = scheduled
        save_profile(user_id, profile)
        return True
    return False

def list_scheduled_messages(user_id):
    profile = load_profile(user_id)
    return profile.get("scheduled_messages", [])

def get_scheduled_message(user_id, index):
    scheduled = list_scheduled_messages(user_id)
    if 0 <= index < len(scheduled):
        return scheduled[index]
    return None

def delete_scheduled_message(user_id, index):
    profile = load_profile(user_id)
    scheduled = profile.get("scheduled_messages", [])
    if 0 <= index < len(scheduled):
        removed = scheduled.pop(index)
        profile["scheduled_messages"] = scheduled
        save_profile(user_id, profile)
        return removed
    return None

def toggle_scheduled_message(user_id, index):
    profile = load_profile(user_id)
    scheduled = profile.get("scheduled_messages", [])
    if 0 <= index < len(scheduled):
        scheduled[index]["enabled"] = not scheduled[index].get("enabled", True)
        profile["scheduled_messages"] = scheduled
        save_profile(user_id, profile)
        return scheduled[index]["enabled"]
    return None

def mark_sent(user_id, index, today_str, mode):
    profile = load_profile(user_id)
    scheduled = profile.get("scheduled_messages", [])
    if 0 <= index < len(scheduled):
        entry = scheduled[index]
        entry["last_sent"] = today_str
        entry["sent_count"] = entry.get("sent_count", 0) + 1
        if mode == "once":
            entry["enabled"] = False
        else:
            repeat_count = entry.get("repeat_count")
            if repeat_count and entry["sent_count"] >= repeat_count:
                entry["enabled"] = False
        profile["scheduled_messages"] = scheduled
        save_profile(user_id, profile)