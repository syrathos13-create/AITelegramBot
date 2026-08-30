import re
import datetime
from google.genai import types
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from config import TELEGRAM_TOKEN

from core.ai_client import build_reply, extract_facts
from core.user_data import (
    get_history, load_profile, save_profile, users, MEMORY_LIMIT,
    should_check_facts, is_banned, check_rate_limit, mark_active, add_saved_media
)
from core.utils import send_error, send_reply
from core.group_utils import should_respond, strip_mention
from core.scheduler import check_daily_events, check_proactive_messages, check_scheduled_messages
from core.bot_settings import get_setting
from core.schedule_wizard import (
    get_wizard, clear_wizard, build_days_keyboard, build_content_keyboard,
    build_mode_keyboard, day_names_string, start_wizard, build_scheduled_text,
    build_scheduled_menu_keyboard, build_edit_field_keyboard,
    is_valid_day_month, is_valid_full_date,
    set_sched_action, get_sched_action, clear_sched_action
)
from core.scheduled_messages import (
    add_scheduled_message, update_scheduled_message, list_scheduled_messages,
    delete_scheduled_message, get_scheduled_message, toggle_scheduled_message,
    update_content_only, update_schedule_only
)
from core.i18n import t
from commands.commands import handle_command, COMMAND_PREFIX, handle_help_page_callback
from commands.admin_commands import is_admin, handle_admin_help_page_callback

def extract_youtube_url(text):
    match = re.search(r'(https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[\w-]+)', text or "")
    return match.group(1) if match else None

def rate_limited(update, user_id, profile):
    return not check_rate_limit(user_id, profile)

def bot_is_silent(update):
    return not get_setting("bot_enabled") and not is_admin(str(update.effective_user.id))

LIMIT_MSG = "⏳ You've reached your daily message limit. Try again tomorrow!"

def save_wizard_result(user_id, wiz):
    days = wiz["days"] if wiz["mode"] == "weekly" else set()
    if wiz["edit_index"] is not None:
        update_scheduled_message(
            user_id, wiz["edit_index"], wiz["mode"], days,
            wiz["day_month"], wiz["full_date"], wiz["repeat_count"], wiz["time"], wiz["text"], wiz["topic"]
        )
    else:
        add_scheduled_message(
            user_id, wiz["mode"], days,
            wiz["day_month"], wiz["full_date"], wiz["repeat_count"], wiz["time"], wiz["text"], wiz["topic"]
        )

def save_schedule_edit(user_id, wiz):
    days = wiz["days"] if wiz["mode"] == "weekly" else set()
    update_schedule_only(user_id, wiz["edit_index"], wiz["mode"], days, wiz["day_month"], wiz["full_date"], wiz["repeat_count"], wiz["time"])

