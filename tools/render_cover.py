#!/usr/bin/env python3
import argparse
import os
from pathlib import Path
from typing import Tuple, Optional

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

try:
    # Optional background remover for cutouts
    from rembg import remove as rembg_remove  # type: ignore
    HAS_REMBG = True
except Exception:
    HAS_REMBG = False


BLUE = (0, 87, 184, 255)      # #0057B8
WHITE = (255, 255, 255, 255)  
YELLOW = (255, 210, 0, 255)   # #FFD200
RED = (212, 0, 0, 255)        # #D40000
CONFETTI_COLORS = [BLUE, WHITE, YELLOW, RED]


def load_image(path: Optional[str]) -> Optional[Image.Image]:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        print(f"[warn] Bild nicht gefunden: {p}")
        return None
    img = Image.open(p).convert("RGBA")
    return img


def ensure_square_canvas(img: Image.Image, size: int) -> Image.Image:
    """Pad to square then resize preserving aspect ratio."""
    w, h = img.size
    scale = size / max(w, h)
    new_w, new_h = int(w * scale), int(h * scale)
    img_resized = img.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    x = (size - new_w) // 2
    y = (size - new_h) // 2
    canvas.alpha_composite(img_resized, (x, y))
    return canvas


def add_confetti(base: Image.Image, density: float = 0.0015, seed: int = 1234) -> None:
    rng = np.random.default_rng(seed)
    w, h = base.size
    num = int(w * h * density)
    draw = ImageDraw.Draw(base, "RGBA")
    # Diagonaler "Fluss"
    for _ in range(num):
        color = CONFETTI_COLORS[rng.integers(low=0, high=len(CONFETTI_COLORS))]
        size = int(rng.uniform(6, 22))
        x = int(rng.uniform(-w * 0.1, w * 1.1))
        y = int(rng.uniform(-h * 0.1, h * 1.1))
        # 50% Kreise, 50% Rechtecke, 10% Dreiecke
        r = rng.random()
        rot = float(rng.uniform(0, 360))
        shape_img = Image.new("RGBA", (size * 2, size * 2), (0, 0, 0, 0))
        sdraw = ImageDraw.Draw(shape_img)
        if r < 0.5:
            sdraw.ellipse((0, 0, size, size), fill=color)
        elif r < 0.9:
            sdraw.rounded_rectangle((0, 0, size, size), radius=size * 0.2, fill=color)
        else:
            sdraw.polygon([(0, size), (size / 2, 0), (size, size)], fill=color)
        shape_img = shape_img.rotate(rot, expand=True, resample=Image.BICUBIC)
        # leichte Bewegungsunschärfe
        if rng.random() < 0.35:
            shape_img = shape_img.filter(ImageFilter.GaussianBlur(radius=rng.uniform(0.3, 1.1)))
        base.alpha_composite(shape_img, (x, y))


def add_vignette(img: Image.Image, strength: float = 0.35) -> None:
    w, h = img.size
    vignette = Image.new("L", (w, h), 0)
    xv, yv = np.meshgrid(np.linspace(-1, 1, w), np.linspace(-1, 1, h))
    r = np.sqrt(xv**2 + yv**2)
    mask = np.clip((r - 0.5) / (1.0 - 0.5), 0, 1)
    mask = (mask * 255 * strength).astype(np.uint8)
    vignette.putdata(mask.reshape(-1))
    dark = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    img.alpha_composite(dark, (0, 0), vignette)


def add_text_with_stroke(
    img: Image.Image,
    text: str,
    font_path: Optional[str],
    font_size: int,
    position: Tuple[int, int],
    fill: Tuple[int, int, int, int] = (255, 255, 255, 255),
    stroke_width: int = 6,
    stroke_fill: Tuple[int, int, int, int] = (0, 0, 0, 200),
    shadow: bool = True,
):
    draw = ImageDraw.Draw(img)
    try:
        if font_path and Path(font_path).exists():
            font = ImageFont.truetype(font_path, font_size)
        else:
            # Fallback system font
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()
    x, y = position
    # Schatten
    if shadow:
        shadow_img = Image.new("RGBA", img.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_img)
        for dx, dy in [(2, 2), (3, 3), (4, 4)]:
            shadow_draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0, 120))
        shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(radius=2))
        img.alpha_composite(shadow_img)
    # Stroke
    for dx in range(-stroke_width, stroke_width + 1):
        for dy in range(-stroke_width, stroke_width + 1):
            if dx * dx + dy * dy <= stroke_width * stroke_width:
                draw.text((x + dx, y + dy), text, font=font, fill=stroke_fill)
    # Fill
    draw.text((x, y), text, font=font, fill=fill)


def overlay_image(
    base: Image.Image, overlay: Image.Image, pos: Tuple[int, int], size_w: int
) -> None:
    # Resize by width keeping AR
    ow, oh = overlay.size
    scale = size_w / float(ow)
    nh = int(oh * scale)
    overlay_resized = overlay.resize((size_w, nh), Image.LANCZOS)
    base.alpha_composite(overlay_resized, pos)


