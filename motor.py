import argparse
import math
import os
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw, ImageFont


# -------------------------
# CONFIGURATION
# -------------------------

# Change these to customize the appearance.
FONT_PATH = r"NotoSans-Regular.ttf"
FONT_BOLD_PATH = r"NotoSans-Bold.ttf"

HEADING_SIZE = 64
TEXT_SIZE = 36
ACTOR_ROLE_SIZE = 30
ACTOR_NAME_SIZE = 42

HEADING_SPACING = 70
TEXT_SPACING = 24
ACTOR_SPACING = 38

IMAGE_SPACING = 40

# Vertical space before/after an image row.
IMAGE_ROW_SPACING = 55

# Horizontal space between logos in an image row.
IMAGE_ROW_GAP = 60

# Vertical space before/after a text row.
TEXT_ROW_SPACING = 25

# Horizontal gap between columns in a text row.
TEXT_ROW_COLUMN_GAP = 100

# Default image height if height isn't specified.
DEFAULT_IMAGE_HEIGHT = 150

# Space between the two lines of an actor credit.
ACTOR_LINE_GAP = 6

# Extra empty space above/below the entire credits.
TOP_PADDING = 0
BOTTOM_PADDING = 100

# Margin used when wrapping text.
SIDE_MARGIN = 100

# Background and text.
BACKGROUND = (0, 0, 0)
FOREGROUND = (255, 255, 255)


# -------------------------
# FONT HANDLING
# -------------------------

def find_font(path, fallback_names):
    """Find a font on Windows if the configured path doesn't exist."""
    if os.path.isfile(path):
        return path

    windows_fonts = os.path.join(
        os.environ.get("WINDIR", r"C:\Windows"),
        "Fonts"
    )

    for name in fallback_names:
        candidate = os.path.join(windows_fonts, name)
        if os.path.isfile(candidate):
            return candidate

    return None


REGULAR_FONT = find_font(
    FONT_PATH,
    ["NotoSans-Regular.ttf", "NotoSans-Regular.otf"]
)

BOLD_FONT = find_font(
    FONT_BOLD_PATH,
    ["NotoSans-Bold.ttf", "NotoSans-Bold.otf"]
)

if REGULAR_FONT is None:
    raise FileNotFoundError(
        "Noto Sans Regular was not found.\n"
        "Install Noto Sans or change FONT_PATH at the top of the script."
    )

if BOLD_FONT is None:
    BOLD_FONT = REGULAR_FONT


def load_font(size, bold=False):
    return ImageFont.truetype(
        BOLD_FONT if bold else REGULAR_FONT,
        size
    )


# -------------------------
# XML HELPERS
# -------------------------

def get_float(element, attribute, default):
    try:
        return float(element.get(attribute, default))
    except (TypeError, ValueError):
        return float(default)


def get_int(element, attribute, default):
    try:
        return int(element.get(attribute, default))
    except (TypeError, ValueError):
        return int(default)


def resolve_image_path(xml_file, src):
    """Resolve image paths relative to the XML file."""
    if not src:
        raise ValueError("An <image> element is missing its src attribute.")

    if os.path.isabs(src):
        return src

    return os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(xml_file)), src)
    )


# -------------------------
# TEXT WRAPPING
# -------------------------

