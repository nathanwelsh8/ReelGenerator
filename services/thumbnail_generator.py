from PIL import Image, ImageDraw, ImageFont
import textwrap
import os
from moviepy.editor import VideoFileClip

def generate(
    title: str,
    output_filename: str,
    video_path: str,
    frame_time: float = 0.0,
    horizontal_margin_ratio: float = 0.22,
    min_side_margin_px: int = 180,
    base_font_size: int = 110,
    min_font_size: int = 50,
) -> str:
    """
    Generate a thumbnail by capturing a frame from the provided video and overlaying the title text.
    Text styling matches the subtitle style (yellow with black stroke) used in editor_agent.
    Adds generous left/right safe padding so text sits well inside Instagram crop areas.

    Args:
        title: Title text to overlay (will wrap to fit width).
        output_filename: Desired filename ('.png' appended if missing) inside image_assests/thumbnails.
        video_path: Path to source video (first frame or at frame_time captured).
        frame_time: Seconds into the video to capture (default 0.0).
        horizontal_margin_ratio: Fraction (0-0.45) of total width to reserve on EACH side.
            e.g. 0.22 => 22% left + 22% right kept clear (56% usable center width).
            Ignored if it would yield less than (W - 2*min_side_margin_px) usable width.
    min_side_margin_px: Fallback absolute pixel margin per side to guarantee padding.
    base_font_size: Starting font size before any downscaling for wrapping.
    min_font_size: Lower bound when shrinking to fit width.
    Returns: Absolute path (string) to generated thumbnail.
    """
    if not title or not output_filename or not video_path:
        raise ValueError("title, output_filename and video_path are required")
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    thumb_dir = "image_assests/thumbnails"
    os.makedirs(thumb_dir, exist_ok=True)
    fname = output_filename
    if not fname.lower().endswith('.png'):
        fname += '.png'
    output_path = os.path.join(thumb_dir, fname)

    # Capture frame
    with VideoFileClip(video_path) as clip:
        frame_time = min(max(frame_time, 0.0), max(0.0, clip.duration - 0.05))
        frame = clip.get_frame(frame_time)  # numpy array
    img = Image.fromarray(frame).convert('RGBA')
    W, H = img.size

    # Clamp margins to sane range
    horizontal_margin_ratio = max(0.0, min(0.45, horizontal_margin_ratio))

    # Font setup
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    # Normalize provided font sizes
    if base_font_size < min_font_size:
        base_font_size = min_font_size
    base_size = base_font_size  # start large, shrink if needed
    try:
        font = ImageFont.truetype(font_path, base_size)
    except Exception:
        font = ImageFont.load_default()

    draw = ImageDraw.Draw(img)
    # Determine max text width with larger safe padding to avoid Instagram edge cropping.
    # Two strategies: ratio-based and absolute pixel minimum; choose the stricter (smaller usable width).
    ratio_usable_width = int(W * (1 - 2 * horizontal_margin_ratio))
    pixel_usable_width = W - 2 * min_side_margin_px
    max_width = min(ratio_usable_width, pixel_usable_width)
    # Ensure we still have a reasonable area
    max_width = max(int(W * 0.38), max_width)  # never shrink below ~38% of width

    # Center zone debugging (optional): uncomment to visualize safe area
    # debug_overlay = Image.new('RGBA', (max_width, H), (255,0,0,40))
    # img.paste(debug_overlay, ((W - max_width)//2, 0), debug_overlay)
    # Adaptive wrap: attempt word wrapping with dynamic width
    words = title.split()
    lines = []
    current = []
    for w in words:
        test = " ".join(current + [w])
        # Shrink progressively until fits or min size reached
        while draw.textlength(test, font=font) > max_width and base_size > min_font_size:
            base_size -= 4
            font = ImageFont.truetype(font_path, base_size)
        if draw.textlength(test, font=font) <= max_width:
            current.append(w)
        else:
            # Current line full; commit and start new line with the word (will re-check size next loop)
            if current:
                lines.append(" ".join(current))
            current = [w]
    if current:
        lines.append(" ".join(current))

    # Recalculate line height
    bbox = font.getbbox('A')
    line_height = (bbox[3] - bbox[1]) + 30
    total_height = line_height * len(lines)
    y = (H - total_height) // 2

    # Draw with stroke for visibility
    for line in lines:
        w = draw.textlength(line, font=font)
        x = (W - w) // 2
        draw.text((x, y), line, font=font, fill='yellow', stroke_width=4, stroke_fill='black')
        y += line_height

    img.save(output_path)
    return output_path


if __name__ == "__main__":
    # Example usage; adjust paths as needed
    sample_video = "video_assets/output_video_15_20250814_195004.mp4"
    if os.path.isfile(sample_video):
        print(generate("Attention is All You Need Until You Need Retention", "thumbnail_15", sample_video))
    else:
        print("Sample video not found; please supply a valid video path.")
