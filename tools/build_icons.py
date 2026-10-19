"""Build the app icons the packaged build uses, from the d logo.

The Windows exe and the macOS app take their icon from packaging/d-tach.ico
and packaging/d-tach.icns. Both are made from app/static/d-logo.png (1089 px),
not favicon.png, which is only 64 px and blurs at large sizes.

Command, from the repo root:

  python tools/build_icons.py

Rerun it when the logo changes and commit the two icon files.
"""

import argparse
from pathlib import Path
from typing import Final

from PIL import Image

REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE: Final[Path] = REPO_ROOT / "app" / "static" / "d-logo.png"
DEFAULT_OUT_DIR: Final[Path] = REPO_ROOT / "packaging"
ICON_STEM: Final[str] = "d-tach"

# Every size Windows picks from: Explorer views, taskbar, shortcuts, high DPI.
ICO_SIZES: Final[list[tuple[int, int]]] = [
    (16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256),
]
# Largest macOS icon size; Pillow writes the smaller ICNS sizes from it.
ICNS_SIZE: Final[int] = 1024


def square_image(source: Path, size: int) -> Image.Image:
    """Return the source image as an RGBA square of the given size."""
    image = Image.open(source).convert("RGBA")
    if image.width != image.height:
        raise ValueError(f"{source} is {image.width}x{image.height}, the icon source must be square")
    return image.resize((size, size), Image.Resampling.LANCZOS)


def build_ico(source: Path, out_dir: Path) -> Path:
    """Write a multi-size Windows .ico and return its path."""
    target = out_dir / f"{ICON_STEM}.ico"
    square_image(source, ICO_SIZES[-1][0]).save(target, format="ICO", sizes=ICO_SIZES)
    return target


def build_icns(source: Path, out_dir: Path) -> Path:
    """Write a macOS .icns and return its path."""
    target = out_dir / f"{ICON_STEM}.icns"
    square_image(source, ICNS_SIZE).save(target, format="ICNS")
    return target


def main() -> None:
    """Build both icon files."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="square PNG to build from")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR, help="folder to write the icons to")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    for path in (build_ico(args.source, args.out), build_icns(args.source, args.out)):
        print(f"Wrote {path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path}")


if __name__ == "__main__":
    main()
