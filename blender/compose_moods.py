"""Put transparent mood renders on their paper-coloured backgrounds and make a side-by-side sheet.

    python3 blender/compose_moods.py <render_dir> <out_dir>
"""
import sys
from pathlib import Path

from PIL import Image

BACKGROUNDS = {
    "dusk": (238, 226, 210),
    "night": (38, 42, 58),
    "morning": (234, 238, 236),
}
NAMES = {"dusk": "1_해질녘", "night": "2_밤", "morning": "3_아침"}


def main(src, dst):
    src, dst = Path(src), Path(dst)
    dst.mkdir(parents=True, exist_ok=True)
    tiles = []
    for mood, color in BACKGROUNDS.items():
        im = Image.open(src / f"hi_{mood}.png").convert("RGBA")
        bg = Image.new("RGBA", im.size, color + (255,))
        bg.alpha_composite(im)
        flat = bg.convert("RGB")
        flat.save(dst / f"{NAMES[mood]}.png", optimize=True)
        tiles.append(flat)
    w, h = tiles[0].size
    scale = 0.5
    tw, th = int(w * scale), int(h * scale)
    sheet = Image.new("RGB", (tw * len(tiles), th))
    for i, t in enumerate(tiles):
        sheet.paste(t.resize((tw, th), Image.LANCZOS), (i * tw, 0))
    sheet.save(dst / "0_세가지_비교.png", optimize=True)


if __name__ == "__main__":
    main(*sys.argv[1:3])
