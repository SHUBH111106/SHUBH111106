import os
import requests
import math

from PIL import Image, ImageDraw, ImageFont, ImageFilter


# ============================================================
# CONFIG
# ============================================================

USERNAME = "SHUBH111106"

ROWS = 7
MAX_WEEKS = 53

CELL = 14
GAP = 5

LEFT = 48
TOP = 82

WIDTH = LEFT + MAX_WEEKS * (CELL + GAP) + 35
HEIGHT = 245

FPS = 30

# ============================================================
# ANIMATION
# ============================================================

# How many frames between each falling block
SPAWN_INTERVAL = 3

# How long the complete fall takes
FALL_FRAMES = 45

SETTLE_FRAMES = 10

HOLD_FRAMES = 30

# ============================================================
# PHYSICS
# ============================================================

GRAVITY = 0.75

# ============================================================
# COLORS
# ============================================================

BACKGROUND = (9, 13, 18)

GRID_EMPTY = (18, 25, 32)

TEXT = (190, 205, 220)

MUTED = (100, 115, 130)

LEVEL_COLORS = {

    1: (14, 68, 41),

    2: (0, 109, 50),

    3: (38, 166, 65),

    4: (57, 211, 83),

}


# ============================================================
# FONTS
# ============================================================

def get_font(size):

    fonts = [

        "C:/Windows/Fonts/consola.ttf",

        "C:/Windows/Fonts/consolab.ttf",

        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",

    ]

    for path in fonts:

        if os.path.exists(path):

            return ImageFont.truetype(
                path,
                size
            )

    return ImageFont.load_default()


FONT_TITLE = get_font(20)
FONT_SMALL = get_font(10)
FONT_TINY = get_font(8)


# ============================================================
# GITHUB DATA
# ============================================================

def get_contributions():

    token = os.getenv("GITHUB_TOKEN")

    if not token:

        raise RuntimeError(
            "GITHUB_TOKEN environment variable is missing."
        )

    query = """
    query($login: String!) {

        user(login: $login) {

            contributionsCollection {

                contributionCalendar {

                    totalContributions

                    weeks {

                        contributionDays {

                            contributionCount
                            date

                        }

                    }

                }

            }

        }

    }
    """

    response = requests.post(

        "https://api.github.com/graphql",

        json={

            "query": query,

            "variables": {

                "login": USERNAME

            }

        },

        headers={

            "Authorization":
                f"Bearer {token}",

            "Content-Type":
                "application/json"

        },

        timeout=30

    )

    response.raise_for_status()

    data = response.json()

    if "errors" in data:

        raise RuntimeError(
            str(data["errors"])
        )

    calendar = (

        data["data"]
        ["user"]
        ["contributionsCollection"]
        ["contributionCalendar"]

    )

    return (

        calendar["weeks"],

        calendar["totalContributions"]

    )


# ============================================================
# CONTRIBUTION LEVEL
# ============================================================

def contribution_level(count):

    if count <= 0:
        return 0

    if count <= 2:
        return 1

    if count <= 5:
        return 2

    if count <= 10:
        return 3

    return 4


# ============================================================
# BLOCK
# ============================================================

class Block:

    def __init__(
        self,
        column,
        target_row,
        count,
        index
    ):

        self.column = column

        self.count = count

        self.level = contribution_level(
            count
        )

        # ----------------------------------------------------
        # Horizontal position
        # ----------------------------------------------------

        self.x = (

            LEFT
            + column * (CELL + GAP)

        )

        # ----------------------------------------------------
        # Start above the grid
        # ----------------------------------------------------

        self.start_y = (

            TOP
            - 50
            - (column % 5) * 10

        )

        self.y = self.start_y

        # ----------------------------------------------------
        # Landing position
        # ----------------------------------------------------

        self.target_y = (

            TOP
            + target_row * (CELL + GAP)

        )

        # ----------------------------------------------------
        # Sequential delay
        # ----------------------------------------------------

        self.delay = (
            index * SPAWN_INTERVAL
        )

        self.active = False

        self.finished = False


# ============================================================
# CREATE BLOCKS
# ============================================================

def create_blocks(weeks):

    blocks = []

    global_index = 0

    for column, week in enumerate(weeks):

        contributions = []

        for day in week[
            "contributionDays"
        ]:

            count = day[
                "contributionCount"
            ]

            if count > 0:

                contributions.append(
                    count
                )

        # ----------------------------------------------------
        # Stack from bottom
        # ----------------------------------------------------

        for stack_index, count in enumerate(
            contributions
        ):

            target_row = (
                ROWS
                - 1
                - stack_index
            )

            block = Block(

                column,

                target_row,

                count,

                global_index

            )

            blocks.append(
                block
            )

            global_index += 1

    return blocks


# ============================================================
# EASING
# ============================================================

def ease_out_cubic(t):

    t = max(
        0.0,
        min(
            1.0,
            t
        )
    )

    return 1 - (
        1 - t
    ) ** 3


# ============================================================
# BOUNCE
# ============================================================

