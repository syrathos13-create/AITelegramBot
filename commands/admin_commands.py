from core.user_data import users, load_profile, save_profile, check_whois_limit, lookup_username
from core.prompt_log import log_prompt_change, get_recent_log
from core.i18n import t
from core.bot_settings import get_setting, set_setting
from core.help_ui import build_help_keyboard
from config import ADMIN_ID

ADMIN_HELP_PAGES = {
    "en": [
        """👑 Admin — 🌍 General & Control

/set_prompt <text> — change the bot's global system prompt

/prompt_log — show recent prompt change history

/active_users — active users in memory this session

/send_message <id> <text> — send a message to a user right now (or reply to their message)

/bot_off — turn the bot off (won't respond to anyone but admins)

/bot_on — turn the bot back on

/bot_status — check if the bot is on or off""",

        """👑 Admin — 🔎 User Lookup

/whois <username> — find a user's ID (or reply to their message)

/whois_limit <number> — set how many times /whois can be used per day""",

        """👑 Admin — 🚫 Moderation

/ban_user <id> — block a user

/unban_user <id> — unblock a user""",

        """👑 Admin — ⚙️ Limits

Per user (reply to their message, or pass their ID):
/set_message_limit <id> <number> — daily message limit
/remove_message_limit <id> — remove all their daily limits
/set_image_limit <id> <number> — daily image generation limit
/set_video_limit <id> <number> — daily video generation limit

Global defaults (apply to everyone without a personal override):
/default_image_limit <number>
/default_video_limit <number>
/default_video_duration <seconds>""",

        """👑 Admin — 🧠 Memory & Admins

/set_fact <id> <key> <value> — set/change one fact (e.g. their name)

/delete_fact <id> <key> — remove one fact

/reset_user <id> — wipe their entire profile and history

👑 Owner only:
/add_admin <id> — give someone admin access
/remove_admin <id> — remove their admin access
/list_admins — see who has admin access

💡 Tip: reply to the target user's message instead of typing their ID.""",
    ],
    "uk": [
        """👑 Адмін — 🌍 Загальні

/set_prompt <текст> — змінити глобальний системний промт бота

/prompt_log — показати історію змін промту

/active_users — активні користувачі в пам'яті цієї сесії

/send_message <id> <текст> — надіслати повідомлення користувачу прямо зараз (або відповіддю на його повідомлення)

/bot_off — вимкнути бота (не відповідатиме нікому крім адмінів)

/bot_on — увімкнути бота знову

/bot_status — перевірити, чи увімкнено бот""",

        """👑 Адмін — 🔎 Пошук користувача

/whois <username> — дізнатись ID користувача (або відповіддю на повідомлення)

/whois_limit <число> — встановити скільки разів на день можна викликати /whois""",

        """👑 Адмін — 🚫 Модерація

/ban_user <id> — заблокувати користувача

/unban_user <id> — розблокувати користувача""",

        """👑 Адмін — ⚙️ Ліміти

Персонально (відповіддю на повідомлення, або з ID):
/set_message_limit <id> <число> — денний ліміт повідомлень
/remove_message_limit <id> — прибрати всі особисті ліміти
/set_image_limit <id> <число> — денний ліміт генерації зображень
/set_video_limit <id> <число> — денний ліміт генерації відео

Глобальні стандартні (діють на всіх без персонального налаштування):
/default_image_limit <число>
/default_video_limit <число>
/default_video_duration <секунди>""",

        """👑 Адмін — 🧠 Пам'ять і адміни

/set_fact <id> <ключ> <значення> — встановити/змінити один факт (напр. ім'я)

/delete_fact <id> <ключ> — видалити один факт

/reset_user <id> — повністю очистити профіль та історію

👑 Лише власник:
/add_admin <id> — надати комусь права адміна
/remove_admin <id> — прибрати права адміна
/list_admins — переглянути, у кого є права адміна

💡 Порада: відповідай на повідомлення користувача замість введення ID.""",
    ],
}

def is_owner(user_id: str) -> bool:
    return user_id == str(ADMIN_ID)

def is_admin(user_id: str) -> bool:
    if is_owner(user_id):
        return True
    return user_id in get_setting("extra_admins")

def resolve_target_id(update, arg_text):
    if arg_text.strip():
        return arg_text.strip().split()[0]
    if update.message.reply_to_message:
        return str(update.message.reply_to_message.from_user.id)
    return None

def resolve_target_and_rest(update, arg_text):
    if update.message.reply_to_message:
        return str(update.message.reply_to_message.from_user.id), arg_text.strip()
    parts = arg_text.strip().split(maxsplit=1)
    if len(parts) < 1:
        return None, ""
    target_id = parts[0]
    rest = parts[1] if len(parts) > 1 else ""
    return target_id, rest

