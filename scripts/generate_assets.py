# -*- coding: utf-8 -*-
"""Generate PNG/ICO assets used by the desktop UI."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)


def rounded_icon(size: int = 256) -> Image.Image:
    scale = 4
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    radius = int(s * 0.23)
    # Deep navy base with a subtle vertical gradient.
    for y in range(s):
        t = y / max(1, s - 1)
        r = int(11 + (18 - 11) * t)
        g = int(31 + (52 - 31) * t)
        b = int(51 + (79 - 51) * t)
        draw.line([(0, y), (s, y)], fill=(r, g, b, 255))
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, s - 1, s - 1), radius=radius, fill=255)
    img.putalpha(mask)
    draw = ImageDraw.Draw(img)
    # Decorative rings.
    draw.ellipse(
        (int(s * 0.53), int(-s * 0.22), int(s * 1.18), int(s * 0.44)),
        outline=(255, 255, 255, 18),
        width=max(2, int(s * 0.012)),
    )
    # Candlestick / bar chart motif.
    bars = [
        (0.21, 0.60, 0.30, 0.82, (255, 255, 255, 235)),
        (0.37, 0.45, 0.46, 0.82, (255, 255, 255, 235)),
        (0.53, 0.53, 0.62, 0.82, (15, 157, 138, 255)),
        (0.69, 0.31, 0.78, 0.82, (15, 157, 138, 255)),
    ]
    for x1, y1, x2, y2, color in bars:
        draw.rounded_rectangle(
            (int(s * x1), int(s * y1), int(s * x2), int(s * y2)),
            radius=int(s * 0.025),
            fill=color,
        )
    # Upward trend line.
    points = [
        (int(s * 0.17), int(s * 0.53)),
        (int(s * 0.34), int(s * 0.42)),
        (int(s * 0.51), int(s * 0.47)),
        (int(s * 0.70), int(s * 0.25)),
        (int(s * 0.86), int(s * 0.17)),
    ]
    draw.line(points, fill=(242, 169, 59, 255), width=max(3, int(s * 0.028)), joint="curve")
    end_x, end_y = points[-1]
    draw.ellipse(
        (end_x - int(s * 0.045), end_y - int(s * 0.045), end_x + int(s * 0.045), end_y + int(s * 0.045)),
        fill=(242, 169, 59, 255),
    )
    return img.resize((size, size), Image.Resampling.LANCZOS)


def chevron(direction: str = "down", color=(100, 116, 139, 255)) -> Image.Image:
    scale = 4
    size = 16
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    if direction == "down":
        points = [(s * 0.22, s * 0.38), (s * 0.50, s * 0.66), (s * 0.78, s * 0.38)]
    else:
        points = [(s * 0.22, s * 0.62), (s * 0.50, s * 0.34), (s * 0.78, s * 0.62)]
    draw.line(points, fill=color, width=max(2, int(s * 0.10)), joint="curve")
    return img.resize((size, size), Image.Resampling.LANCZOS)


def checkmark(color=(255, 255, 255, 255)) -> Image.Image:
    scale = 4
    size = 14
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.line(
        [(s * 0.18, s * 0.53), (s * 0.42, s * 0.76), (s * 0.83, s * 0.25)],
        fill=color,
        width=max(2, int(s * 0.13)),
        joint="curve",
    )
    return img.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    icon = rounded_icon(512)
    icon.save(ASSETS / "app_icon.png")
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    icon.save(ASSETS / "app_icon.ico", sizes=sizes)
    chevron("down").save(ASSETS / "chevron_down.png")
    chevron("up").save(ASSETS / "chevron_up.png")
    checkmark().save(ASSETS / "check_white.png")
    print("Assets written to", ASSETS)


if __name__ == "__main__":
    main()