def wizard_when_str(lang, wiz):
    if wiz["mode"] == "yearly":
        return wiz["day_month"]
    elif wiz["mode"] == "once":
        return wiz["full_date"]
    else:
        return day_names_string(lang, wiz["days"])

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_text = update.message.text or ""
    user_id = str(update.effective_user.id)

    # 1) Ожидание номера для действия из меню /scheduled
    sched_action = get_sched_action(user_id)
    if sched_action and update.effective_chat.type == "private":
        profile = load_profile(user_id)
        lang = profile.get("ui_lang", "en")

        if not raw_text.strip().isdigit():
            await update.message.reply_text(t("sched_invalid_number", lang))
            return
        idx = int(raw_text.strip()) - 1
        entry = get_scheduled_message(user_id, idx)
        if not entry:
            await update.message.reply_text(t("sched_invalid_number", lang))
            return

        action = sched_action["action"]
        clear_sched_action(user_id)

        if action == "pause":
            new_state = toggle_scheduled_message(user_id, idx)
            key = "toggle_scheduled_on" if new_state else "toggle_scheduled_off"
            await update.message.reply_text(t(key, lang, number=str(idx + 1)))
        elif action == "delete":
            delete_scheduled_message(user_id, idx)
            await update.message.reply_text(t("delete_scheduled_done", lang, number=str(idx + 1)))
        elif action == "change":
            keyboard = build_edit_field_keyboard(lang, idx)
            await update.message.reply_text(t("sched_choose_field", lang, number=str(idx + 1)), reply_markup=keyboard)
        return

    # 2) Шаги мастера /tips
    wiz = get_wizard(user_id)
    if wiz and update.effective_chat.type == "private":
        profile = load_profile(user_id)
        lang = profile.get("ui_lang", "en")

        if wiz["step"] == "date_dm":
            if not is_valid_day_month(raw_text.strip()):
                await update.message.reply_text(t("write_everyday_daymonth_invalid", lang))
                return
            wiz["day_month"] = raw_text.strip()
            wiz["step"] = "repeat"
            await update.message.reply_text(t("write_everyday_repeat_prompt", lang))
            return

        if wiz["step"] == "date_full":
            if not is_valid_full_date(raw_text.strip()):
                await update.message.reply_text(t("write_everyday_fulldate_invalid", lang))
                return
            wiz["full_date"] = raw_text.strip()
            wiz["repeat_count"] = None
            wiz["step"] = "time"
            await update.message.reply_text(t("write_everyday_time_prompt", lang))
            return

        if wiz["step"] == "repeat":
            if not raw_text.strip().isdigit():
                await update.message.reply_text(t("write_everyday_repeat_invalid", lang))
                return
            count = int(raw_text.strip())
            wiz["repeat_count"] = count if count > 0 else None
            wiz["step"] = "time"
            await update.message.reply_text(t("write_everyday_time_prompt", lang))
            return

        if wiz["step"] == "time":
            if not re.match(r'^([01]\d|2[0-3]):[0-5]\d$', raw_text.strip()):
                await update.message.reply_text(t("write_everyday_time_invalid", lang))
                return
            wiz["time"] = raw_text.strip()

            if wiz.get("edit_field") == "schedule":
                save_schedule_edit(user_id, wiz)
                await update.message.reply_text(t("write_everyday_confirm", lang, days=wizard_when_str(lang, wiz), time=wiz["time"]))
                clear_wizard(user_id)
                return

            wiz["step"] = "content"
            keyboard = build_content_keyboard(lang)
            await update.message.reply_text(t("write_everyday_content_prompt", lang), reply_markup=keyboard)
            return

        if wiz["step"] in ("awaiting_text", "awaiting_topic"):
            if wiz["step"] == "awaiting_text":
                wiz["text"] = raw_text.strip()
            else:
                wiz["topic"] = raw_text.strip()

            if wiz.get("edit_field") == "content":
                update_content_only(user_id, wiz["edit_index"], wiz["text"], wiz["topic"])
            else:
                save_wizard_result(user_id, wiz)

            await update.message.reply_text(t("write_everyday_confirm", lang, days=wizard_when_str(lang, wiz), time=wiz["time"] or "-"))
            clear_wizard(user_id)
            return

    user_text = strip_mention(raw_text, context.bot.username)

    if user_text.strip().startswith(COMMAND_PREFIX):
        await handle_command(update, context, user_text)
        return

    if bot_is_silent(update):
        return

    if not should_respond(update, context):
        return

    profile = load_profile(user_id)

    if is_banned(profile):
        return
    if rate_limited(update, user_id, profile):
        await update.message.reply_text(LIMIT_MSG)
        return

    if update.effective_chat.type == "private":
        mark_active(user_id, profile)

    history = get_history(user_id)
    history.append({"role": "user", "text": user_text})
    users[user_id] = history[-MEMORY_LIMIT:]

    birthday_just_set = False
    if should_check_facts(user_id):
        new_facts = extract_facts(user_text, profile)
        if new_facts:
            if "birthday" in new_facts and new_facts["birthday"] != profile.get("birthday"):
                birthday_just_set = True
            profile.update(new_facts)
            if birthday_just_set:
                profile["firstmessage"] = True
            save_profile(user_id, profile)

    parts = [user_text]
    youtube_url = extract_youtube_url(user_text)
    if youtube_url:
        parts.append(types.Part(file_data=types.FileData(file_uri=youtube_url)))

    try:
        reply_text = build_reply(user_id, profile, parts, chat_id=str(update.effective_chat.id))
    except Exception as e:
        await send_error(update, e)
        return

    users[user_id].append({"role": "assistant", "text": reply_text})
    users[user_id] = users[user_id][-MEMORY_LIMIT:]
    await send_reply(update, profile, reply_text)

    if birthday_just_set:
        lang = profile.get("ui_lang", "en")
        await update.message.reply_text(t("birthday_auto_confirm", lang, date=profile['birthday']))

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if bot_is_silent(update):
        return
    if not should_respond(update, context):
        return

    user_id = str(update.effective_user.id)
    profile = load_profile(user_id)

    if is_banned(profile):
        return
    if rate_limited(update, user_id, profile):
        await update.message.reply_text(LIMIT_MSG)
        return

    largest_photo = update.message.photo[-1]
    add_saved_media(profile, "photo", largest_photo.file_id)
    save_profile(user_id, profile)

    caption = strip_mention(update.message.caption or "", context.bot.username) or "Пользователь прислал фото без подписи."

    history = get_history(user_id)
    history.append({"role": "user", "text": f"[фото] {caption}"})
    users[user_id] = history[-MEMORY_LIMIT:]

    photo_file = await largest_photo.get_file()
    photo_bytes = await photo_file.download_as_bytearray()
    image_part = types.Part.from_bytes(data=bytes(photo_bytes), mime_type="image/jpeg")

    try:
        reply_text = build_reply(user_id, profile, [caption, image_part], chat_id=str(update.effective_chat.id))
    except Exception as e:
        await send_error(update, e)
        return

    users[user_id].append({"role": "assistant", "text": reply_text})
    users[user_id] = users[user_id][-MEMORY_LIMIT:]
    await send_reply(update, profile, reply_text)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if bot_is_silent(update):
        return
    if not should_respond(update, context):
        return

    user_id = str(update.effective_user.id)
    profile = load_profile(user_id)

    if is_banned(profile):
        return
    if rate_limited(update, user_id, profile):
        await update.message.reply_text(LIMIT_MSG)
        return

    add_saved_media(profile, "voice", update.message.voice.file_id)
    save_profile(user_id, profile)

    history = get_history(user_id)
    history.append({"role": "user", "text": "[голосовое сообщение]"})
    users[user_id] = history[-MEMORY_LIMIT:]

    voice_file = await update.message.voice.get_file()
    voice_bytes = await voice_file.download_as_bytearray()
    audio_part = types.Part.from_bytes(data=bytes(voice_bytes), mime_type="audio/ogg")

    try:
        reply_text = build_reply(user_id, profile, ["Ответь на голосовое сообщение пользователя.", audio_part], chat_id=str(update.effective_chat.id))
    except Exception as e:
        await send_error(update, e)
        return

    users[user_id].append({"role": "assistant", "text": reply_text})
    users[user_id] = users[user_id][-MEMORY_LIMIT:]
    await send_reply(update, profile, reply_text)

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if bot_is_silent(update):
        return
    if not should_respond(update, context):
        return

    user_id = str(update.effective_user.id)
    profile = load_profile(user_id)

    if is_banned(profile):
        return
    if rate_limited(update, user_id, profile):
        await update.message.reply_text(LIMIT_MSG)
        return

    add_saved_media(profile, "audio", update.message.audio.file_id)
    save_profile(user_id, profile)

    history = get_history(user_id)
    history.append({"role": "user", "text": "[аудиофайл]"})
    users[user_id] = history[-MEMORY_LIMIT:]

    await update.message.reply_text("🎵 Saved to your gallery!")

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if bot_is_silent(update):
        return
    if not should_respond(update, context):
        return

    user_id = str(update.effective_user.id)
    profile = load_profile(user_id)

    if is_banned(profile):
        return
    if rate_limited(update, user_id, profile):
        await update.message.reply_text(LIMIT_MSG)
        return

    add_saved_media(profile, "video", update.message.video.file_id)
    save_profile(user_id, profile)

    caption = strip_mention(update.message.caption or "", context.bot.username) or "Пользователь прислал видео без подписи."

    history = get_history(user_id)
    history.append({"role": "user", "text": f"[видео] {caption}"})
    users[user_id] = history[-MEMORY_LIMIT:]

    video_file = await update.message.video.get_file()
    video_bytes = await video_file.download_as_bytearray()
    video_part = types.Part.from_bytes(data=bytes(video_bytes), mime_type="video/mp4")

    try:
        reply_text = build_reply(user_id, profile, [caption, video_part], chat_id=str(update.effective_chat.id))
    except Exception as e:
        await send_error(update, e)
        return

    users[user_id].append({"role": "assistant", "text": reply_text})
    users[user_id] = users[user_id][-MEMORY_LIMIT:]
    await send_reply(update, profile, reply_text)