def calculate_position(
    start,
    target,
    progress
):

    progress = max(
        0.0,
        min(
            1.0,
            progress
        )
    )

    # --------------------------------------------------------
    # Main fall
    # --------------------------------------------------------

    eased = ease_out_cubic(
        progress
    )

    position = (

        start
        + (
            target
            - start
        ) * eased

    )

    # --------------------------------------------------------
    # Small landing bounce
    # --------------------------------------------------------

    if progress > 0.82:

        bounce_progress = (

            progress
            - 0.82

        ) / 0.18

        bounce = (

            math.sin(
                bounce_progress
                * math.pi
                * 2
            )

            * (

                1
                - bounce_progress

            )

            * 5

        )

        position -= bounce

    return position


# ============================================================
# UPDATE BLOCKS
# ============================================================

def update_blocks(
    blocks,
    frame
):

    for block in blocks:

        # ----------------------------------------------------
        # Has this block started?
        # ----------------------------------------------------

        if frame < block.delay:

            continue

        block.active = True

        local_frame = (
            frame
            - block.delay
        )

        # ----------------------------------------------------
        # Has it finished?
        # ----------------------------------------------------

        if local_frame >= FALL_FRAMES:

            block.y = block.target_y

            block.finished = True

            continue

        # ----------------------------------------------------
        # Calculate movement
        # ----------------------------------------------------

        progress = (

            local_frame
            / FALL_FRAMES

        )

        block.y = calculate_position(

            block.start_y,

            block.target_y,

            progress

        )


# ============================================================
# DRAW GRID
# ============================================================

def draw_grid(
    draw,
    weeks_count
):

    for column in range(
        weeks_count
    ):

        for row in range(ROWS):

            x = (

                LEFT
                + column * (CELL + GAP)

            )

            y = (

                TOP
                + row * (CELL + GAP)

            )

            draw.rounded_rectangle(

                (
                    x,
                    y,
                    x + CELL,
                    y + CELL
                ),

                radius=3,

                fill=GRID_EMPTY

            )


# ============================================================
# DRAW MONTHS
# ============================================================

def draw_months(
    draw,
    weeks
):

    months = {

        "01": "Jan",
        "02": "Feb",
        "03": "Mar",
        "04": "Apr",
        "05": "May",
        "06": "Jun",
        "07": "Jul",
        "08": "Aug",
        "09": "Sep",
        "10": "Oct",
        "11": "Nov",
        "12": "Dec"

    }

    previous = None

    for column, week in enumerate(
        weeks
    ):

        days = week[
            "contributionDays"
        ]

        if not days:
            continue

        month = days[0][
            "date"
        ][5:7]

        if month == previous:
            continue

        previous = month

        x = (

            LEFT
            + column * (CELL + GAP)

        )

        draw.text(

            (
                x,
                TOP - 22
            ),

            months.get(
                month,
                ""
            ),

            font=FONT_SMALL,

            fill=MUTED

        )


# ============================================================
# DRAW WEEKDAYS
# ============================================================

def draw_weekdays(draw):

    labels = [

        "Mon",
        "Tue",
        "Wed",
        "Thu",
        "Fri",
        "Sat",
        "Sun"

    ]

    for row, label in enumerate(
        labels
    ):

        y = (

            TOP
            + row * (CELL + GAP)

        )

        draw.text(

            (
                4,
                y + 1
            ),

            label,

            font=FONT_TINY,

            fill=MUTED

        )


# ============================================================
# DRAW HEADER
# ============================================================

def draw_header(
    draw,
    total_contributions
):

    draw.text(

        (
            LEFT,
            14
        ),

        "Contribution Gravity Drop",

        font=FONT_TITLE,

        fill=TEXT

    )

    draw.text(

        (
            LEFT,
            40
        ),

        "commits fall  •  one by one  •  stack",

        font=FONT_SMALL,

        fill=MUTED

    )

    counter = (

        f"{total_contributions:,}"
        " contributions"

    )

    bbox = draw.textbbox(

        (0, 0),

        counter,

        font=FONT_SMALL

    )

    width = (
        bbox[2]
        - bbox[0]
    )

    draw.text(

        (
            WIDTH
            - width
            - 10,

            20
        ),

        counter,

        font=FONT_SMALL,

        fill=TEXT

    )


# ============================================================
# DRAW STATUS
# ============================================================

def draw_status(
    draw,
    text
):

    draw.text(

        (
            LEFT,
            HEIGHT - 22
        ),

        text,

        font=FONT_SMALL,

        fill=MUTED

    )


# ============================================================
# DRAW BLOCK
# ============================================================

def draw_block(
    draw,
    glow_draw,
    block
):

    if not block.active:

        return

    x = int(
        block.x
    )

    y = int(
        block.y
    )

    color = LEVEL_COLORS[
        block.level
    ]

    # --------------------------------------------------------
    # Glow
    # --------------------------------------------------------

    glow_draw.rounded_rectangle(

        (
            x - 5,
            y - 5,
            x + CELL + 5,
            y + CELL + 5
        ),

        radius=4,

        fill=color + (130,)

    )

    # --------------------------------------------------------
    # Block
    # --------------------------------------------------------

    draw.rounded_rectangle(

        (
            x,
            y,
            x + CELL,
            y + CELL
        ),

        radius=3,

        fill=color

    )


