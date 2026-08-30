import io
import re
import asyncio
from core.ai_client import (
    AVAILABLE_VOICES, generate_image, search_answer, edit_image,
    generate_docx_content, generate_pptx_content,
    generate_table_content, revise_structured_content, generate_drawing_instructions
)
from core.paint_client import render_drawing
from core.document_client import create_docx, create_xlsx, create_pptx, read_docx, read_xlsx, read_pptx
from core.user_data import load_profile, save_profile, users, check_image_limit, add_saved_media, record_username, check_video_limit
from core.video_client import generate_video_sync
from core.bot_settings import get_setting
from core.utils import send_error
from core.group_prompts import save_group_prompt, delete_group_prompt
from core.prompt_log import log_prompt_change
from core.i18n import t
from core.help_ui import build_help_keyboard
from core.schedule_wizard import start_wizard, build_mode_keyboard, build_scheduled_text, build_scheduled_menu_keyboard
from core.scheduled_messages import list_scheduled_messages
from commands.admin_commands import handle_admin_command, ADMIN_HELP_PAGES

COMMAND_PREFIX = "/"

ADMIN_COMMAND_MAP = {
    "set_prompt": "prompt",
    "prompt_log": "promptlog",
    "active_users": "users",
    "send_message": "message",
    "bot_off": "off",
    "bot_on": "on",
    "bot_status": "status",
    "whois": "whois",
    "whois_limit": "whoislimit",
    "ban_user": "ban",
    "unban_user": "unban",
    "set_message_limit": "limit",
    "remove_message_limit": "unlimited",
    "set_image_limit": "imagelimit",
    "set_video_limit": "videolimit_user",
    "default_image_limit": "defaultimagelimit",
    "default_video_limit": "defaultvideolimit",
    "default_video_duration": "videoduration",
    "set_fact": "setfact",
    "delete_fact": "deletefact",
    "reset_user": "resetuser",
    "add_admin": "addadmin",
    "remove_admin": "removeadmin",
    "list_admins": "listadmins",
    "check_key": "checkkey",
}

