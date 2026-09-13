import os
import math
import random
import requests

from PIL import Image, ImageDraw, ImageFilter


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
FRAMES = 240

OUTPUT = "assets/lava-flow.gif"

BACKGROUND = (5, 5, 8)


# ============================================================
# LAVA PALETTE
# ============================================================

# Dark -> hot
LAVA_STOPS = [
    (18, 5, 5),
    (55, 8, 4),
    (105, 15, 3),
    (170, 30, 2),
    (225, 65, 3),
    (255, 120, 5),
    (255, 185, 25),
    (255, 235, 120),
]


# ============================================================
# GITHUB GRAPHQL
# ============================================================

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
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


def fetch_contributions():

    token = os.environ.get("GITHUB_TOKEN")

    if not token:
        raise RuntimeError(
            "GITHUB_TOKEN environment variable is missing."
        )

    response = requests.post(
        "https://api.github.com/graphql",
        json={
            "query": QUERY,
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
        raise RuntimeError(data["errors"])

    return (
        data["data"]["user"]
        ["contributionsCollection"]
        ["contributionCalendar"]
        ["weeks"]
    )


# ============================================================
# CONTRIBUTION LEVEL
# ============================================================

def contribution_level(count):

    if count == 0:
        return 0

    if count <= 2:
        return 1

    if count <= 5:
        return 2

    if count <= 9:
        return 3

    return 4


# ============================================================
# COLOR INTERPOLATION
# ============================================================

def lava_color(value):

    value = max(
        0.0,
        min(7.0, value)
    )

    index = int(value)

    if index >= len(LAVA_STOPS) - 1:
        return LAVA_STOPS[-1]

    fraction = value - index

    a = LAVA_STOPS[index]
    b = LAVA_STOPS[index + 1]

    return tuple(
        int(
            a[i] +
            (b[i] - a[i]) * fraction
        )
        for i in range(3)
    )


# ============================================================
# SMOOTH WAVE
# ============================================================

def wave(x):

    return (
        math.sin(x) +
        math.sin(x * 0.47) * 0.5 +
        math.sin(x * 0.19) * 0.25
    )


# ============================================================
# BUILD CONTRIBUTION GRID
# ============================================================

def build_grid(weeks):

    grid = [
        [0 for _ in range(MAX_WEEKS)]
        for _ in range(ROWS)
    ]

    recent = weeks[-MAX_WEEKS:]

    for x, week in enumerate(recent):

        for y, day in enumerate(
            week["contributionDays"]
        ):

            if y >= ROWS:
                continue

            grid[y][x] = contribution_level(
                day["contributionCount"]
            )

    return grid


# ============================================================
# LAVA SIMULATION
# ============================================================

def simulate_lava(base_grid, frame):

    heat = [
        [
            base_grid[y][x] * 1.15
            for x in range(MAX_WEEKS)
        ]
        for y in range(ROWS)
    ]

    # --------------------------------------------------------
    # MOVING HEAT FIELD
    # --------------------------------------------------------

    for y in range(ROWS):

        for x in range(MAX_WEEKS):

            # Flow direction changes over time
            flow_x = (
                math.sin(
                    frame * 0.035 +
                    y * 0.9
                ) * 0.55
            )

            flow_y = (
                math.cos(
                    frame * 0.028 +
                    x * 0.25
                ) * 0.35
            )

            sx = int(
                max(
                    0,
                    min(
                        MAX_WEEKS - 1,
                        x + flow_x
                    )
                )
            )

            sy = int(
                max(
                    0,
                    min(
                        ROWS - 1,
                        y + flow_y
                    )
                )
            )

            heat[y][x] += (
                base_grid[sy][sx] * 0.8
            )

    # --------------------------------------------------------
    # DIFFUSION
    # --------------------------------------------------------

    result = [
        row[:]
        for row in heat
    ]

    for y in range(ROWS):

        for x in range(MAX_WEEKS):

            neighbors = []

            for dy, dx in [
                (-1, 0),
                (1, 0),
                (0, -1),
                (0, 1),
                (-1, -1),
                (-1, 1),
                (1, -1),
                (1, 1)
            ]:

                ny = y + dy
                nx = x + dx

                if (
                    0 <= ny < ROWS and
                    0 <= nx < MAX_WEEKS
                ):
                    neighbors.append(
                        heat[ny][nx]
                    )

            if neighbors:

                average = (
                    sum(neighbors) /
                    len(neighbors)
                )

                result[y][x] = (
                    heat[y][x] * 0.72 +
                    average * 0.28
                )

    # --------------------------------------------------------
    # MOVING HOTSPOTS
    # --------------------------------------------------------

    for hotspot in range(9):

        hx = (
            (frame * (0.035 + hotspot * 0.004))
            +
            hotspot * 6.7
        ) % MAX_WEEKS

        hy = (
            ROWS / 2
            +
            math.sin(
                frame * 0.035 +
                hotspot
            ) * 2.2
        )

        strength = (
            1.5 +
            math.sin(
                frame * 0.06 +
                hotspot
            ) * 0.6
        )

        for y in range(ROWS):

            for x in range(MAX_WEEKS):

                distance = math.sqrt(
                    (x - hx) ** 2 +
                    (y - hy) ** 2
                )

                influence = math.exp(
                    -(distance ** 2) / 5.0
                )

                result[y][x] += (
                    influence *
                    strength
                )

    # --------------------------------------------------------
    # EDGE COOLING
    # --------------------------------------------------------

    for y in range(ROWS):

        for x in range(MAX_WEEKS):

            result[y][x] *= 0.92

            # Keep contribution cells alive
            result[y][x] += (
                base_grid[y][x] * 0.35
            )

    return result


# ============================================================
# DRAW GLOW
# ============================================================

def draw_glow(img, x, y, intensity):

    if intensity < 3.0:
        return

    glow = Image.new(
        "RGBA",
        img.size,
        (0, 0, 0, 0)
    )

    gd = ImageDraw.Draw(glow)

    radius = int(
        4 + intensity * 1.2
    )

    alpha = int(
        min(
            120,
            25 + intensity * 10
        )
    )

    gd.rounded_rectangle(
        [
            x - radius,
            y - radius,
            x + CELL + radius,
            y + CELL + radius
        ],
        radius=radius,
        fill=(
            255,
            70,
            5,
            alpha
        )
    )

    glow = glow.filter(
        ImageFilter.GaussianBlur(
            radius=5
        )
    )

    img.alpha_composite(glow)


# ============================================================
# DRAW LAVA CELL
# ============================================================

def draw_lava_cell(
    draw,
    x,
    y,
    intensity,
    frame,
    cell_x,
    cell_y
):

    color = lava_color(intensity)

    # --------------------------------------------------------
    # Organic edge distortion
    # --------------------------------------------------------

    distortion = (
        math.sin(
            frame * 0.08 +
            cell_x * 1.7 +
            cell_y * 2.1
        ) * 1.1
    )

    radius = int(
        max(
            2,
            3 + distortion
        )
    )

    # --------------------------------------------------------
    # Outer dark molten edge
    # --------------------------------------------------------

    draw.rounded_rectangle(
        [
            x - 1,
            y - 1,
            x + CELL + 1,
            y + CELL + 1
        ],
        radius=radius + 1,
        fill=(12, 5, 5)
    )

    # --------------------------------------------------------
    # Main lava
    # --------------------------------------------------------

    draw.rounded_rectangle(
        [
            x,
            y,
            x + CELL,
            y + CELL
        ],
        radius=radius,
        fill=color
    )

    # --------------------------------------------------------
    # Moving hot core
    # --------------------------------------------------------

    if intensity > 4.5:

        pulse = (
            math.sin(
                frame * 0.15 +
                cell_x +
                cell_y
            ) + 1
        ) / 2

        core = int(
            2 + pulse * 3
        )

        core_color = (
            255,
            225,
            100
        )

        draw.rounded_rectangle(
            [
                x + core,
                y + core,
                x + CELL - core,
                y + CELL - core
            ],
            radius=2,
            fill=core_color
        )


# ============================================================
# FRAME GENERATION
# ============================================================

def generate_frame(
    base_grid,
    frame
):

    heat = simulate_lava(
        base_grid,
        frame
    )

    img = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        BACKGROUND + (255,)
    )

    # ========================================================
    # HEADER
    # ========================================================

    draw = ImageDraw.Draw(img)

    draw.text(
        (LEFT, 18),
        "CONTRIBUTION HEAT",
        fill=(235, 225, 225)
    )

    draw.text(
        (LEFT, 39),
        "activity is molten",
        fill=(120, 100, 100)
    )

    # ========================================================
    # GLOW PASS
    # ========================================================

    for y in range(ROWS):

        for x in range(MAX_WEEKS):

            intensity = heat[y][x]

            px = (
                LEFT +
                x * (CELL + GAP)
            )

            py = (
                TOP +
                y * (CELL + GAP)
            )

            draw_glow(
                img,
                px,
                py,
                intensity
            )

    # ========================================================
    # LAVA PASS
    # ========================================================

    draw = ImageDraw.Draw(img)

    for y in range(ROWS):

        for x in range(MAX_WEEKS):

            intensity = heat[y][x]

            # Don't completely erase empty GitHub cells
            if intensity < 0.15:

                intensity = 0

            px = (
                LEFT +
                x * (CELL + GAP)
            )

            py = (
                TOP +
                y * (CELL + GAP)
            )

            draw_lava_cell(
                draw,
                px,
                py,
                intensity,
                frame,
                x,
                y
            )

    return img.convert("RGB")


# ============================================================
# GENERATE GIF
# ============================================================

def generate_animation(weeks):

    base_grid = build_grid(
        weeks
    )

    frames = []

    print(
        f"Generating {FRAMES} lava frames..."
    )

    for frame in range(FRAMES):

        if frame % 20 == 0:

            print(
                f"Frame {frame}/{FRAMES}"
            )

        frames.append(
            generate_frame(
                base_grid,
                frame
            )
        )

    return frames


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "Fetching GitHub contribution data..."
    )

    weeks = fetch_contributions()

    print(
        "GitHub contribution data loaded."
    )

    frames = generate_animation(
        weeks
    )

    os.makedirs(
        os.path.dirname(OUTPUT),
        exist_ok=True
    )

    print(
        "Saving GIF..."
    )

    frames[0].save(
        OUTPUT,
        save_all=True,
        append_images=frames[1:],
        duration=int(
            1000 / FPS
        ),
        loop=0,
        optimize=False
    )

    print()
    print(
        "================================"
    )
    print(
        "LAVA FLOW GENERATED"
    )
    print(
        "================================"
    )
    print(
        f"Output : {OUTPUT}"
    )
    print(
        f"Frames : {len(frames)}"
    )
    print(
        f"Size   : {WIDTH} × {HEIGHT}"
    )
    print(
        f"FPS    : {FPS}"
    )


if __name__ == "__main__":
    main()