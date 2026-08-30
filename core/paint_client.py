import io
from PIL import Image, ImageDraw, ImageFont

def render_drawing(instructions):
    width = instructions.get("width", 800)
    height = instructions.get("height", 600)
    background = instructions.get("background", "white")

    img = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except Exception:
        font = ImageFont.load_default()

    for el in instructions.get("elements", []):
        etype = el.get("type")
        color = el.get("color", "black")

        if etype == "line":
            draw.line([(el["x1"], el["y1"]), (el["x2"], el["y2"])], fill=color, width=el.get("width", 2))
        elif etype == "rectangle":
            draw.rectangle([(el["x1"], el["y1"]), (el["x2"], el["y2"])], outline=color, width=el.get("width", 2))
        elif etype == "circle":
            x, y, r = el["x"], el["y"], el["r"]
            draw.ellipse([(x - r, y - r), (x + r, y + r)], outline=color, width=el.get("width", 2))
        elif etype == "polygon":
            points = [tuple(p) for p in el["points"]]
            if el.get("fill"):
                draw.polygon(points, fill=color)
            else:
                draw.polygon(points, outline=color, width=el.get("width", 2))
        elif etype == "text":
            draw.text((el["x"], el["y"]), el.get("text", ""), fill=color, font=font)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    buf.name = "drawing.png"
    return buf