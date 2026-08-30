from core.ai_client import generate_voice_audio, DEFAULT_VOICE

async def send_error(update, e):
    print(f"[ERROR] {repr(e)}", flush=True)
    error_message = str(e)
    if "429" in error_message or "quota" in error_message.lower() or "RESOURCE_EXHAUSTED" in error_message:
        await update.message.reply_text("⚠️ Error: API quota/tokens exhausted. Please try again later.")
    elif "401" in error_message or "403" in error_message or "API_KEY" in error_message:
        await update.message.reply_text("⚠️ Error: API key issue. Please check the configuration.")
    else:
        await update.message.reply_text(f"⚠️ Something went wrong. Error: {error_message[:200]}")

async def send_reply(update, profile, reply_text):
    mode = profile.get("reply_mode", "text")

    if mode == "text":
        await update.message.reply_text(reply_text)
        return

    audio_buffer = None
    try:
        voice_name = profile.get("voice", DEFAULT_VOICE)
        audio_buffer = generate_voice_audio(reply_text, voice_name)
    except Exception:
        audio_buffer = None

    if mode == "voice":
        if audio_buffer:
            await update.message.reply_audio(audio=audio_buffer)
        else:
            await update.message.reply_text(reply_text)
    elif mode == "both":
        await update.message.reply_text(reply_text)
        if audio_buffer:
            await update.message.reply_audio(audio=audio_buffer)