HELP_PAGES = {
    "en": [
        """🤖 RoBerT0 commands — 💬 Chat & Voice

/mode text | voice | both — how I reply (default: text)

/voices — list available TTS voices

/voice <name> — pick your voice (e.g. /voice Puck)

/language en | uk — switch the language of these command messages""",

        """🤖 RoBerT0 commands — 🎨 Generation

/image <description> — generate a picture

/video <seconds> <description> — generate a video (takes 1-2 min)

/editimage <what to change> — reply to a photo to edit it

/draw <description> — draw an exact diagram (shapes, triangles, labeled text) like Paint""",

        """🤖 RoBerT0 commands — 📄 Documents

/docx <description> — generate a Word document

/pptx <description> — generate a PowerPoint presentation

/table <description> — generate an Excel spreadsheet

/editfile <instruction> — reply to a .docx/.xlsx/.pptx to revise its content""",

        """🤖 RoBerT0 commands — 🔍 Search

/find <product> — search reviews/info about something

/movie <mood/genre> — get movie or show recommendations

/song <name> — find a link to a song (I can't send audio files)""",

        """🤖 RoBerT0 commands — 🙋 Profile & Memory

/myprofile — see your basic info (name, city, language, etc.)

/memories — numbered list of everything I remember about you

/delete <number> — remove one remembered fact by its number

/personality <text> — customize how I behave just with you

/resetpersonality — remove that personal customization

/reset — clear your profile and conversation history

/whoami — see your own Telegram ID""",

        """🤖 RoBerT0 commands — 📦 Gallery

/savequote <text> — save a quote (or reply to any message to save it as-is)

/quote <number> — resend a saved item by its number

/gallery — see everything saved (photos, video, audio, voice notes, quotes)""",

        """🤖 RoBerT0 commands — 📅 Reminders

/firstmessage on | off — allow me to message you first (also enables occasional check-ins)

/birthday DD-MM — I'll send a personal birthday message every year

/tips — set up recurring messages (weekly days, yearly date, or a one-time date), time, and content

/scheduled — view your scheduled messages, or change/pause/delete them (buttons)""",

        """🤖 RoBerT0 commands — 👥 Groups

/groupprompt <text> — set a custom personality for this group (admins only)

/resetgroupprompt — remove it, back to default (admins only)

In groups, mention me (@bot_username) or reply to my message for a normal chat reply.
Commands work in groups without needing to mention me. Daily message limits apply everywhere.""",
    ],
    "uk": [
        """🤖 Команди RoBerT0 — 💬 Чат і голос

/mode text | voice | both — як я відповідаю (за замовчуванням: text)

/voices — список доступних голосів TTS

/voice <ім'я> — обрати свій голос (напр. /voice Puck)

/language en | uk — переключити мову цих командних повідомлень""",

        """🤖 Команди RoBerT0 — 🎨 Генерація

/image <опис> — згенерувати зображення

/video <секунди> <опис> — згенерувати відео (займає 1-2 хв)

/editimage <що змінити> — відповідай на фото, щоб відредагувати його

/draw <опис> — намалювати точну схему (фігури, трикутники, підписи) як у Paint""",

        """🤖 Команди RoBerT0 — 📄 Документи

/docx <опис> — згенерувати документ Word

/pptx <опис> — згенерувати презентацію PowerPoint

/table <опис> — згенерувати таблицю Excel

/editfile <інструкція> — відповідай на .docx/.xlsx/.pptx, щоб змінити вміст""",

        """🤖 Команди RoBerT0 — 🔍 Пошук

/find <товар> — знайти відгуки/інформацію про щось

/movie <настрій/жанр> — отримати рекомендації фільмів чи серіалів

/song <назва> — знайти посилання на пісню (аудіофайл надіслати не можу)""",

        """🤖 Команди RoBerT0 — 🙋 Профіль і пам'ять

/myprofile — базова інформація про тебе (ім'я, місто, мова тощо)

/memories — нумерований список усього, що я про тебе пам'ятаю

/delete <номер> — видалити один запам'ятований факт за номером

/personality <текст> — налаштувати мою поведінку лише з тобою

/resetpersonality — прибрати це персональне налаштування

/reset — очистити твій профіль та історію розмови

/whoami — дізнатись свій Telegram ID""",

        """🤖 Команди RoBerT0 — 📦 Галерея

/savequote <текст> — зберегти цитату (або відповідай на будь-яке повідомлення, щоб зберегти його як є)

/quote <номер> — переслати збережений елемент за номером

/gallery — переглянути все збережене (фото, відео, аудіо, голосові, цитати)""",

        """🤖 Команди RoBerT0 — 📅 Нагадування

/firstmessage on | off — дозволити мені писати першим (також вмикає періодичні повідомлення)

/birthday DD-MM — щороку надсилатиму особисте привітання з днем народження

/tips — налаштувати регулярні повідомлення (дні тижня, щорічна дата або одноразова дата), час і зміст

/scheduled — переглянути заплановані повідомлення, або змінити/призупинити/видалити (кнопками)""",

        """🤖 Команди RoBerT0 — 👥 Групи

/groupprompt <текст> — задати особливу поведінку для цієї групи (лише адміни)

/resetgroupprompt — прибрати, повернутись до стандартної (лише адміни)

У групах згадай мене (@bot_username) або відповідай на моє повідомлення для звичайної відповіді.
Команди працюють у групах без потреби згадувати мене. Денні ліміти діють всюди.""",
    ],
}

NON_FACT_KEYS = {
    "custom_prompt", "voice", "reply_mode", "reminders", "birthday",
    "firstmessage", "banned", "message_limit", "unlimited", "message_date",
    "message_count", "last_active", "last_proactive", "ui_lang",
    "image_date", "image_count", "image_limit", "saved_media",
    "whois_date", "whois_count", "video_date", "video_count", "video_limit",
    "scheduled_messages"
}
CORE_PROFILE_KEYS = {"name", "city", "language", "age", "job"}