async def handle_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if bot_is_silent(update):
        return
    if not should_respond(update, context):
        return

    user_id = str(update.effective_user.id)
    profile = load_profile(user_id)

    if is_banned(profile):
        return
    if rate_limited(update, user_id, profile):
        await update.message.reply_text(LIMIT_MSG)
        return

    sticker = update.message.sticker
    emoji = sticker.emoji or "🙂"

    history = get_history(user_id)
    history.append({"role": "user", "text": f"[стикер {emoji}]"})
    users[user_id] = history[-MEMORY_LIMIT:]

    if sticker.is_animated or sticker.is_video:
        prompt_parts = [f"Пользователь прислал анимированный стикер с эмодзи {emoji}. Отреагируй на это коротко и по-дружески."]
    else:
        sticker_file = await sticker.get_file()
        sticker_bytes = await sticker_file.download_as_bytearray()
        image_part = types.Part.from_bytes(data=bytes(sticker_bytes), mime_type="image/webp")
        prompt_parts = [f"Пользователь прислал стикер (эмодзи: {emoji}). Отреагируй на его содержание коротко и по-дружески.", image_part]

    try:
        reply_text = build_reply(user_id, profile, prompt_parts, chat_id=str(update.effective_chat.id))
    except Exception as e:
        await send_error(update, e)
        return

    users[user_id].append({"role": "assistant", "text": reply_text})
    users[user_id] = users[user_id][-MEMORY_LIMIT:]
    await send_reply(update, profile, reply_text)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if bot_is_silent(update):
        return
    if not should_respond(update, context):
        return

    user_id = str(update.effective_user.id)
    profile = load_profile(user_id)

    if is_banned(profile):
        return
    if rate_limited(update, user_id, profile):
        await update.message.reply_text(LIMIT_MSG)
        return

    from core.document_client import read_docx, read_xlsx, read_pptx

    filename = update.message.document.file_name or ""
    doc_file = await update.message.document.get_file()
    file_bytes = await doc_file.download_as_bytearray()
    file_bytes = bytes(file_bytes)

    if filename.endswith(".docx"):
        extracted = read_docx(file_bytes)
    elif filename.endswith(".xlsx"):
        extracted = read_xlsx(file_bytes)
    elif filename.endswith(".pptx"):
        extracted = read_pptx(file_bytes)
    else:
        return

    caption = strip_mention(update.message.caption or "", context.bot.username) or "Прокомментируй содержимое этого документа, дай советы по улучшению."

    history = get_history(user_id)
    history.append({"role": "user", "text": f"[документ {filename}] {caption}"})
    users[user_id] = history[-MEMORY_LIMIT:]

    prompt = f"{caption}\n\nСодержимое документа:\n{extracted[:8000]}"

    try:
        reply_text = build_reply(user_id, profile, [prompt], chat_id=str(update.effective_chat.id))
    except Exception as e:
        await send_error(update, e)
        return

    users[user_id].append({"role": "assistant", "text": reply_text})
    users[user_id] = users[user_id][-MEMORY_LIMIT:]
    await send_reply(update, profile, reply_text)

