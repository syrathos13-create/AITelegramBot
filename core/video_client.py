import time
import os
import tempfile
from core.ai_client import client

VIDEO_MODEL = "veo-3.1-fast-generate-preview"

def generate_video_sync(prompt, duration_seconds):
    operation = client.models.generate_videos(
        model=VIDEO_MODEL,
        prompt=prompt,
        config={"duration_seconds": duration_seconds},
    )
    while not operation.done:
        time.sleep(10)
        operation = client.operations.get(operation)

    generated = operation.result.generated_videos[0]
    client.files.download(file=generated.video)

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp_path = tmp.name
    generated.video.save(tmp_path)

    with open(tmp_path, "rb") as f:
        data = f.read()
    os.remove(tmp_path)
    return data