import json
import io
import wave
from google import genai
from google.genai import types
from config import GEMINI_API_KEY
from core.user_data import users
from core.group_prompts import load_group_prompt

client = genai.Client(api_key=GEMINI_API_KEY)

TEXT_MODEL = "gemini-3.5-flash-lite"
TTS_MODEL = "gemini-3.1-flash-tts-preview"
IMAGE_MODEL = "gemini-2.5-flash-image"
AVAILABLE_VOICES = ["Kore", "Puck", "Enceladus", "Charon"]
DEFAULT_VOICE = "Kore"

CORE_FACT_KEYS = {"name", "city", "language", "age", "job"}

def read_system_prompt():
    with open("system_prompt.txt", "r", encoding="utf-8") as f:
        return f.read()

def extract_facts(user_text, current_profile):
    if not user_text:
        return {}
    prompt = f"""Вот текущий профиль пользователя (JSON): {json.dumps(current_profile, ensure_ascii=False)}

Новое сообщение пользователя: "{user_text}"

Проанализируй сообщение и найди ЛЮБЫЕ факты о самом пользователе — город/страна, язык,
профессия, хобби, животные, еда, музыка, возраст и т.д.

Отдельно обрати внимание на дату рождения: если пользователь упоминает, когда у него день
рождения (в любой форме), верни это отдельным полем "birthday" СТРОГО в формате "DD-MM"
(например "25-12"). Если год тоже назван — год не сохраняй, только день и месяц.

Верни ТОЛЬКО валидный JSON с новыми/обновлёнными парами ключ-значение (короткие английские ключи).
Если факт заменяет старый — верни новое значение.
Если фактов нет — верни пустой JSON: {{}}
Не пиши ничего кроме JSON."""

    try:
        response = client.models.generate_content(model=TEXT_MODEL, contents=prompt)
    except Exception:
        return {}

    raw = response.text.strip().replace("```json", "").replace("```", "").strip()
    try:
        new_facts = json.loads(raw)
        if isinstance(new_facts, dict):
            return new_facts
    except json.JSONDecodeError:
        pass
    return {}

def build_reply(user_id, profile, parts, chat_id=None):
    system_prompt = read_system_prompt()

    if chat_id:
        group_prompt = load_group_prompt(chat_id)
        if group_prompt:
            system_prompt += f"\n\nИнструкция для этой группы (переопределяет общие правила бота, если противоречит): {group_prompt}"

    custom_prompt = profile.get("custom_prompt")
    if custom_prompt:
        system_prompt += f"\n\nДополнительная инструкция специально для этого пользователя (важнее правил группы и общих правил, если противоречит): {custom_prompt}"

    core_facts = {k: v for k, v in profile.items() if k in CORE_FACT_KEYS}
    profile_info = f"Известные факты о пользователе: {json.dumps(core_facts, ensure_ascii=False)}"
    history_text = "\n".join(f"{m['role']}: {m['text']}" for m in users.get(user_id, []))

    language_instruction = (
        "\n\nВАЖНО: всегда отвечай строго на том языке, на котором написано ПОСЛЕДНЕЕ сообщение "
        "пользователя (то, что идёт прямо перед этой инструкцией) — даже если раньше в этом же "
        "разговоре использовался другой язык. Переключайся на новый язык сразу, без вопросов "
        "и без смешивания языков в одном ответе."
    )
    intro_text = f"{system_prompt}\n\n{profile_info}\n\nИстория переписки:\n{history_text}{language_instruction}"
    contents = [intro_text] + parts

    response = client.models.generate_content(
        model=TEXT_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            tools=[
                types.Tool(google_search=types.GoogleSearch()),
                types.Tool(url_context=types.UrlContext())
            ]
        )
    )
    return response.text

def generate_voice_audio(text, voice_name):
    response = client.models.generate_content(
        model=TTS_MODEL,
        contents=text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
                )
            )
        )
    )
    pcm_data = response.candidates[0].content.parts[0].inline_data.data

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(pcm_data)
    buffer.seek(0)
    buffer.name = "reply.wav"
    return buffer

def generate_image(prompt):
    response = client.models.generate_content(model=IMAGE_MODEL, contents=prompt)
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            return part.inline_data.data, part.inline_data.mime_type
    return None, None