# ============================================================
# RENDER
# ============================================================

def render_frame(
    weeks,
    blocks,
    total_contributions,
    status
):

    image = Image.new(

        "RGBA",

        (
            WIDTH,
            HEIGHT
        ),

        BACKGROUND + (255,)

    )

    draw = ImageDraw.Draw(
        image
    )

    # --------------------------------------------------------
    # Header
    # --------------------------------------------------------

    draw_header(

        draw,

        total_contributions

    )

    # --------------------------------------------------------
    # Grid
    # --------------------------------------------------------

    draw_grid(

        draw,

        len(weeks)

    )

    # --------------------------------------------------------
    # Labels
    # --------------------------------------------------------

    draw_months(

        draw,

        weeks

    )

    draw_weekdays(
        draw
    )

    # --------------------------------------------------------
    # Glow
    # --------------------------------------------------------

    glow = Image.new(

        "RGBA",

        (
            WIDTH,
            HEIGHT
        ),

        (
            0,
            0,
            0,
            0
        )

    )

    glow_draw = ImageDraw.Draw(
        glow
    )

    # --------------------------------------------------------
    # Blocks
    # --------------------------------------------------------

    for block in blocks:

        draw_block(

            draw,

            glow_draw,

            block

        )

    # --------------------------------------------------------
    # Apply glow
    # --------------------------------------------------------

    glow = glow.filter(

        ImageFilter.GaussianBlur(
            6
        )

    )

    image.alpha_composite(
        glow
    )

    # --------------------------------------------------------
    # Redraw blocks
    # --------------------------------------------------------

    draw = ImageDraw.Draw(
        image
    )

    for block in blocks:

        if not block.active:
            continue

        x = int(
            block.x
        )

        y = int(
            block.y
        )

        color = LEVEL_COLORS[
            block.level
        ]

        draw.rounded_rectangle(

            (
                x,
                y,
                x + CELL,
                y + CELL
            ),

            radius=3,

            fill=color

        )

    # --------------------------------------------------------
    # Status
    # --------------------------------------------------------

    draw_status(

        draw,

        status

    )

    return image.convert(
        "RGB"
    )


# ============================================================
# GENERATE ANIMATION
# ============================================================

def generate_animation(
    weeks,
    blocks,
    total_contributions
):

    frames = []

    # --------------------------------------------------------
    # Calculate total duration
    # --------------------------------------------------------

    last_delay = 0

    if blocks:

        last_delay = max(
            block.delay
            for block in blocks
        )

    total_frames = (

        last_delay
        + FALL_FRAMES
        + SETTLE_FRAMES

    )

    # --------------------------------------------------------
    # Animation
    # --------------------------------------------------------

    for frame in range(
        total_frames
    ):

        update_blocks(

            blocks,

            frame

        )

        active_count = sum(

            1
            for block in blocks
            if block.active

        )

        status = (

            f"{active_count} blocks falling"

        )

        frames.append(

            render_frame(

                weeks,

                blocks,

                total_contributions,

                status

            )

        )

    # --------------------------------------------------------
    # Final hold
    # --------------------------------------------------------

    final = render_frame(

        weeks,

        blocks,

        total_contributions,

        "contribution history settled"

    )

    for _ in range(
        HOLD_FRAMES
    ):

        frames.append(
            final.copy()
        )

    return frames


# ============================================================
# SAVE GIF
# ============================================================

def save_gif(frames):

    os.makedirs(

        "assets",

        exist_ok=True

    )

    output = (
        "assets/gravity-drop.gif"
    )

    frames[0].save(

        output,

        save_all=True,

        append_images=frames[1:],

        duration=int(
            1000 / FPS
        ),

        loop=0,

        optimize=True

    )

    return output


# ============================================================
# MAIN
# ============================================================

def main():

    print()

    print(
        "Fetching GitHub contribution data..."
    )

    weeks, total_contributions = (
        get_contributions()
    )

    weeks = weeks[
        :MAX_WEEKS
    ]

    print(
        f"Received {len(weeks)} weeks."
    )

    print(
        f"Total contributions: "
        f"{total_contributions:,}"
    )

    print()

    # --------------------------------------------------------
    # Create ALL blocks
    # --------------------------------------------------------

    blocks = create_blocks(
        weeks
    )

    print(
        f"Created {len(blocks)} "
        "contribution blocks."
    )

    print()

    print(
        "Starting sequential gravity..."
    )

    # --------------------------------------------------------
    # Generate
    # --------------------------------------------------------

    frames = generate_animation(

        weeks,

        blocks,

        total_contributions

    )

    print()

    print(
        f"Generated {len(frames)} frames."
    )

    print(
        "Creating GIF..."
    )

    output = save_gif(
        frames
    )

    print()

    print(
        "======================================"
    )

    print(
        " Gravity Drop generated successfully"
    )

    print(
        "======================================"
    )

    print()

    print(
        f"Output: {output}"
    )

    print(
        f"Frames: {len(frames)}"
    )

    print(
        f"Size: {WIDTH} × {HEIGHT}"
    )

    print()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()