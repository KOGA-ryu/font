from __future__ import annotations

import argparse
from pathlib import Path

from .atlas import generate_pack
from .compiler import compile_grid
from .contact_sheet import generate_contact_sheet


DEFAULT_PACK = Path("packs/stone_architecture_4x4")


def main() -> None:
    parser = argparse.ArgumentParser(prog="glyph_lab", description="Compile 4x4 glyph brush grids.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-pack", help="generate the default glyph pack")
    init_parser.add_argument("--pack", default=str(DEFAULT_PACK))

    sheet_parser = subparsers.add_parser("contact-sheet", help="generate a contact sheet")
    sheet_parser.add_argument("--pack", default=str(DEFAULT_PACK))

    compile_parser = subparsers.add_parser("compile", help="compile a control grid to PNG layers")
    compile_parser.add_argument("--pack", default=str(DEFAULT_PACK))
    compile_parser.add_argument("--grid", default="examples/stone_post_grid.txt")
    compile_parser.add_argument("--out", default="out")

    args = parser.parse_args()
    pack = Path(getattr(args, "pack", DEFAULT_PACK))

    if args.command == "init-pack":
        generate_pack(pack)
        generate_contact_sheet(pack / "atlas.png", pack / "glyphs.json", pack / "contact_sheet.png")
        return

    if args.command == "contact-sheet":
        generate_contact_sheet(pack / "atlas.png", pack / "glyphs.json", pack / "contact_sheet.png")
        return

    if args.command == "compile":
        compile_grid(pack / "atlas.png", pack / "glyphs.json", args.grid, args.out)


if __name__ == "__main__":
    main()
