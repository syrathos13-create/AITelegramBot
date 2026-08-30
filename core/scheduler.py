from datetime import date, datetime
from core.user_data import load_profile, save_profile, users, list_all_user_ids
from core.ai_client import build_reply
from core.scheduled_messages import mark_sent

INACTIVITY_DAYS = 3
COOLDOWN_DAYS = 3

def days_since(date_str):
    if not date_str:
        return None
    try:
        then = datetime.strptime(date_str, "%Y-%m-%d").date()
        return (date.today() - then).days
    except ValueError:
        return None

async def check_daily_events(context):
    """Теперь только день рождения — старые /remind перенесены в /tips (mode='once'/'yearly')."""
    today = date.today().strftime("%d-%m")

    for user_id in list_all_user_ids():
        profile = load_profile(user_id)
        if not profile.get("firstmessage"):
            continue

        if profile.get("birthday") == today:
            try:
                if user_id not in users:
                    users[user_id] = []
                prompt = (
                    "Сегодня день рождения этого пользователя! Напиши тёплое, искреннее "
                    "поздравление с днём рождения, пожелай, чтобы сбылись мечты, и упомяни "
                    "что-то из того, что ты о нём знаешь, чтобы поздравление было личным."
                )
                message = build_reply(user_id, profile, [prompt])
                await context.bot.send_message(chat_id=int(user_id), text=f"🎉 {message}")
            except Exception:
                pass

async def check_proactive_messages(context):
    for user_id in list_all_user_ids():
        profile = load_profile(user_id)
        if not profile.get("firstmessage"):
            continue

        inactive_days = days_since(profile.get("last_active"))
        if inactive_days is None or inactive_days < INACTIVITY_DAYS:
            continue

        cooldown = days_since(profile.get("last_proactive"))
        if cooldown is not None and cooldown < COOLDOWN_DAYS:
            continue

        try:
            if user_id not in users:
                users[user_id] = []
            prompt = (
                f"Ты давно не общался с этим пользователем ({inactive_days} дней). "
                "Напиши короткое, естественное сообщение, чтобы завязать разговор — "
                "например поздоровайся и спроси, как дела, или, если из истории переписки "
                "видно, о чём вы говорили в последний раз, мягко спроси об этом. "
                "Не будь навязчивым, звучи по-дружески и коротко."
            )
            message = build_reply(user_id, profile, [prompt])
            await context.bot.send_message(chat_id=int(user_id), text=message)
            profile["last_proactive"] = str(date.today())
            save_profile(user_id, profile)
        except Exception:
            pass

async def check_scheduled_messages(context):
    """Раз в минуту — три режима: weekly (дни недели), yearly (день-месяц каждый год), once (конкретная дата)."""
    now = datetime.now()
    weekday = now.isoweekday()
    current_time = now.strftime("%H:%M")
    today_str = now.strftime("%Y-%m-%d")
    today_dm = now.strftime("%d-%m")
    today_full = now.strftime("%d-%m-%Y")

    for user_id in list_all_user_ids():
        profile = load_profile(user_id)
        if not profile.get("firstmessage"):
            continue

        scheduled = profile.get("scheduled_messages", [])
        for i, entry in enumerate(scheduled):
            if not entry.get("enabled", True):
                continue
            if entry.get("time") != current_time:
                continue
            if entry.get("last_sent") == today_str:
                continue

            mode = entry.get("mode", "weekly")

            if mode == "weekly":
                if weekday not in entry.get("days", []):
                    continue
                repeat_count = entry.get("repeat_count")
                if repeat_count and entry.get("sent_count", 0) >= repeat_count:
                    continue
            elif mode == "yearly":
                if entry.get("day_month") != today_dm:
                    continue
                repeat_count = entry.get("repeat_count")
                if repeat_count and entry.get("sent_count", 0) >= repeat_count:
                    continue
            elif mode == "once":
                if entry.get("full_date") != today_full:
                    continue
            else:
                continue

            try:
                if entry.get("text"):
                    message = entry["text"]
                elif entry.get("topic"):
                    if user_id not in users:
                        users[user_id] = []
                    prompt = (
                        f"Напиши короткое дружеское сообщение пользователю на тему: \"{entry['topic']}\". "
                        "Сформулируй по-новому, живо, не как шаблон — учти, что ты о нём знаешь."
                    )
                    message = build_reply(user_id, profile, [prompt])
                else:
                    if user_id not in users:
                        users[user_id] = []
                    prompt = (
                        "Напиши короткое, дружеское сообщение пользователю просто чтобы начать "
                        "разговор сегодня, с учётом того, что ты о нём знаешь."
                    )
                    message = build_reply(user_id, profile, [prompt])
                await context.bot.send_message(chat_id=int(user_id), text=message)
                mark_sent(user_id, i, today_str, mode)
            except Exception:
                pass