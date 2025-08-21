from __future__ import annotations
from io import BytesIO
from typing import Optional

# Pillow is already used elsewhere in the project
from PIL import Image


def save_bytes_as_png(image_bytes: bytes, output_path: str, background: Optional[str] = None) -> str:
    """
    Save the provided image (any Pillow-supported format, including WEBP) as a PNG to output_path.
    - Preserves transparency when present (RGBA).
    - If a solid background is desired for formats with alpha, pass background (e.g., '#FFFFFF').
    Returns the output_path.
    """
    with Image.open(BytesIO(image_bytes)) as im:
        im.load()
        # Convert mode if needed; keep alpha when present
        if background and (im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)):
            # Composite onto a solid background
            bg = Image.new("RGBA", im.size, background)
            bg.paste(im, (0, 0), im.convert("RGBA"))
            im = bg.convert("RGB")
        else:
            # Normalize to a common mode for PNG while preserving alpha
            if im.mode not in ("RGB", "RGBA"):
                im = im.convert("RGBA" if ("transparency" in im.info or im.mode.endswith("A")) else "RGB")
        im.save(output_path, format="PNG")
    return output_path
