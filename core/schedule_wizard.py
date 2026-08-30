from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from core.i18n import t

DAY_NAMES = {
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "uk": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"],
}

wizard_state = {}
sched_action_state = {}  # user_id -> {"action": "change"|"pause"|"delete"}

def is_valid_day_month(dm_str):
    try:
        datetime.strptime(f"{dm_str}-2000", "%d-%m-%Y")  # 2000 — високосный, разрешает 29-02
        return True
    except ValueError:
        return False

def is_valid_full_date(date_str):
    try:
        datetime.strptime(date_str, "%d-%m-%Y")
        return True
    except ValueError:
        return False

def start_wizard(user_id, edit_index=None, existing=None, edit_field=None):
    """edit_field: None (новая запись/полное изменение), 'schedule' (только дата/время), 'content' (только текст)."""
    if existing:
        wizard_state[user_id] = {
            "step": "mode",
            "mode": existing.get("mode", "weekly"),
            "days": set(existing.get("days", [])),
            "day_month": existing.get("day_month"),
            "full_date": existing.get("full_date"),
            "repeat_count": existing.get("repeat_count"),
            "time": existing.get("time"),
            "text": existing.get("text"),
            "topic": existing.get("topic"),
            "edit_index": edit_index,
            "edit_field": edit_field,
        }
    else:
        wizard_state[user_id] = {
            "step": "mode",
            "mode": None,
            "days": set(),
            "day_month": None,
            "full_date": None,
            "repeat_count": None,
            "time": None,
            "text": None,
            "topic": None,
            "edit_index": None,
            "edit_field": None,
        }

def get_wizard(user_id):
    return wizard_state.get(user_id)

def clear_wizard(user_id):
    wizard_state.pop(user_id, None)

def set_sched_action(user_id, action):
    sched_action_state[user_id] = {"action": action}

def get_sched_action(user_id):
    return sched_action_state.get(user_id)

def clear_sched_action(user_id):
    sched_action_state.pop(user_id, None)

def build_mode_keyboard(lang):
    if lang == "uk":
        weekly = "📅 Щотижня (обрати дні)"
        yearly = "🎉 Щороку (той самий день)"
        once = "🗓 Один раз (конкретна дата)"
    else:
        weekly = "📅 Weekly (choose days)"
        yearly = "🎉 Yearly (same day every year)"
        once = "🗓 Once (specific date)"
    rows = [
        [InlineKeyboardButton(weekly, callback_data="wizmode:weekly")],
        [InlineKeyboardButton(yearly, callback_data="wizmode:yearly")],
        [InlineKeyboardButton(once, callback_data="wizmode:once")],
    ]
    return InlineKeyboardMarkup(rows)

def build_days_keyboard(lang, selected_days):
    names = DAY_NAMES.get(lang, DAY_NAMES["en"])
    rows = []
    row = []
    for i, name in enumerate(names, start=1):
        mark = "✅" if i in selected_days else "❌"
        row.append(InlineKeyboardButton(f"{mark} {name}", callback_data=f"wizday:{i}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    done_label = "▶️ Done" if lang == "en" else "▶️ Готово"
    cancel_label = "✖️ Cancel" if lang == "en" else "✖️ Скасувати"
    rows.append([
        InlineKeyboardButton(done_label, callback_data="wizdone"),
        InlineKeyboardButton(cancel_label, callback_data="wizcancel"),
    ])
    return InlineKeyboardMarkup(rows)

def build_content_keyboard(lang):
    if lang == "uk":
        custom = "✍️ Напишу сам"
        topic = "🎯 Дай тему — нейромережа сама напише"
        ai = "🤖 Хай нейромережа сама вирішить"
    else:
        custom = "✍️ Write it myself"
        topic = "🎯 Give a topic — AI writes around it"
        ai = "🤖 Let AI decide freely"
    rows = [
        [InlineKeyboardButton(custom, callback_data="wizcontent:custom")],
        [InlineKeyboardButton(topic, callback_data="wizcontent:topic")],
        [InlineKeyboardButton(ai, callback_data="wizcontent:ai")],
    ]
    return InlineKeyboardMarkup(rows)

def day_names_string(lang, days):
    names = DAY_NAMES.get(lang, DAY_NAMES["en"])
    return ", ".join(names[d - 1] for d in sorted(days))

def when_string(lang, entry):
    mode = entry.get("mode")
    if mode == "yearly":
        s = entry.get("day_month", "?")
        rc = entry.get("repeat_count")
        return f"{s} ({t('sched_yearly_label', lang)})" + (f" x{rc}" if rc else "")
    elif mode == "once":
        return entry.get("full_date", "?")
    else:
        s = day_names_string(lang, entry.get("days", []))
        rc = entry.get("repeat_count")
        return s + (f" (x{rc})" if rc else "")

def build_scheduled_text(lang, scheduled):
    if not scheduled:
        return t("scheduled_empty", lang)
    lines = []
    for i, entry in enumerate(scheduled):
        status = t("scheduled_status_on", lang) if entry.get("enabled", True) else t("scheduled_status_off", lang)
        when = when_string(lang, entry)
        if entry.get("text"):
            content = t("scheduled_type_custom", lang, text=entry["text"][:50])
        elif entry.get("topic"):
            content = t("scheduled_type_topic", lang, topic=entry["topic"][:50])
        else:
            content = t("scheduled_type_ai", lang)
        lines.append(f"{i+1}. {status} — {when} @ {entry['time']}\n   {content}")
    return t("scheduled_list", lang, lines="\n".join(lines))

def build_scheduled_menu_keyboard(lang):
    rows = [
        [InlineKeyboardButton(t("sched_change_button", lang), callback_data="schedmenu:change")],
        [InlineKeyboardButton(t("sched_pause_button", lang), callback_data="schedmenu:pause")],
        [InlineKeyboardButton(t("sched_delete_button", lang), callback_data="schedmenu:delete")],
        [InlineKeyboardButton(t("sched_new_button", lang), callback_data="schednew")],
    ]
    return InlineKeyboardMarkup(rows)

def build_edit_field_keyboard(lang, idx):
    rows = [
        [InlineKeyboardButton(t("sched_field_schedule", lang), callback_data=f"schedfield:schedule:{idx}")],
        [InlineKeyboardButton(t("sched_field_content", lang), callback_data=f"schedfield:content:{idx}")],
    ]
    return InlineKeyboardMarkup(rows)