def edit_image(image_bytes, mime_type, instruction):
    image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    response = client.models.generate_content(
        model=IMAGE_MODEL,
        contents=[instruction, image_part],
    )
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            return part.inline_data.data, part.inline_data.mime_type
    return None, None

def search_answer(prompt_text):
    response = client.models.generate_content(
        model=TEXT_MODEL,
        contents=prompt_text,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())]
        )
    )
    return response.text

def generate_docx_content(description):
    prompt = f"""Создай содержание документа Word по запросу: "{description}"

Верни ТОЛЬКО валидный JSON:
{{"title": "Заголовок", "sections": [{{"heading": "Название раздела", "text": "Текст раздела"}}]}}
Не пиши ничего кроме JSON."""
    response = client.models.generate_content(model=TEXT_MODEL, contents=prompt)
    raw = response.text.strip().replace("```json", "").replace("```", "").strip()
    return json.loads(raw)

def generate_pptx_content(description):
    prompt = f"""Создай содержание презентации PowerPoint по запросу: "{description}"

Верни ТОЛЬКО валидный JSON:
{{"title": "Заголовок", "slides": [{{"title": "Заголовок слайда", "bullets": ["пункт 1", "пункт 2"]}}]}}
Сделай 5-8 слайдов. Не пиши ничего кроме JSON."""
    response = client.models.generate_content(model=TEXT_MODEL, contents=prompt)
    raw = response.text.strip().replace("```json", "").replace("```", "").strip()
    return json.loads(raw)

def generate_table_content(description):
    prompt = f"""Создай таблицу по запросу: "{description}"

Верни ТОЛЬКО валидный JSON:
{{"title": "Название", "headers": ["Колонка1", "Колонка2"], "rows": [["значение1", "значение2"]]}}
Не пиши ничего кроме JSON."""
    response = client.models.generate_content(model=TEXT_MODEL, contents=prompt)
    raw = response.text.strip().replace("```json", "").replace("```", "").strip()
    return json.loads(raw)

def revise_structured_content(original_text, instruction, kind):
    formats = {
        "docx": '{"title": "...", "sections": [{"heading": "...", "text": "..."}]}',
        "pptx": '{"title": "...", "slides": [{"title": "...", "bullets": ["..."]}]}',
        "table": '{"title": "...", "headers": ["..."], "rows": [["..."]]}',
    }
    prompt = f"""Вот текущее содержимое документа:
{original_text}

Инструкция пользователя по изменению: "{instruction}"

Примени изменения и верни ТОЛЬКО валидный JSON в формате:
{formats[kind]}
Не пиши ничего кроме JSON."""
    response = client.models.generate_content(model=TEXT_MODEL, contents=prompt)
    raw = response.text.strip().replace("```json", "").replace("```", "").strip()
    return json.loads(raw)

def generate_drawing_instructions(description):
    prompt = f"""Пользователь просит нарисовать/начертить: "{description}"

Составь точный чертёж как список примитивных фигур (как в Paint). Используй координаты
в пикселях на холсте 800x600 (0,0 — левый верхний угол).

Верни ТОЛЬКО валидный JSON строго в этом формате:
{{
  "width": 800,
  "height": 600,
  "background": "white",
  "elements": [
    {{"type": "line", "x1": 100, "y1": 100, "x2": 300, "y2": 100, "color": "black", "width": 2}},
    {{"type": "rectangle", "x1": 50, "y1": 50, "x2": 200, "y2": 150, "color": "black", "width": 2}},
    {{"type": "circle", "x": 400, "y": 300, "r": 50, "color": "blue", "width": 2}},
    {{"type": "polygon", "points": [[100,400],[200,400],[150,300]], "color": "black", "width": 2, "fill": false}},
    {{"type": "text", "x": 110, "y": 410, "text": "A", "color": "black"}}
  ]
}}

Для треугольников/фигур из задачи используй "polygon" с точными координатами вершин,
а рядом подписывай вершины/углы через "text". Продумай координаты так, чтобы фигура была
геометрически осмысленной.
Не пиши ничего кроме JSON."""

    response = client.models.generate_content(model=TEXT_MODEL, contents=prompt)
    raw = response.text.strip().replace("```json", "").replace("```", "").strip()
    return json.loads(raw)