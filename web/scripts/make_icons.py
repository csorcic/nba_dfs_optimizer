"""Draw the app icons (run once: python web/scripts/make_icons.py)."""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "app" / "icons"
BG, BALL, SEAM = (20, 23, 28), (229, 98, 28), (20, 23, 28)


def draw(size: int, maskable: bool) -> Image.Image:
    s = size * 4  # draw large, then shrink for smooth edges
    img = Image.new("RGB", (s, s), BG)
    d = ImageDraw.Draw(img)
    if not maskable:  # rounded-square look for normal icons
        img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, s - 1, s - 1], radius=s // 5, fill=BG)
    r = s * (0.30 if maskable else 0.36)  # maskable icons keep art inside the safe zone
    cx = cy = s / 2
    w = max(2, int(s * 0.03))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=BALL)
    d.line([cx, cy - r, cx, cy + r], fill=SEAM, width=w)
    d.line([cx - r, cy, cx + r, cy], fill=SEAM, width=w)
    d.arc([cx - 1.9 * r, cy - r, cx - 0.1 * r, cy + r], -60, 60, fill=SEAM, width=w)
    d.arc([cx + 0.1 * r, cy - r, cx + 1.9 * r, cy + r], 120, 240, fill=SEAM, width=w)
    return img.resize((size, size), Image.LANCZOS)


OUT.mkdir(parents=True, exist_ok=True)
draw(192, False).save(OUT / "icon-192.png")
draw(512, False).save(OUT / "icon-512.png")
draw(512, True).save(OUT / "maskable-512.png")
print("icons written to", OUT)
