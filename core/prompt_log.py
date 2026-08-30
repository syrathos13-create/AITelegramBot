import os
from datetime import datetime

LOG_PATH = "prompt_changes.log"

def log_prompt_change(scope, chat_id, user_id, new_prompt):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = (
        f"[{timestamp}] scope={scope} chat_id={chat_id} changed_by={user_id}\n"
        f"{new_prompt}\n"
        f"{'-' * 40}\n"
    )
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(entry)

def get_recent_log(n=5):
    if not os.path.exists(LOG_PATH):
        return "No prompt changes logged yet."
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    entries = [e.strip() for e in content.strip().split("-" * 40) if e.strip()]
    recent = entries[-n:]
    return "\n\n".join(recent) if recent else "No prompt changes logged yet."