def cutout(img: Image.Image) -> Image.Image:
    if HAS_REMBG:
        try:
            cut = rembg_remove(img)
            return cut.convert("RGBA")
        except Exception:
            pass
    return img


def compose_variant(
    variant_idx: int,
    size: int,
    out_dir: Path,
    dom_path: Optional[str],
    schwell_paths: Tuple[Optional[str], Optional[str], Optional[str]],
    parade_path: Optional[str],
    font_path: Optional[str],
    title_text: str,
):
    canvas = Image.new("RGBA", (size, size), (20, 24, 28, 255))

    # Hintergrund (Dom)
    dom_img = load_image(dom_path)
    if dom_img is not None:
        dom_img = ensure_square_canvas(dom_img, size)
        # leichter Klarheits-Boost
        dom_blur = dom_img.filter(ImageFilter.GaussianBlur(radius=1.0))
        sharpen = Image.blend(dom_img, dom_blur, alpha= -0.25)
        canvas.alpha_composite(sharpen)
    else:
        # Fallback Verlauf
        grad = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        top = (30, 80, 160, 255)
        bottom = (250, 220, 120, 255)
        for y in range(size):
            t = y / (size - 1)
            r = int(top[0] * (1 - t) + bottom[0] * t)
            g = int(top[1] * (1 - t) + bottom[1] * t)
            b = int(top[2] * (1 - t) + bottom[2] * t)
            a = 255
            ImageDraw.Draw(grad).line([(0, y), (size, y)], fill=(r, g, b, a))
        canvas.alpha_composite(grad)

    # Parade Layer mittig
    parade_img = load_image(parade_path)
    if parade_img is not None:
        parade_img = cutout(parade_img)
        overlay_image(canvas, parade_img, (int(size*0.05), int(size*0.55)), int(size*0.9))

    # Schwellköpfe links/rechts/vorne
    positions = [
        (int(size * 0.06), int(size * 0.48), int(size * 0.36)),
        (int(size * 0.56), int(size * 0.50), int(size * 0.38)),
        (int(size * 0.28), int(size * 0.40), int(size * 0.52)),
    ]
    jitter = [(0, 0), (20, -15), (-25, 10)]
    for idx, spath in enumerate(schwell_paths):
        simg = load_image(spath)
        if simg is None:
            continue
        simg = cutout(simg)
        x, y, w = positions[(idx + variant_idx) % len(positions)]
        jx, jy = jitter[(idx + variant_idx) % len(jitter)]
        overlay_image(canvas, simg, (x + jx, y + jy), w)

    # Konfetti
    add_confetti(canvas, density=0.002 + 0.0005 * variant_idx, seed=1234 + variant_idx)

    # Vignette
    add_vignette(canvas, 0.30)

    # Titel
    add_text_with_stroke(
        canvas,
        title_text,
        font_path=font_path,
        font_size=int(size * 0.08),
        position=(int(size * 0.08), int(size * 0.06)),
        fill=YELLOW,
        stroke_width=int(size * 0.006),
        stroke_fill=(0, 0, 0, 220),
    )

    # Unterzeile optional
    sub = "Mainz Fastnacht"
    add_text_with_stroke(
        canvas,
        sub,
        font_path=font_path,
        font_size=int(size * 0.035),
        position=(int(size * 0.08), int(size * 0.16)),
        fill=WHITE,
        stroke_width=int(size * 0.0035),
        stroke_fill=(0, 0, 0, 200),
        shadow=False,
    )

    # Export 4096 und 3000
    out_4k = out_dir / f"cover_v{variant_idx+1}_4096.png"
    out_3k = out_dir / f"cover_v{variant_idx+1}_3000.png"
    canvas_4k = canvas.resize((4096, 4096), Image.LANCZOS)
    canvas_4k.save(out_4k)
    canvas_3k = canvas.resize((3000, 3000), Image.LANCZOS)
    # leicht schärfen nach Skalierung
    canvas_3k = canvas_3k.filter(ImageFilter.UnsharpMask(radius=1.0, percent=120, threshold=3))
    canvas_3k.save(out_3k)
    print(f"[ok] Exportiert: {out_4k} und {out_3k}")


def main():
    parser = argparse.ArgumentParser(description="Render Mainz Fastnacht Cover")
    parser.add_argument("--title", default="Jetzt geht's wieder los")
    parser.add_argument("--size", type=int, default=4096)
    parser.add_argument("--dom")
    parser.add_argument("--schwell1")
    parser.add_argument("--schwell2")
    parser.add_argument("--schwell3")
    parser.add_argument("--parade")
    parser.add_argument("--font", help="Pfad zu einer verspielten TTF, z.B. Bungee/Fredoka")
    parser.add_argument("--out", default="/workspace/assets/outputs")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    for i in range(3):
        compose_variant(
            i,
            args.size,
            out_dir,
            dom_path=args.dom,
            schwell_paths=(args.schwell1, args.schwell2, args.schwell3),
            parade_path=args.parade,
            font_path=args.font,
            title_text=args.title,
        )


if __name__ == "__main__":
    main()
