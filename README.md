# CreditMotor
The program I use to make the credits you see at the end of some of my videos.

## Requirements

Install Pillow:

    pip install pillow

You also need FFmpeg installed and available in PATH:

    ffmpeg -version

To use a different font other than the fonts provided, change FONT_PATH and FONT_BOLD_PATH at the top of `motor.py`.

## Usage

Render an MP4:

    python motor.py credits.xml -o ending_credits.mp4

Only generate the tall credits PNG:

    python motor.py credits.xml --png -o credits.png

## XML elements

### Settings

    <settings width="1920" height="1080" fps="60" scroll_speed="80"/>

### Heading

    <heading>CAST</heading>

### Regular text

    <text>This is a normal centered line.</text>

Long text automatically wraps.

### Actor

    <actor role="Director">John Smith</actor>

### Single image

The height controls the logo/image height while preserving its aspect ratio:

    <image src="images/logo.png" height="250"/>

### Image row

    <image_row>
        <image src="images/python.png" height="120"/>
        <image src="images/ffmpeg.png" height="120"/>
        <image src="images/blender.png" height="120"/>
    </image_row>

### Text row

    <text_row>
        <text>Programming</text>
        <text>Rollerblade</text>
    </text_row>

### Spacer

    <spacer height="100"/>

## Layout customization

The following values near the top of the Python script control spacing:

    IMAGE_SPACING
    IMAGE_ROW_SPACING
    IMAGE_ROW_GAP
    TEXT_ROW_SPACING
    TEXT_ROW_COLUMN_GAP
    HEADING_SPACING
    TEXT_SPACING
    ACTOR_SPACING

For example:

    IMAGE_ROW_GAP = 100

increases the horizontal distance between logos in an image row.
