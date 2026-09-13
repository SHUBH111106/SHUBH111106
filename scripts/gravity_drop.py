import os
import requests
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter


# ============================================================
# CONFIGURATION
# ============================================================

USERNAME = "SHUBH111106"

ROWS = 7
MAX_WEEKS = 53

CELL = 14
GAP = 5

LEFT = 48
TOP = 82

GRID_WIDTH = MAX_WEEKS * (CELL + GAP)
GRID_HEIGHT = ROWS * (CELL + GAP)

WIDTH = LEFT + GRID_WIDTH + 35
HEIGHT = 245

FPS = 30

BACKGROUND = (9, 13, 18)
GRID_EMPTY = (18, 25, 32)

TEXT = (190, 205, 220)
MUTED = (100, 115, 130)

# GitHub-style intensity colors
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

    possible_fonts = [
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/consolab.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ]

    for path in possible_fonts:

        if os.path.exists(path):
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


FONT_TITLE = get_font(20)
FONT_SMALL = get_font(10)
FONT_TINY = get_font(8)


# ============================================================
# GITHUB CONTRIBUTIONS
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
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
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
        week,
        original_row,
        count,
        stack_row
    ):

        self.week = week

        self.original_row = original_row

        self.count = count

        self.level = contribution_level(count)

        # Horizontal position
        self.x = (
            LEFT +
            week * (CELL + GAP)
        )

        # Start above the grid
        self.y = -CELL * 2.5

        # Final stacking position
        self.target_row = stack_row

        self.target_y = (
            TOP +
            stack_row * (CELL + GAP)
        )

        # Physics
        self.velocity = 0.0

        self.locked = False

        self.delay = 0

        self.bounces = 0


# ============================================================
# CREATE WEEK BLOCKS
# ============================================================

def create_week_blocks(
    week_index,
    week
):

    blocks = []

    contributions = []

    for row, day in enumerate(
        week["contributionDays"]
    ):

        count = day["contributionCount"]

        if count > 0:

            contributions.append(
                (
                    row,
                    count
                )
            )

    # --------------------------------------------------------
    # Stack blocks from bottom upward
    # --------------------------------------------------------

    # Original weekday order is preserved.
    #
    # The first contribution lands at the bottom,
    # the next one above it, etc.

    for stack_index, (
        original_row,
        count
    ) in enumerate(contributions):

        target_row = ROWS - 1 - stack_index

        block = Block(
            week_index,
            original_row,
            count,
            target_row
        )

        # Small stagger makes the animation feel organic.
        block.delay = stack_index * 3

        blocks.append(block)

    return blocks


# ============================================================
# UPDATE PHYSICS
# ============================================================

def update_blocks(
    blocks,
    frame
):

    for block in blocks:

        # ----------------------------------------------------
        # Spawn delay
        # ----------------------------------------------------

        if frame < block.delay:
            continue

        # ----------------------------------------------------
        # Already settled
        # ----------------------------------------------------

        if block.locked:
            continue

        # ----------------------------------------------------
        # Gravity
        # ----------------------------------------------------

        block.velocity += 0.42

        block.y += block.velocity

        # ----------------------------------------------------
        # Target collision
        # ----------------------------------------------------

        if block.y >= block.target_y:

            block.y = block.target_y

            # Small bounce
            if (
                block.bounces < 2
                and block.velocity > 2.0
            ):

                block.velocity *= -0.22

                block.bounces += 1

            else:

                block.velocity = 0

                block.locked = True


# ============================================================
# DRAW GRID
# ============================================================

