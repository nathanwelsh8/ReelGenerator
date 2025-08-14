from PIL import Image, ImageDraw, ImageFont
import textwrap
import os

def generate(title: str, output_filename: str) -> str:
    """
    Overlays the given title in white, centered, medium/large text on reel_title_cover.png.
    Breaks lines as needed to fit. Saves as reel_title_cover.png (or custom filename).
    """

    if not title or not output_filename:
        raise ValueError("Title and output path must be provided.")

    cover_path = "image_assests/reel_title_cover.png"
    thumb_dir = "image_assests/thumbnails"
    os.makedirs(thumb_dir, exist_ok=True)
    if output_filename is None:
        output_path = os.path.join(thumb_dir, "reel_title_cover.png")
    else:
        fname = output_filename
        if not fname.lower().endswith(".png"):
            fname += ".png"
        output_path = os.path.join(thumb_dir, fname)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font_size = 64

    if not os.path.isfile(cover_path):
        raise FileNotFoundError(f"Cover image not found: {cover_path}")
    img = Image.open(cover_path).convert("RGBA")
    W, H = img.size

    try:
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        font = ImageFont.load_default()

    draw = ImageDraw.Draw(img)
    max_width = W - 80
    lines = []
    for line in textwrap.wrap(title, width=20):
        while draw.textlength(line, font=font) > max_width and font_size > 24:
            font_size -= 4
            font = ImageFont.truetype(font_path, font_size)
        lines.append(line)

    # Use getbbox for line height (compatible with modern Pillow)
    bbox = font.getbbox('A')
    line_height = (bbox[3] - bbox[1]) + 40
    total_height = line_height * len(lines)
    y = (H - total_height) // 2

    for line in lines:
        w = draw.textlength(line, font=font)
        x = (W - w) // 2
        draw.text((x, y), line, font=font, fill="white")
        y += line_height

    img.save(output_path)
    return output_path


if __name__ == "__main__":
    generate("Attention is All You Need Until You Need Retention", "thumbnail_15")