async def handle_wizard_callback(update, context):
    query = update.callback_query
    user_id = str(query.from_user.id)
    profile = load_profile(user_id)
    lang = profile.get("ui_lang", "en")

    wiz = get_wizard(user_id)
    if not wiz:
        await query.answer()
        return

    data = query.data

    if data == "wizcancel":
        clear_wizard(user_id)
        await query.edit_message_text(t("write_everyday_cancelled", lang))
        await query.answer()
        return

    if data.startswith("wizmode:"):
        mode = data.split(":")[1]
        wiz["mode"] = mode
        if mode == "weekly":
            wiz["step"] = "days"
            keyboard = build_days_keyboard(lang, wiz["days"])
            await query.edit_message_text(t("write_everyday_days_prompt", lang), reply_markup=keyboard)
        elif mode == "yearly":
            wiz["step"] = "date_dm"
            await query.edit_message_text(t("write_everyday_daymonth_prompt", lang))
        else:
            wiz["step"] = "date_full"
            await query.edit_message_text(t("write_everyday_fulldate_prompt", lang))
        await query.answer()
        return

    if data.startswith("wizday:"):
        day = int(data.split(":")[1])
        if day in wiz["days"]:
            wiz["days"].remove(day)
        else:
            wiz["days"].add(day)
        keyboard = build_days_keyboard(lang, wiz["days"])
        await query.edit_message_reply_markup(reply_markup=keyboard)
        await query.answer()
        return

    if data == "wizdone":
        if not wiz["days"]:
            await query.answer(t("write_everyday_no_days", lang), show_alert=True)
            return
        wiz["step"] = "repeat"
        await query.edit_message_text(t("write_everyday_repeat_prompt", lang))
        await query.answer()
        return

    if data.startswith("wizcontent:"):
        choice = data.split(":")[1]
        if choice == "ai":
            wiz["text"] = None
            wiz["topic"] = None
            if wiz.get("edit_field") == "content":
                update_content_only(user_id, wiz["edit_index"], None, None)
            else:
                save_wizard_result(user_id, wiz)
            await query.edit_message_text(t("write_everyday_confirm", lang, days=wizard_when_str(lang, wiz), time=wiz["time"] or "-"))
            clear_wizard(user_id)
        elif choice == "topic":
            wiz["step"] = "awaiting_topic"
            await query.edit_message_text(t("write_everyday_topic_prompt", lang))
        else:
            wiz["step"] = "awaiting_text"
            await query.edit_message_text(t("write_everyday_text_prompt", lang))
        await query.answer()
        return

    await query.answer()