async def handle_command(update, context, text: str):
    user_id = str(update.effective_user.id)
    parts = text[len(COMMAND_PREFIX):].split(maxsplit=1)
    if not parts:
        return
    cmd = parts[0].lower()
    arg_text = parts[1] if len(parts) > 1 else ""
    profile = load_profile(user_id)
    lang = profile.get("ui_lang", "en")

    record_username(user_id, update.effective_user.username, update.effective_user.first_name)

    if cmd == "help":
        pages = HELP_PAGES.get(lang, HELP_PAGES["en"])
        keyboard = build_help_keyboard(lang, 1, len(pages), "helppage")
        await update.message.reply_text(pages[0], reply_markup=keyboard)

    elif cmd == "admin_help":
        pages = ADMIN_HELP_PAGES.get(lang, ADMIN_HELP_PAGES["en"])
        keyboard = build_help_keyboard(lang, 1, len(pages), "adminpage")
        await update.message.reply_text(pages[0], reply_markup=keyboard)

    elif cmd == "language":
        choice = arg_text.strip().lower()
        if choice not in ("en", "uk"):
            await update.message.reply_text(t("language_usage", lang))
            return
        profile["ui_lang"] = choice
        save_profile(user_id, profile)
        key = "language_set_en" if choice == "en" else "language_set_uk"
        await update.message.reply_text(t(key, choice))

    elif cmd == "voices":
        await update.message.reply_text(t("voices_list", lang, voices=", ".join(AVAILABLE_VOICES)))

    elif cmd == "voice":
        if not arg_text:
            await update.message.reply_text(t("voice_usage", lang, voices=", ".join(AVAILABLE_VOICES)))
            return
        chosen = arg_text.strip().capitalize()
        if chosen not in AVAILABLE_VOICES:
            await update.message.reply_text(t("voice_unknown", lang, voices=", ".join(AVAILABLE_VOICES)))
            return
        profile["voice"] = chosen
        save_profile(user_id, profile)
        await update.message.reply_text(t("voice_set", lang, voice=chosen))

    elif cmd == "mode":
        choice = arg_text.strip().lower()
        if choice not in ("text", "voice", "both"):
            await update.message.reply_text(t("mode_usage", lang))
            return
        profile["reply_mode"] = choice
        save_profile(user_id, profile)
        await update.message.reply_text(t("mode_set", lang, mode=choice))

    elif cmd == "image":
        if not arg_text.strip():
            await update.message.reply_text(t("image_usage", lang))
            return
        if not check_image_limit(user_id, profile):
            await update.message.reply_text(t("image_limit_reached", lang))
            return
        await update.message.reply_text(t("image_generating", lang))
        try:
            image_bytes, mime_type = generate_image(arg_text.strip())
        except Exception as e:
            await send_error(update, e)
            return
        if image_bytes:
            photo_buffer = io.BytesIO(image_bytes)
            photo_buffer.name = "image.png"
            await update.message.reply_photo(photo=photo_buffer)
        else:
            await update.message.reply_text(t("image_fail", lang))

    elif cmd == "video":
        max_duration = get_setting("max_video_duration")
        parts_v = arg_text.strip().split(maxsplit=1)
        if len(parts_v) < 2 or not parts_v[0].isdigit():
            await update.message.reply_text(t("video_usage", lang, max=max_duration))
            return
        duration = int(parts_v[0])
        description = parts_v[1]
        if duration < 1 or duration > max_duration:
            await update.message.reply_text(t("video_duration_invalid", lang, max=max_duration))
            return
        if not check_video_limit(user_id, profile):
            await update.message.reply_text(t("video_limit_reached", lang))
            return
        await update.message.reply_text(t("video_generating", lang))
        try:
            video_bytes = await asyncio.to_thread(generate_video_sync, description, duration)
        except Exception as e:
            await send_error(update, e)
            return
        video_buffer = io.BytesIO(video_bytes)
        video_buffer.name = "video.mp4"
        await update.message.reply_video(video=video_buffer)

    elif cmd == "editimage":
        replied = update.message.reply_to_message
        if not replied or not replied.photo or not arg_text.strip():
            await update.message.reply_text(t("editimage_usage", lang))
            return
        photo_file = await replied.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        try:
            image_bytes, mime_type = edit_image(bytes(photo_bytes), "image/jpeg", arg_text.strip())
        except Exception as e:
            await send_error(update, e)
            return
        if image_bytes:
            buf = io.BytesIO(image_bytes)
            buf.name = "edited.png"
            await update.message.reply_photo(photo=buf)
        else:
            await update.message.reply_text(t("image_fail", lang))

    elif cmd == "draw":
        if not arg_text.strip():
            await update.message.reply_text(t("draw_usage", lang))
            return
        await update.message.reply_text(t("draw_working", lang))
        try:
            instructions = generate_drawing_instructions(arg_text.strip())
            buf = render_drawing(instructions)
        except Exception as e:
            await send_error(update, e)
            return
        await update.message.reply_photo(photo=buf)

    elif cmd == "docx":
        if not arg_text.strip():
            await update.message.reply_text(t("docx_usage", lang))
            return
        await update.message.reply_text(t("doc_generating", lang))
        try:
            data = generate_docx_content(arg_text.strip())
        except Exception as e:
            await send_error(update, e)
            return

        image_bytes = None
        if check_image_limit(user_id, profile):
            try:
                image_bytes, _ = generate_image(f"Illustration for a document about: {arg_text.strip()}")
            except Exception:
                image_bytes = None

        buf = create_docx(data["title"], data["sections"], image_bytes=image_bytes)
        await update.message.reply_document(document=buf)

    elif cmd == "pptx":
        if not arg_text.strip():
            await update.message.reply_text(t("pptx_usage", lang))
            return
        await update.message.reply_text(t("doc_generating", lang))
        try:
            data = generate_pptx_content(arg_text.strip())
        except Exception as e:
            await send_error(update, e)
            return

        image_bytes = None
        if check_image_limit(user_id, profile):
            try:
                image_bytes, _ = generate_image(f"Background image for a presentation about: {arg_text.strip()}, subtle, not too busy, works well behind text")
            except Exception:
                image_bytes = None

        buf = create_pptx(data["title"], data["slides"], image_bytes=image_bytes)
        await update.message.reply_document(document=buf)

    elif cmd == "table":
        if not arg_text.strip():
            await update.message.reply_text(t("table_usage", lang))
            return
        await update.message.reply_text(t("doc_generating", lang))
        try:
            data = generate_table_content(arg_text.strip())
            buf = create_xlsx(data["title"], data["headers"], data["rows"])
        except Exception as e:
            await send_error(update, e)
            return
        await update.message.reply_document(document=buf)

    elif cmd == "editfile":
        replied = update.message.reply_to_message
        if not replied or not replied.document or not arg_text.strip():
            await update.message.reply_text(t("editfile_usage", lang))
            return

        filename = replied.document.file_name or ""
        doc_file = await replied.document.get_file()
        file_bytes = await doc_file.download_as_bytearray()
        file_bytes = bytes(file_bytes)

        await update.message.reply_text(t("editfile_working", lang))

        try:
            if filename.endswith(".docx"):
                original_text = read_docx(file_bytes)
                data = revise_structured_content(original_text, arg_text.strip(), "docx")
                buf = create_docx(data["title"], data["sections"])
            elif filename.endswith(".xlsx"):
                original_text = read_xlsx(file_bytes)
                data = revise_structured_content(original_text, arg_text.strip(), "table")
                buf = create_xlsx(data["title"], data["headers"], data["rows"])
            elif filename.endswith(".pptx"):
                original_text = read_pptx(file_bytes)
                data = revise_structured_content(original_text, arg_text.strip(), "pptx")
                buf = create_pptx(data["title"], data["slides"])
            else:
                await update.message.reply_text(t("editfile_unsupported", lang))
                return
        except Exception as e:
            await send_error(update, e)
            return

        await update.message.reply_document(document=buf)

    elif cmd == "reset":
        save_profile(user_id, {})
        users[user_id] = []
        await update.message.reply_text(t("reset_done", lang))

    elif cmd == "personality":
        if not arg_text.strip():
            await update.message.reply_text(t("personality_usage", lang))
            return
        profile["custom_prompt"] = arg_text.strip()
        save_profile(user_id, profile)
        await update.message.reply_text(t("personality_set", lang))

    elif cmd == "resetpersonality":
        profile.pop("custom_prompt", None)
        save_profile(user_id, profile)
        await update.message.reply_text(t("resetpersonality_done", lang))

    elif cmd == "myprofile":
        visible = {k: v for k, v in profile.items() if k in CORE_PROFILE_KEYS}
        if not visible:
            await update.message.reply_text(t("myprofile_empty", lang))
        else:
            lines = "\n".join(f"• {k}: {v}" for k, v in visible.items())
            await update.message.reply_text(t("myprofile_lines", lang, lines=lines))

    elif cmd == "memories":
        visible = {k: v for k, v in profile.items() if k not in NON_FACT_KEYS}
        if not visible:
            await update.message.reply_text(t("memories_empty", lang))
            return
        lines = "\n".join(f"{i+1}. {k}: {v}" for i, (k, v) in enumerate(visible.items()))
        await update.message.reply_text(t("memories_list", lang, lines=lines))

    elif cmd == "delete":
        if not arg_text.strip().isdigit():
            await update.message.reply_text(t("delete_usage", lang))
            return
        visible = {k: v for k, v in profile.items() if k not in NON_FACT_KEYS}
        idx = int(arg_text.strip()) - 1
        keys_list = list(visible.keys())
        if 0 <= idx < len(keys_list):
            removed_key = keys_list[idx]
            del profile[removed_key]
            save_profile(user_id, profile)
            await update.message.reply_text(t("delete_removed", lang, key=removed_key))
        else:
            await update.message.reply_text(t("delete_invalid", lang))

    elif cmd == "find":
        if not arg_text.strip():
            await update.message.reply_text(t("find_usage", lang))
            return
        await update.message.reply_text(t("find_searching", lang))
        try:
            result = search_answer(
                f"Найди актуальную информацию и отзывы про: {arg_text.strip()}. "
                f"Кратко перечисли главные плюсы, минусы и общее впечатление пользователей."
            )
        except Exception as e:
            await send_error(update, e)
            return
        await update.message.reply_text(result)

    elif cmd == "movie":
        if not arg_text.strip():
            await update.message.reply_text(t("movie_usage", lang))
            return
        await update.message.reply_text(t("movie_looking", lang))
        try:
            result = search_answer(
                f"Посоветуй 3-5 фильмов или сериалов по запросу: {arg_text.strip()}. "
                f"Для каждого — короткое описание в 1-2 предложения и почему он подходит под запрос."
            )
        except Exception as e:
            await send_error(update, e)
            return
        await update.message.reply_text(result)

    elif cmd == "song":
        if not arg_text.strip():
            await update.message.reply_text(t("song_usage", lang))
            return
        await update.message.reply_text(t("song_searching", lang))
        try:
            result = search_answer(
                f"Найди ссылку на песню: {arg_text.strip()} (YouTube или Spotify). "
                f"Дай короткий ответ с названием исполнителя и ссылкой."
            )
        except Exception as e:
            await send_error(update, e)
            return
        await update.message.reply_text(result)

    elif cmd == "whoami":
        await update.message.reply_text(t("whoami_reply", lang, id=user_id))

    elif cmd == "savequote":
        replied = update.message.reply_to_message
        if replied:
            add_saved_media(profile, "quote_msg", replied.message_id, chat_id=replied.chat_id)
            save_profile(user_id, profile)
            await update.message.reply_text(t("savequote_msg_saved", lang))
            return
        if not arg_text.strip():
            await update.message.reply_text(t("savequote_usage", lang))
            return
        add_saved_media(profile, "quote", arg_text.strip())
        save_profile(user_id, profile)
        await update.message.reply_text(t("savequote_text_saved", lang))

    elif cmd == "quote":
        if not arg_text.strip().isdigit():
            await update.message.reply_text(t("quote_usage", lang))
            return
        saved = profile.get("saved_media", [])
        idx = int(arg_text.strip()) - 1
        if not (0 <= idx < len(saved)):
            await update.message.reply_text(t("quote_invalid", lang))
            return
        item = saved[idx]
        try:
            if item["type"] == "quote_msg":
                await context.bot.forward_message(
                    chat_id=update.effective_chat.id,
                    from_chat_id=item["chat_id"],
                    message_id=item["value"]
                )
            elif item["type"] == "quote":
                await update.message.reply_text(item["value"])
            elif item["type"] == "photo":
                await update.message.reply_photo(photo=item["value"])
            elif item["type"] == "audio":
                await update.message.reply_audio(audio=item["value"])
            elif item["type"] == "voice":
                await update.message.reply_voice(voice=item["value"])
            elif item["type"] == "video":
                await update.message.reply_video(video=item["value"])
        except Exception as e:
            await update.message.reply_text(t("quote_fail", lang, error=str(e)[:150]))

    elif cmd == "gallery":
        saved = profile.get("saved_media", [])
        if not saved:
            await update.message.reply_text(t("gallery_empty", lang))
            return
        lines = []
        for i, item in enumerate(saved):
            label = item["value"][:60] if item["type"] in ("quote",) else f"{item['type']} item"
            lines.append(f"{i+1}. [{item['type']}] {label} ({item['date']})")
        await update.message.reply_text(t("gallery_header", lang, lines="\n".join(lines)))

    elif cmd == "firstmessage":
        choice = arg_text.strip().lower()
        if choice not in ("on", "off"):
            await update.message.reply_text(t("firstmessage_usage", lang))
            return
        profile["firstmessage"] = (choice == "on")
        save_profile(user_id, profile)
        await update.message.reply_text(t("firstmessage_set", lang, state=choice.upper()))

    elif cmd == "birthday":
        date_str = arg_text.strip()
        if not re.match(r'^\d{2}-\d{2}$', date_str):
            await update.message.reply_text(t("birthday_usage", lang))
            return
        profile["birthday"] = date_str
        save_profile(user_id, profile)
        await update.message.reply_text(t("birthday_set", lang, date=date_str))

    elif cmd == "tips":
        if update.effective_chat.type != "private":
            await update.message.reply_text(t("write_everyday_dm_only", lang))
            return
        start_wizard(user_id)
        keyboard = build_mode_keyboard(lang)
        await update.message.reply_text(t("write_everyday_mode_prompt", lang), reply_markup=keyboard)

    elif cmd == "scheduled":
        scheduled = list_scheduled_messages(user_id)
        text = build_scheduled_text(lang, scheduled)
        keyboard = build_scheduled_menu_keyboard(lang)
        await update.message.reply_text(text, reply_markup=keyboard)

    elif cmd == "groupprompt":
        chat_type = update.effective_chat.type
        if chat_type not in ("group", "supergroup"):
            await update.message.reply_text(t("group_only", lang))
            return
        member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
        if member.status not in ("administrator", "creator"):
            await update.message.reply_text(t("group_admin_only_set", lang))
            return
        if not arg_text.strip():
            await update.message.reply_text(t("groupprompt_usage", lang))
            return
        save_group_prompt(update.effective_chat.id, arg_text.strip())
        log_prompt_change("group", update.effective_chat.id, user_id, arg_text.strip())
        await update.message.reply_text(t("groupprompt_set", lang))

    elif cmd == "resetgroupprompt":
        chat_type = update.effective_chat.type
        if chat_type not in ("group", "supergroup"):
            await update.message.reply_text(t("group_only", lang))
            return
        member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
        if member.status not in ("administrator", "creator"):
            await update.message.reply_text(t("group_admin_only_reset", lang))
            return
        delete_group_prompt(update.effective_chat.id)
        log_prompt_change("group", update.effective_chat.id, user_id, "(reset to default)")
        await update.message.reply_text(t("resetgroupprompt_done", lang))

    elif cmd in ADMIN_COMMAND_MAP:
        await handle_admin_command(update, context, ADMIN_COMMAND_MAP[cmd], arg_text)

    else:
        await update.message.reply_text(t("unknown_command", lang))

async def handle_help_page_callback(update, context):
    query = update.callback_query
    _, page_str = query.data.split(":")
    page = int(page_str)

    user_id = str(query.from_user.id)
    profile = load_profile(user_id)
    lang = profile.get("ui_lang", "en")

    pages = HELP_PAGES.get(lang, HELP_PAGES["en"])
    if page < 1 or page > len(pages):
        await query.answer()
        return

    keyboard = build_help_keyboard(lang, page, len(pages), "helppage")
    await query.edit_message_text(pages[page - 1], reply_markup=keyboard)
    await query.answer()