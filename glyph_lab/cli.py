from __future__ import annotations

import argparse
from pathlib import Path

from .atlas import generate_pack
from .compiler import compile_grid
from .contact_sheet import generate_contact_sheet
from .candidate_filter import write_candidate_review
from .generate_candidates import write_primitive_review
from .promotion import promote_candidates
from .review_export import generate_review_contact_sheet


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

    review_parser = subparsers.add_parser("review-candidates", help="score generated variants")
    review_parser.add_argument("--pack", default=str(DEFAULT_PACK))

    primitive_parser = subparsers.add_parser("generate-primitives", help="generate primitive candidate review artifacts")
    primitive_parser.add_argument("--pack", default=str(DEFAULT_PACK))

    promote_parser = subparsers.add_parser("promote-candidates", help="promote reviewed candidates")
    promote_parser.add_argument("--pack", default=str(DEFAULT_PACK))
    promote_parser.add_argument("--request", required=True)
    promote_parser.add_argument("--apply", action="store_true")

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
        return

    if args.command == "review-candidates":
        result = write_candidate_review(pack)
        generate_review_contact_sheet(
            result["accepted_candidates"],
            result["rejected_candidates"],
            pack / "review_contact_sheet.png",
        )
        return

    if args.command == "generate-primitives":
        write_primitive_review(pack)
        return

    if args.command == "promote-candidates":
        promote_candidates(pack, args.request, apply=args.apply)


if __name__ == "__main__":
    main()