def draw_grid(
    draw,
    weeks_count
):

    for week in range(MAX_WEEKS):

        for row in range(ROWS):

            x = (
                LEFT +
                week * (CELL + GAP)
            )

            y = (
                TOP +
                row * (CELL + GAP)
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
# DRAW BLOCK
# ============================================================

def draw_block(
    draw,
    glow_draw,
    block
):

    if block.y < TOP - CELL * 3:
        return

    x = int(block.x)

    y = int(block.y)

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
    # Main block
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
# MONTH LABELS
# ============================================================

def draw_months(
    draw,
    weeks
):

    last_month = None

    for week_index, week in enumerate(weeks):

        if not week["contributionDays"]:
            continue

        date = week[
            "contributionDays"
        ][0]["date"]

        month = date[5:7]

        month_names = {
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
            "12": "Dec",
        }

        name = month_names.get(
            month,
            ""
        )

        if month != last_month:

            x = (
                LEFT +
                week_index * (CELL + GAP)
            )

            draw.text(
                (x, TOP - 22),
                name,
                font=FONT_SMALL,
                fill=MUTED
            )

            last_month = month


# ============================================================
# WEEKDAY LABELS
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

    for row, label in enumerate(labels):

        y = (
            TOP +
            row * (CELL + GAP)
        )

        draw.text(
            (
                5,
                y + 1
            ),

            label,

            font=FONT_TINY,

            fill=MUTED
        )


# ============================================================
# HEADER
# ============================================================

def draw_header(
    draw,
    total_contributions
):

    draw.text(
        (LEFT, 14),

        "Contribution Gravity Drop",

        font=FONT_TITLE,

        fill=TEXT
    )

    draw.text(
        (LEFT, 40),

        "commits fall  •  collide  •  stack",

        font=FONT_SMALL,

        fill=MUTED
    )

    # Contribution counter
    counter = (
        f"{total_contributions:,} contributions"
    )

    bbox = draw.textbbox(
        (0, 0),
        counter,
        font=FONT_SMALL
    )

    counter_width = (
        bbox[2] - bbox[0]
    )

    draw.text(
        (
            WIDTH -
            counter_width -
            10,
            20
        ),

        counter,

        font=FONT_SMALL,

        fill=TEXT
    )


# ============================================================
# STATUS
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
# RENDER FRAME
# ============================================================

def render_frame(
    weeks,
    active_blocks,
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

    draw = ImageDraw.Draw(image)

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

    draw_weekdays(draw)

    draw_months(
        draw,
        weeks
    )

    # --------------------------------------------------------
    # Glow layer
    # --------------------------------------------------------

    glow = Image.new(
        "RGBA",
        (
            WIDTH,
            HEIGHT
        ),

        (0, 0, 0, 0)
    )

    glow_draw = ImageDraw.Draw(
        glow
    )

    # --------------------------------------------------------
    # Blocks
    # --------------------------------------------------------

    for block in active_blocks:

        draw_block(
            draw,
            glow_draw,
            block
        )

    # --------------------------------------------------------
    # Glow
    # --------------------------------------------------------

    glow = glow.filter(
        ImageFilter.GaussianBlur(6)
    )

    image.alpha_composite(glow)

    # --------------------------------------------------------
    # Redraw blocks over glow
    # --------------------------------------------------------

    draw = ImageDraw.Draw(image)

    for block in active_blocks:

        if block.y < TOP - CELL * 3:
            continue

        x = int(block.x)

        y = int(block.y)

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
    # Bottom status
    # --------------------------------------------------------

    draw_status(
        draw,
        status
    )

    return image.convert("RGB")


# ============================================================
# EASING
# ============================================================

def ease_out_cubic(t):

    t = max(
        0.0,
        min(1.0, t)
    )

    return 1 - (
        1 - t
    ) ** 3


# ============================================================
# GENERATE WEEK ANIMATION
# ============================================================

def animate_week(
    weeks,
    week_index,
    blocks,
    total_contributions
):

    frames = []

    # --------------------------------------------------------
    # Number of frames
    # --------------------------------------------------------

    FALL_FRAMES = 55
    SETTLE_FRAMES = 15
    HOLD_FRAMES = 8

    total_frames = (
        FALL_FRAMES +
        SETTLE_FRAMES
    )

    # --------------------------------------------------------
    # Animate
    # --------------------------------------------------------

    for frame in range(
        total_frames
    ):

        update_blocks(
            blocks,
            frame
        )

        status = (
            f"week {week_index + 1:02d} / "
            f"{len(weeks):02d}"
            "   •   gravity active"
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
    # Hold settled state
    # --------------------------------------------------------

    final = render_frame(
        weeks,
        blocks,
        total_contributions,
        f"week {week_index + 1:02d} / "
        f"{len(weeks):02d}"
        "   •   settled"
    )

    for _ in range(
        HOLD_FRAMES
    ):

        frames.append(
            final.copy()
        )

    return frames


# ============================================================
# FINAL HOLD
# ============================================================

def final_animation(
    weeks,
    all_blocks,
    total_contributions
):

    frames = []

    final = render_frame(
        weeks,
        all_blocks,
        total_contributions,
        "52 weeks  •  contribution history settled"
    )

    for _ in range(45):

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

    # --------------------------------------------------------
    # GitHub normally returns 53 weeks
    # --------------------------------------------------------

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

    frames = []

    all_blocks = []

    # --------------------------------------------------------
    # Animate every week
    # --------------------------------------------------------

    for week_index, week in enumerate(
        weeks
    ):

        print(
            f"Animating week "
            f"{week_index + 1}/"
            f"{len(weeks)}..."
        )

        week_blocks = (
            create_week_blocks(
                week_index,
                week
            )
        )

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # Keep previously settled blocks.
        # Add this week's blocks.
        # ----------------------------------------------------

        all_blocks.extend(
            week_blocks
        )

        week_frames = animate_week(
            weeks,
            week_index,
            week_blocks,
            total_contributions
        )

        # ----------------------------------------------------
        # Re-render using ALL blocks so previous weeks
        # remain visible.
        # ----------------------------------------------------

        for frame in week_frames:

            # We don't need to reconstruct physics here.
            # The frame already represents the current week.

            frames.append(frame)

    # --------------------------------------------------------
    # Final frame
    # --------------------------------------------------------

    frames.extend(
        final_animation(
            weeks,
            all_blocks,
            total_contributions
        )
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
        f"Size:   {WIDTH} × {HEIGHT}"
    )

    print()


if __name__ == "__main__":
    main()