def text_width(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def text_height(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[3] - bbox[1]


def wrap_text(draw, text, font, max_width):
    """Wrap text by words, preserving explicit newlines."""
    if not text:
        return [""]

    result = []

    for paragraph in str(text).splitlines():
        words = paragraph.split()

        if not words:
            result.append("")
            continue

        current = words[0]

        for word in words[1:]:
            test = current + " " + word

            if text_width(draw, test, font) <= max_width:
                current = test
            else:
                result.append(current)
                current = word

        result.append(current)

    return result


# -------------------------
# IMAGE LOADING
# -------------------------

def load_scaled_image(path, height):
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Image not found: {path}")

    image = Image.open(path).convert("RGBA")

    height = max(1, int(height))
    width = max(1, round(image.width * height / image.height))

    return image.resize(
        (width, height),
        Image.Resampling.LANCZOS
    )


# -------------------------
# CREDIT ITEM BUILDING
# -------------------------

def build_items(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()

    if root.tag.lower() != "credits":
        raise ValueError("The root XML element must be <credits>.")

    settings = root.find("settings")

    width = 1920
    height = 1080
    fps = 60
    scroll_speed = 80

    if settings is not None:
        width = get_int(settings, "width", width)
        height = get_int(settings, "height", height)
        fps = get_int(settings, "fps", fps)
        scroll_speed = get_float(settings, "scroll_speed", scroll_speed)

    if width <= 0 or height <= 0:
        raise ValueError("Width and height must be greater than zero.")

    if fps <= 0:
        raise ValueError("FPS must be greater than zero.")

    if scroll_speed <= 0:
        raise ValueError("scroll_speed must be greater than zero.")

    items = []

    for element in root:
        tag = element.tag.lower()

        if tag == "settings":
            continue

        if tag == "heading":
            items.append({
                "type": "heading",
                "text": element.text or ""
            })

        elif tag == "text":
            items.append({
                "type": "text",
                "text": element.text or ""
            })

        elif tag == "actor":
            items.append({
                "type": "actor",
                "role": element.get("role", ""),
                "name": element.text or ""
            })

        elif tag == "image":
            items.append({
                "type": "image",
                "path": resolve_image_path(
                    xml_file,
                    element.get("src")
                ),
                "height": get_float(
                    element,
                    "height",
                    DEFAULT_IMAGE_HEIGHT
                )
            })

        elif tag == "image_row":
            images = []

            for image_element in element:
                if image_element.tag.lower() != "image":
                    continue

                images.append({
                    "path": resolve_image_path(
                        xml_file,
                        image_element.get("src")
                    ),
                    "height": get_float(
                        image_element,
                        "height",
                        DEFAULT_IMAGE_HEIGHT
                    )
                })

            if images:
                items.append({
                    "type": "image_row",
                    "images": images
                })

        elif tag == "text_row":
            texts = []

            for text_element in element:
                if text_element.tag.lower() != "text":
                    continue

                texts.append(text_element.text or "")

            if texts:
                items.append({
                    "type": "text_row",
                    "texts": texts
                })

        elif tag == "spacer":
            items.append({
                "type": "spacer",
                "height": get_float(element, "height", 50)
            })

        else:
            print(f"[WARNING] Unknown XML element: <{element.tag}>")

    return width, height, fps, scroll_speed, items


# -------------------------
# RENDERING
# -------------------------

def create_credit_canvas(xml_file, width, height, items):
    """
    Create one tall RGBA image containing the complete credits.
    """
    dummy = Image.new("RGB", (width, height), BACKGROUND)
    draw = ImageDraw.Draw(dummy)

    # First pass estimates the required height.
    y = TOP_PADDING

    rendered_items = []

    for item in items:
        item_type = item["type"]

        if item_type == "heading":
            font = load_font(HEADING_SIZE, bold=True)
            lines = wrap_text(
                draw,
                item["text"].strip(),
                font,
                width - SIDE_MARGIN * 2
            )

            line_heights = [
                text_height(draw, line, font) for line in lines
            ]

            item_height = sum(line_heights) + max(0, len(lines) - 1) * 8

            rendered_items.append({
                **item,
                "font": font,
                "lines": lines,
                "height": item_height
            })

            y += item_height + HEADING_SPACING

        elif item_type == "text":
            font = load_font(TEXT_SIZE)
            lines = wrap_text(
                draw,
                item["text"].strip(),
                font,
                width - SIDE_MARGIN * 2
            )

            line_heights = [
                text_height(draw, line, font) for line in lines
            ]

            item_height = sum(line_heights) + max(0, len(lines) - 1) * 6

            rendered_items.append({
                **item,
                "font": font,
                "lines": lines,
                "height": item_height
            })

            y += item_height + TEXT_SPACING

        elif item_type == "actor":
            role_font = load_font(ACTOR_ROLE_SIZE)
            name_font = load_font(ACTOR_NAME_SIZE, bold=True)

            role_lines = wrap_text(
                draw,
                item["role"].strip(),
                role_font,
                width - SIDE_MARGIN * 2
            )

            name_lines = wrap_text(
                draw,
                item["name"].strip(),
                name_font,
                width - SIDE_MARGIN * 2
            )

            role_height = sum(
                text_height(draw, line, role_font)
                for line in role_lines
            ) + max(0, len(role_lines) - 1) * 4

            name_height = sum(
                text_height(draw, line, name_font)
                for line in name_lines
            ) + max(0, len(name_lines) - 1) * 6

            item_height = (
                role_height
                + ACTOR_LINE_GAP
                + name_height
            )

            rendered_items.append({
                **item,
                "role_font": role_font,
                "name_font": name_font,
                "role_lines": role_lines,
                "name_lines": name_lines,
                "height": item_height
            })

            y += item_height + ACTOR_SPACING

        elif item_type == "image":
            image = load_scaled_image(
                item["path"],
                item["height"]
            )

            rendered_items.append({
                **item,
                "image": image,
                "height": image.height
            })

            y += image.height + IMAGE_SPACING

        elif item_type == "image_row":
            images = [
                load_scaled_image(
                    image["path"],
                    image["height"]
                )
                for image in item["images"]
            ]

            row_height = max(image.height for image in images)

            rendered_items.append({
                **item,
                "loaded_images": images,
                "height": row_height
            })

            y += row_height + IMAGE_ROW_SPACING

        elif item_type == "text_row":
            font = load_font(TEXT_SIZE)

            # The row is horizontally centered as a whole.
            widths = [
                text_width(draw, text, font)
                for text in item["texts"]
            ]

            row_width = (
                sum(widths)
                + TEXT_ROW_COLUMN_GAP * max(0, len(widths) - 1)
            )

            row_height = max(
                text_height(draw, text, font)
                for text in item["texts"]
            )

            rendered_items.append({
                **item,
                "font": font,
                "widths": widths,
                "row_width": row_width,
                "height": row_height
            })

            y += row_height + TEXT_ROW_SPACING

        elif item_type == "spacer":
            spacer_height = max(0, item["height"])

            rendered_items.append({
                **item,
                "height": spacer_height
            })

            y += spacer_height

    total_height = max(height, math.ceil(y + BOTTOM_PADDING))

    canvas = Image.new(
        "RGBA",
        (width, total_height),
        (*BACKGROUND, 255)
    )

    draw = ImageDraw.Draw(canvas)

    y = TOP_PADDING

    for item in rendered_items:
        item_type = item["type"]

        if item_type == "heading":
            for line in item["lines"]:
                bbox = draw.textbbox(
                    (0, 0),
                    line,
                    font=item["font"]
                )

                line_width = bbox[2] - bbox[0]

                draw.text(
                    (
                        (width - line_width) / 2,
                        y
                    ),
                    line,
                    font=item["font"],
                    fill=FOREGROUND
                )

                y += bbox[3] - bbox[1] + 8

            y += HEADING_SPACING

        elif item_type == "text":
            for line in item["lines"]:
                bbox = draw.textbbox(
                    (0, 0),
                    line,
                    font=item["font"]
                )

                line_width = bbox[2] - bbox[0]

                draw.text(
                    (
                        (width - line_width) / 2,
                        y
                    ),
                    line,
                    font=item["font"],
                    fill=FOREGROUND
                )

                y += bbox[3] - bbox[1] + 6

            y += TEXT_SPACING

        elif item_type == "actor":
            for line in item["role_lines"]:
                bbox = draw.textbbox(
                    (0, 0),
                    line,
                    font=item["role_font"]
                )

                line_width = bbox[2] - bbox[0]

                draw.text(
                    (
                        (width - line_width) / 2,
                        y
                    ),
                    line,
                    font=item["role_font"],
                    fill=FOREGROUND
                )

                y += bbox[3] - bbox[1] + 4

            y += ACTOR_LINE_GAP

            for line in item["name_lines"]:
                bbox = draw.textbbox(
                    (0, 0),
                    line,
                    font=item["name_font"]
                )

                line_width = bbox[2] - bbox[0]

                draw.text(
                    (
                        (width - line_width) / 2,
                        y
                    ),
                    line,
                    font=item["name_font"],
                    fill=FOREGROUND
                )

                y += bbox[3] - bbox[1] + 6

            y += ACTOR_SPACING

        elif item_type == "image":
            image = item["image"]

            x = (width - image.width) // 2

            canvas.alpha_composite(
                image,
                (x, int(y))
            )

            y += image.height + IMAGE_SPACING

        elif item_type == "image_row":
            images = item["loaded_images"]

            total_width = (
                sum(image.width for image in images)
                + IMAGE_ROW_GAP * max(0, len(images) - 1)
            )

            x = (width - total_width) / 2
            row_top = y

            for image in images:
                image_y = (
                    row_top
                    + (item["height"] - image.height) / 2
                )

                canvas.alpha_composite(
                    image,
                    (round(x), round(image_y))
                )

                x += image.width + IMAGE_ROW_GAP

            y += item["height"] + IMAGE_ROW_SPACING

        elif item_type == "text_row":
            x = (width - item["row_width"]) / 2

            for text, text_width_value in zip(
                item["texts"],
                item["widths"]
            ):
                bbox = draw.textbbox(
                    (0, 0),
                    text,
                    font=item["font"]
                )

                text_y = (
                    y
                    + (item["height"] - (bbox[3] - bbox[1])) / 2
                )

                draw.text(
                    (round(x), round(text_y)),
                    text,
                    font=item["font"],
                    fill=FOREGROUND
                )

                x += text_width_value + TEXT_ROW_COLUMN_GAP

            y += item["height"] + TEXT_ROW_SPACING

        elif item_type == "spacer":
            y += item["height"]

    return canvas


# -------------------------
# FFMPEG VIDEO CREATION
# -------------------------

def render_video(
    tall_image_path,
    output_path,
    width,
    height,
    fps,
    scroll_speed,
    total_height
):
    ffmpeg = shutil.which("ffmpeg")

    if ffmpeg is None:
        raise RuntimeError(
            "FFmpeg was not found in PATH. "
            "Install FFmpeg and make sure 'ffmpeg' works in Command Prompt."
        )

    # The image starts completely below the video and ends
    # completely above it.
    travel_distance = height + total_height

    duration = travel_distance / scroll_speed

    if duration <= 0:
        duration = 1

    # At t=0:
    #
    #     y = height
    #
    # meaning the top of the credits image is exactly at
    # the bottom of the video.
    #
    # At the end:
    #
    #     y = -total_height
    #
    # meaning the bottom of the credits image is exactly
    # at the top of the video.
    y_expression = f"{height}-t*{scroll_speed}"

    filter_expression = (
        f"color=c=black:s={width}x{height}:r={fps}:d={duration}[bg];"
        f"[bg][0:v]overlay="
        f"x=0:"
        f"y='{y_expression}':"
        f"eof_action=pass"
    )

    command = [
        ffmpeg,
        "-y",

        # Credits PNG
        "-loop", "1",
        "-i", tall_image_path,

        "-filter_complex",
        filter_expression,

        "-t", str(duration),
        "-r", str(fps),

        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",

        output_path
    ]

    print("\nRendering video...")
    print(f"Credits image: {total_height}px tall")
    print(f"Travel distance: {travel_distance}px")
    print(f"Duration: {duration:.2f} seconds")
    print(f"Scroll speed: {scroll_speed}px/s")

    subprocess.run(command, check=True)

    return duration


# -------------------------
# MAIN
# -------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate scrolling ending credits from XML."
    )

    parser.add_argument(
        "xml",
        help="Path to the credits XML file."
    )

    parser.add_argument(
        "-o",
        "--output",
        default="ending_credits.mp4",
        help="Output MP4 filename."
    )

    parser.add_argument(
        "--png",
        action="store_true",
        help="Only create the tall PNG instead of rendering an MP4."
    )

    args = parser.parse_args()

    xml_file = os.path.abspath(args.xml)
    output_file = os.path.abspath(args.output)

    print("Loading XML...")
    width, height, fps, scroll_speed, items = build_items(xml_file)

    print(
        f"Resolution: {width}x{height}\n"
        f"FPS: {fps}\n"
        f"Scroll speed: {scroll_speed}px/s\n"
        f"Items: {len(items)}"
    )

    print("Building credits image...")

    canvas = create_credit_canvas(
        xml_file,
        width,
        height,
        items
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        tall_png = os.path.join(
            temp_dir,
            "credits.png"
        )

        canvas.save(
            tall_png,
            "PNG"
        )

        print(
            f"Credits image: "
            f"{canvas.width}x{canvas.height}"
        )

        if args.png:
            png_output = os.path.splitext(output_file)[0] + ".png"

            canvas.save(
                png_output,
                "PNG"
            )

            print(f"\nSaved: {png_output}")
            return

        duration = render_video(
            tall_png,
            output_file,
            width,
            height,
            fps,
            scroll_speed,
            canvas.height
        )

    print(f"\nFinished!")
    print(f"Duration: {duration:.2f} seconds")
    print(f"Saved: {output_file}")


if __name__ == "__main__":
    main()
