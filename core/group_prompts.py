import os

GROUP_PROMPTS_DIR = "group_prompts"
os.makedirs(GROUP_PROMPTS_DIR, exist_ok=True)

def group_prompt_path(chat_id):
    return os.path.join(GROUP_PROMPTS_DIR, f"{chat_id}.txt")

def load_group_prompt(chat_id):
    path = group_prompt_path(chat_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return None

def save_group_prompt(chat_id, text):
    with open(group_prompt_path(chat_id), "w", encoding="utf-8") as f:
        f.write(text)

def delete_group_prompt(chat_id):
    path = group_prompt_path(chat_id)
    if os.path.exists(path):
        os.remove(path)