async def handle_scheduled_menu_callback(update, context):
    query = update.callback_query
    user_id = str(query.from_user.id)
    profile = load_profile(user_id)
    lang = profile.get("ui_lang", "en")
    data = query.data

    if data == "schednew":
        start_wizard(user_id)
        keyboard = build_mode_keyboard(lang)
        await query.edit_message_text(t("write_everyday_mode_prompt", lang), reply_markup=keyboard)
        await query.answer()
        return

    if data.startswith("schedmenu:"):
        action = data.split(":")[1]
        set_sched_action(user_id, action)
        prompt_key = {
            "change": "sched_enter_number_change",
            "pause": "sched_enter_number_pause",
            "delete": "sched_enter_number_delete",
        }[action]
        await query.edit_message_text(t(prompt_key, lang))
        await query.answer()
        return

    if data.startswith("schedfield:"):
        _, field, idx_str = data.split(":")
        idx = int(idx_str)
        entry = get_scheduled_message(user_id, idx)
        if not entry:
            await query.answer()
            return
        start_wizard(user_id, edit_index=idx, existing=entry, edit_field=field)
        if field == "schedule":
            keyboard = build_mode_keyboard(lang)
            await query.edit_message_text(t("write_everyday_mode_prompt", lang), reply_markup=keyboard)
        else:
            keyboard = build_content_keyboard(lang)
            await query.edit_message_text(t("write_everyday_content_prompt", lang), reply_markup=keyboard)
        await query.answer()
        return

    await query.answer()

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT, handle_message))
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
app.add_handler(MessageHandler(filters.VOICE, handle_voice))
app.add_handler(MessageHandler(filters.AUDIO, handle_audio))
app.add_handler(MessageHandler(filters.VIDEO, handle_video))
app.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))
app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
app.add_handler(CallbackQueryHandler(handle_help_page_callback, pattern="^helppage:"))
app.add_handler(CallbackQueryHandler(handle_admin_help_page_callback, pattern="^adminpage:"))
app.add_handler(CallbackQueryHandler(handle_scheduled_menu_callback, pattern="^sched"))
app.add_handler(CallbackQueryHandler(handle_wizard_callback, pattern="^wiz"))

app.job_queue.run_daily(check_daily_events, time=datetime.time(hour=9, minute=0))
app.job_queue.run_daily(check_proactive_messages, time=datetime.time(hour=18, minute=0))
app.job_queue.run_repeating(check_scheduled_messages, interval=60, first=0)

print("RoBerT0 запущен...")
app.run_polling()