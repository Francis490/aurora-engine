"""
generate_icons.py
AURORA ENGINE — Genera icone PWA (192, 512).

FIX (2026-09-29):
- draw_sun ora usa glow_draw per disegnare l'alone (prima ignorato)

Uso:
    python generate_icons.py
"""
from PIL import Image, ImageDraw, ImageFilter
import os


SPACE_DEEP = (26, 11, 46)
SPACE_PURPLE = (60, 25, 100)
AURORA_PURPLE = (139, 60, 224)
AURORA_PINK = (200, 80, 192)
AURORA_CYAN = (6, 182, 212)
SOLAR = (251, 191, 36)
SOLAR_BRIGHT = (253, 230, 138)


def lerp(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def draw_radial_bg(draw, cx, cy, size):
    steps = 200
    max_r = int(size * 0.75)
    for i in range(steps, 0, -1):
        t = i / steps
        r = int(max_r * t)
        intensity = (1 - t) ** 1.8
        color = lerp(SPACE_DEEP, SPACE_PURPLE, intensity)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)


def draw_aurora_arcs(draw, cx, cy, size):
    for i in range(40):
        t = i / 40
        r = size * (0.3 + t * 0.15)
        color = lerp(SPACE_PURPLE, AURORA_PURPLE, t)
        bbox = [cx - r, cy - r * 0.7, cx + r, cy + r * 0.7]
        draw.arc(bbox, start=110, end=250, fill=color, width=3)

    for i in range(40):
        t = i / 40
        r = size * (0.3 + t * 0.15)
        color = lerp(SPACE_PURPLE, AURORA_PINK, t)
        bbox = [cx - r, cy - r * 0.7, cx + r, cy + r * 0.7]
        draw.arc(bbox, start=-70, end=70, fill=color, width=3)

    for i in range(30):
        t = i / 30
        r = size * (0.35 + t * 0.1)
        color = lerp(SPACE_PURPLE, AURORA_CYAN, t)
        bbox = [cx - r, cy - r * 0.7, cx + r, cy + r * 0.7]
        draw.arc(bbox, start=-40, end=40, fill=color, width=2)


def draw_sun(draw, glow_draw, cx, cy, size):
    """
    Disegna il sole. Se glow_draw è fornito, l'alone va su glow_draw
    (così può essere blurrato separatamente).
    """
    sun_r = size * 0.16
    halo_target = glow_draw if glow_draw is not None else draw

    # Alone (va su glow_draw se fornito, altrimenti su draw)
    for i in range(25, 0, -1):
        t = i / 25
        r = sun_r * 2.2 * t
        intensity = (1 - t) ** 1.5
        color = lerp(SPACE_PURPLE, SOLAR, intensity)
        halo_target.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)

    # Disco (sempre su draw)
    draw.ellipse([cx - sun_r, cy - sun_r, cx + sun_r, cy + sun_r], fill=SOLAR)

    # Highlight
    hl_r = sun_r * 0.35
    hl_x = cx - sun_r * 0.3
    hl_y = cy - sun_r * 0.3
    draw.ellipse([hl_x - hl_r, hl_y - hl_r, hl_x + hl_r, hl_y + hl_r],
                 fill=SOLAR_BRIGHT)


def make_icon(size, path):
    cx = cy = size // 2

    img = Image.new("RGBA", (size, size), SPACE_DEEP + (255,))
    draw = ImageDraw.Draw(img)

    draw_radial_bg(draw, cx, cy, size)
    draw_aurora_arcs(draw, cx, cy, size)

    # Crea glow separato
    glow = Image.new("RGB", (size, size), (0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    draw_sun(draw, gdraw, cx, cy, size)

    # Blur + blend
    glow_blur = glow.filter(ImageFilter.GaussianBlur(radius=max(2, size // 30)))
    blended = Image.blend(img.convert("RGB"), glow_blur, alpha=0.5)
    img = blended.convert("RGBA")

    # Ridisegna il sole in primo piano
    draw = ImageDraw.Draw(img)
    draw_sun(draw, None, cx, cy, size)

    img.save(path, "PNG", optimize=True)
    print(f"[+] {path} ({size}x{size})")


if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))
    make_icon(192, os.path.join(base, "icon-192.png"))
    make_icon(512, os.path.join(base, "icon-512.png"))
    print("[OK] Icone Aurora generate.")
