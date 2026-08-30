from telegram import InlineKeyboardButton, InlineKeyboardMarkup

CATEGORY_LABELS = {
    "en": ["💬 Chat & Voice", "🎨 Generation", "📄 Documents", "🔍 Search", "🙋 Profile & Memory", "📦 Gallery", "📅 Reminders", "👥 Groups"],
    "uk": ["💬 Чат і голос", "🎨 Генерація", "📄 Документи", "🔍 Пошук", "🙋 Профіль і пам'ять", "📦 Галерея", "📅 Нагадування", "👥 Групи"],
}

ADMIN_CATEGORY_LABELS = {
    "en": ["🌍 General & Control", "🔎 User Lookup", "🚫 Moderation", "⚙️ Limits", "🧠 Memory & Admins"],
    "uk": ["🌍 Загальні", "🔎 Пошук користувача", "🚫 Модерація", "⚙️ Ліміти", "🧠 Пам'ять і адміни"],
}

NAV_LABELS = {
    "en": {"back": "◀️ Back", "next": "Next ▶️"},
    "uk": {"back": "◀️ Назад", "next": "Далі ▶️"},
}

def build_help_keyboard(lang, current_page, total_pages, prefix):
    labels_map = CATEGORY_LABELS if prefix == "helppage" else ADMIN_CATEGORY_LABELS
    labels = labels_map.get(lang, labels_map["en"])
    nav = NAV_LABELS.get(lang, NAV_LABELS["en"])

    rows = []
    row = []
    for i, label in enumerate(labels, start=1):
        text = f"• {label}" if i == current_page else label
        row.append(InlineKeyboardButton(text, callback_data=f"{prefix}:{i}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    nav_row = []
    if current_page > 1:
        nav_row.append(InlineKeyboardButton(nav["back"], callback_data=f"{prefix}:{current_page-1}"))
    if current_page < total_pages:
        nav_row.append(InlineKeyboardButton(nav["next"], callback_data=f"{prefix}:{current_page+1}"))
    if nav_row:
        rows.append(nav_row)

    return InlineKeyboardMarkup(rows)