async def handle_admin_command(update, context, subcmd: str, arg_text: str):
    user_id = str(update.effective_user.id)

    if not is_admin(user_id):
        await update.message.reply_text("This command is for bot admins only.")
        return

    admin_profile = load_profile(user_id)
    lang = admin_profile.get("ui_lang", "en")

    if subcmd == "prompt":
        if not arg_text.strip():
            await update.message.reply_text(t("admin_prompt_usage", lang))
            return
        with open("system_prompt.txt", "w", encoding="utf-8") as f:
            f.write(arg_text.strip())
        log_prompt_change("global", "N/A", user_id, arg_text.strip())
        await update.message.reply_text(t("admin_prompt_updated", lang))

    elif subcmd == "promptlog":
        recent = get_recent_log(5)
        await update.message.reply_text(t("admin_promptlog_header", lang, recent=recent))

    elif subcmd == "users":
        count = len(users)
        await update.message.reply_text(t("admin_users_count", lang, count=count))

    elif subcmd == "message":
        target_id, text_to_send = resolve_target_and_rest(update, arg_text)
        if not target_id or not text_to_send.strip():
            await update.message.reply_text(t("admin_message_usage", lang))
            return
        try:
            await context.bot.send_message(chat_id=int(target_id), text=text_to_send.strip())
            await update.message.reply_text(t("admin_message_sent", lang, id=target_id))
        except Exception as e:
            await update.message.reply_text(t("admin_message_failed", lang, error=str(e)[:200]))

    elif subcmd == "off":
        set_setting("bot_enabled", False)
        await update.message.reply_text(t("admin_off_done", lang))

    elif subcmd == "on":
        set_setting("bot_enabled", True)
        await update.message.reply_text(t("admin_on_done", lang))

    elif subcmd == "status":
        status_key = "admin_status_on" if get_setting("bot_enabled") else "admin_status_off"
        await update.message.reply_text(t(status_key, lang))

    elif subcmd == "whois":
        daily_limit = get_setting("whois_daily_limit")
        if not check_whois_limit(admin_profile, daily_limit):
            save_profile(user_id, admin_profile)
            await update.message.reply_text(t("admin_whois_limit_reached", lang, limit=daily_limit))
            return
        save_profile(user_id, admin_profile)

        if update.message.reply_to_message:
            u = update.message.reply_to_message.from_user
            await update.message.reply_text(t("admin_whois_found", lang, name=u.first_name, username=u.username or "no username", id=u.id))
            return

        username = arg_text.strip().lstrip("@")
        if not username:
            await update.message.reply_text(t("admin_whois_usage", lang))
            return

        found_id = lookup_username(username)
        if found_id:
            await update.message.reply_text(t("admin_whois_found", lang, name=f"@{username}", username=username, id=found_id))
            return

        try:
            chat = await context.bot.get_chat(f"@{username}")
            await update.message.reply_text(t("admin_whois_found", lang, name=chat.first_name, username=chat.username, id=chat.id))
        except Exception:
            await update.message.reply_text(t("admin_whois_notfound", lang))

    elif subcmd == "whoislimit":
        if not arg_text.strip().isdigit():
            current = get_setting("whois_daily_limit")
            await update.message.reply_text(t("admin_whoislimit_usage", lang, current=current))
            return
        set_setting("whois_daily_limit", int(arg_text.strip()))
        await update.message.reply_text(t("admin_whoislimit_set", lang, number=arg_text.strip()))

    elif subcmd == "ban":
        target_id = resolve_target_id(update, arg_text)
        if not target_id:
            await update.message.reply_text(t("admin_ban_usage", lang))
            return
        profile = load_profile(target_id)
        profile["banned"] = True
        save_profile(target_id, profile)
        await update.message.reply_text(t("admin_ban_done", lang, id=target_id))

    elif subcmd == "unban":
        target_id = resolve_target_id(update, arg_text)
        if not target_id:
            await update.message.reply_text(t("admin_unban_usage", lang))
            return
        profile = load_profile(target_id)
        profile["banned"] = False
        save_profile(target_id, profile)
        await update.message.reply_text(t("admin_unban_done", lang, id=target_id))

    elif subcmd == "limit":
        target_id, rest = resolve_target_and_rest(update, arg_text)
        if not target_id or not rest.strip().isdigit():
            await update.message.reply_text(t("admin_limit_usage", lang))
            return
        profile = load_profile(target_id)
        profile["message_limit"] = int(rest.strip())
        profile["unlimited"] = False
        save_profile(target_id, profile)
        await update.message.reply_text(t("admin_limit_done", lang, id=target_id, number=rest.strip()))

    elif subcmd == "unlimited":
        target_id = resolve_target_id(update, arg_text)
        if not target_id:
            await update.message.reply_text(t("admin_unlimited_usage", lang))
            return
        profile = load_profile(target_id)
        profile["unlimited"] = True
        save_profile(target_id, profile)
        await update.message.reply_text(t("admin_unlimited_done", lang, id=target_id))

    elif subcmd == "imagelimit":
        target_id, rest = resolve_target_and_rest(update, arg_text)
        if not target_id or not rest.strip().isdigit():
            await update.message.reply_text(t("admin_setimagelimit_usage", lang))
            return
        profile = load_profile(target_id)
        profile["image_limit"] = int(rest.strip())
        save_profile(target_id, profile)
        await update.message.reply_text(t("admin_setimagelimit_done", lang, id=target_id, number=rest.strip()))

    elif subcmd == "videolimit_user":
        target_id, rest = resolve_target_and_rest(update, arg_text)
        if not target_id or not rest.strip().isdigit():
            await update.message.reply_text(t("admin_setvideolimit_usage", lang))
            return
        profile = load_profile(target_id)
        profile["video_limit"] = int(rest.strip())
        save_profile(target_id, profile)
        await update.message.reply_text(t("admin_setvideolimit_done", lang, id=target_id, number=rest.strip()))

    elif subcmd == "defaultimagelimit":
        if not arg_text.strip().isdigit():
            current = get_setting("image_daily_limit_default")
            await update.message.reply_text(t("admin_defaultimagelimit_usage", lang, current=current))
            return
        set_setting("image_daily_limit_default", int(arg_text.strip()))
        await update.message.reply_text(t("admin_defaultimagelimit_done", lang, number=arg_text.strip()))

    elif subcmd == "defaultvideolimit":
        if not arg_text.strip().isdigit():
            current = get_setting("video_daily_limit")
            await update.message.reply_text(t("admin_videolimit_usage", lang, current=current))
            return
        set_setting("video_daily_limit", int(arg_text.strip()))
        await update.message.reply_text(t("admin_videolimit_set", lang, number=arg_text.strip()))

    elif subcmd == "videoduration":
        if not arg_text.strip().isdigit():
            current = get_setting("max_video_duration")
            await update.message.reply_text(t("admin_videoduration_usage", lang, current=current))
            return
        set_setting("max_video_duration", int(arg_text.strip()))
        await update.message.reply_text(t("admin_videoduration_set", lang, number=arg_text.strip()))

    elif subcmd == "setfact":
        target_id, rest = resolve_target_and_rest(update, arg_text)
        rest_parts = rest.split(maxsplit=1)
        if not target_id or len(rest_parts) < 2:
            await update.message.reply_text(t("admin_setfact_usage", lang))
            return
        key, value = rest_parts[0], rest_parts[1]
        profile = load_profile(target_id)
        profile[key] = value
        save_profile(target_id, profile)
        await update.message.reply_text(t("admin_setfact_done", lang, key=key, value=value, id=target_id))

    elif subcmd == "deletefact":
        target_id, rest = resolve_target_and_rest(update, arg_text)
        key = rest.strip()
        if not target_id or not key:
            await update.message.reply_text(t("admin_deletefact_usage", lang))
            return
        profile = load_profile(target_id)
        if key in profile:
            del profile[key]
            save_profile(target_id, profile)
            await update.message.reply_text(t("admin_deletefact_done", lang, key=key, id=target_id))
        else:
            await update.message.reply_text(t("admin_deletefact_notfound", lang, id=target_id, key=key))

    elif subcmd == "resetuser":
        target_id = resolve_target_id(update, arg_text)
        if not target_id:
            await update.message.reply_text(t("admin_resetuser_usage", lang))
            return
        save_profile(target_id, {})
        users[target_id] = []
        await update.message.reply_text(t("admin_resetuser_done", lang, id=target_id))

    elif subcmd == "addadmin":
        if not is_owner(user_id):
            await update.message.reply_text(t("owner_only", lang))
            return
        target_id = resolve_target_id(update, arg_text)
        if not target_id:
            await update.message.reply_text(t("addadmin_usage", lang))
            return
        admins = get_setting("extra_admins")
        if target_id not in admins:
            admins.append(target_id)
            set_setting("extra_admins", admins)
        await update.message.reply_text(t("addadmin_done", lang, id=target_id))

    elif subcmd == "removeadmin":
        if not is_owner(user_id):
            await update.message.reply_text(t("owner_only", lang))
            return
        target_id = resolve_target_id(update, arg_text)
        if not target_id:
            await update.message.reply_text(t("removeadmin_usage", lang))
            return
        admins = get_setting("extra_admins")
        if target_id in admins:
            admins.remove(target_id)
            set_setting("extra_admins", admins)
        await update.message.reply_text(t("removeadmin_done", lang, id=target_id))

    elif subcmd == "listadmins":
        if not is_owner(user_id):
            await update.message.reply_text(t("owner_only", lang))
            return
        admins = get_setting("extra_admins")
        admins_text = "\n".join(f"• {a}" for a in admins) if admins else t("listadmins_none", lang)
        await update.message.reply_text(t("listadmins_header", lang, owner=ADMIN_ID, admins=admins_text))

    else:
        await update.message.reply_text(t("admin_unknown", lang))

async def handle_admin_help_page_callback(update, context):
    query = update.callback_query
    user_id = str(query.from_user.id)

    if not is_admin(user_id):
        await query.answer("Admins only", show_alert=True)
        return

    _, page_str = query.data.split(":")
    page = int(page_str)

    profile = load_profile(user_id)
    lang = profile.get("ui_lang", "en")

    pages = ADMIN_HELP_PAGES.get(lang, ADMIN_HELP_PAGES["en"])
    if page < 1 or page > len(pages):
        await query.answer()
        return

    keyboard = build_help_keyboard(lang, page, len(pages), "adminpage")
    await query.edit_message_text(pages[page - 1], reply_markup=keyboard)
    await query.answer()