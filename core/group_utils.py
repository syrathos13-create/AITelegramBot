def should_respond(update, context) -> bool:
    chat_type = update.effective_chat.type
    if chat_type == "private":
        return True

    bot_username = context.bot.username

    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        if update.message.reply_to_message.from_user.id == context.bot.id:
            return True

    text = update.message.text or update.message.caption or ""
    if bot_username and f"@{bot_username}".lower() in text.lower():
        return True

    return False

def strip_mention(text, bot_username):
    if not text or not bot_username:
        return text
    return text.replace(f"@{bot_username}", "").strip()