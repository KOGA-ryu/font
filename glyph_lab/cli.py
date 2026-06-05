from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ascii_bridge import import_ascii_grid
from .ascii_promotion import write_ascii_promotion_request
from .atlas import generate_pack
from .compiler import compile_grid
from .compositor import compile_layered_grid
from .contact_sheet import generate_contact_sheet
from .candidate_filter import write_candidate_review
from .generate_candidates import write_primitive_review
from .grooves import measure_rhythm_image
from .image_to_layers import probe_image_to_layers
from .linework_candidates import write_linework_review
from .measurement_pass import write_art_pass_measurements
from .object_hints import write_object_hints
from .profiles import measure_profile_image
from .promotion import promote_candidates
from .review_export import generate_review_contact_sheet
from .scaffold import measure_scaffold_image


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

    layered_parser = subparsers.add_parser("compile-layered", help="compile a layered control grid to PNG layers")
    layered_parser.add_argument("--pack", default=str(DEFAULT_PACK))
    layered_parser.add_argument("--input", default="examples/layered_stone_post.json")
    layered_parser.add_argument("--out", default="out_layered")

    probe_parser = subparsers.add_parser("probe-image", help="probe an image into a layered glyph grid")
    probe_parser.add_argument("--pack", default=str(DEFAULT_PACK))
    probe_parser.add_argument("--image", required=True)
    probe_parser.add_argument("--out", default="out_probe")
    probe_parser.add_argument("--grid-size", type=int, default=32)

    profile_parser = subparsers.add_parser("measure-profile", help="measure a silhouette profile from an image")
    profile_parser.add_argument("--image", required=True)
    profile_parser.add_argument("--out", default="out_profile")
    profile_parser.add_argument("--grid-size", type=int, default=32)

    rhythm_parser = subparsers.add_parser("measure-rhythm", help="measure repeated grooves and bands from an image")
    rhythm_parser.add_argument("--image", required=True)
    rhythm_parser.add_argument("--out", default="out_rhythm")
    rhythm_parser.add_argument("--grid-size", type=int, default=32)

    scaffold_parser = subparsers.add_parser("measure-scaffold", help="measure a construction support scaffold")
    scaffold_parser.add_argument("--image", required=True)
    scaffold_parser.add_argument("--out", default="out_scaffold")
    scaffold_parser.add_argument("--grid-size", type=int, default=32)

    hint_parser = subparsers.add_parser("hint-object", help="fuse measurements into object-family hints")
    hint_parser.add_argument("--profile")
    hint_parser.add_argument("--rhythm")
    hint_parser.add_argument("--probe")
    hint_parser.add_argument("--out", default="out_hint")

    art_measure_parser = subparsers.add_parser(
        "measure-from-art-passes",
        help="create final measurements from organized art-pass evidence",
    )
    art_measure_parser.add_argument("--probe")
    art_measure_parser.add_argument("--profile")
    art_measure_parser.add_argument("--rhythm")
    art_measure_parser.add_argument("--layered")
    art_measure_parser.add_argument("--out", default="out_measure_art")

    review_parser = subparsers.add_parser("review-candidates", help="score generated variants")
    review_parser.add_argument("--pack", default=str(DEFAULT_PACK))

    primitive_parser = subparsers.add_parser("generate-primitives", help="generate primitive candidate review artifacts")
    primitive_parser.add_argument("--pack", default=str(DEFAULT_PACK))

    linework_parser = subparsers.add_parser("generate-linework", help="generate linework glyph kit review artifacts")
    linework_parser.add_argument("--pack", default=str(DEFAULT_PACK))

    ascii_parser = subparsers.add_parser("import-ascii-grid", help="import ASCII output as a layered glyph grid")
    ascii_parser.add_argument("--pack", default=str(DEFAULT_PACK))
    ascii_parser.add_argument("--ascii", required=True)
    ascii_parser.add_argument("--mapping", required=True)
    ascii_parser.add_argument("--out", default="out_ascii_bridge")

    suggest_parser = subparsers.add_parser(
        "suggest-ascii-promotions",
        help="write a promotion request from ASCII bridge fallback warnings",
    )
    suggest_parser.add_argument("--manifest", required=True)
    suggest_parser.add_argument("--mapping", required=True)
    suggest_parser.add_argument("--accepted", required=True)
    suggest_parser.add_argument("--out", required=True)
    suggest_parser.add_argument("--limit", type=int)

    promote_parser = subparsers.add_parser("promote-candidates", help="promote reviewed candidates")
    promote_parser.add_argument("--pack", default=str(DEFAULT_PACK))
    promote_parser.add_argument("--request", required=True)
    promote_parser.add_argument("--accepted")
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

    if args.command == "compile-layered":
        compile_layered_grid(pack / "atlas.png", pack / "glyphs.json", args.input, args.out)
        return

    if args.command == "probe-image":
        probe_image_to_layers(args.image, pack, args.out, grid_size=args.grid_size)
        return

    if args.command == "measure-profile":
        measure_profile_image(args.image, args.out, grid_size=args.grid_size)
        return

    if args.command == "measure-rhythm":
        measure_rhythm_image(args.image, args.out, grid_size=args.grid_size)
        return

    if args.command == "measure-scaffold":
        measure_scaffold_image(args.image, args.out, grid_size=args.grid_size)
        return

    if args.command == "hint-object":
        write_object_hints(
            _load_json(args.profile) if args.profile else None,
            _load_json(args.rhythm) if args.rhythm else None,
            args.out,
            probe=_load_json(args.probe) if args.probe else None,
        )
        return

    if args.command == "measure-from-art-passes":
        write_art_pass_measurements(
            args.out,
            probe=_load_json(args.probe) if args.probe else None,
            profile=_load_json(args.profile) if args.profile else None,
            rhythm=_load_json(args.rhythm) if args.rhythm else None,
            layered=_load_json(args.layered) if args.layered else None,
        )
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

    if args.command == "generate-linework":
        write_linework_review(pack)
        return

    if args.command == "import-ascii-grid":
        import_ascii_grid(pack, args.ascii, args.mapping, args.out)
        return

    if args.command == "suggest-ascii-promotions":
        write_ascii_promotion_request(args.manifest, args.mapping, args.accepted, args.out, limit=args.limit)
        return

    if args.command == "promote-candidates":
        promote_candidates(pack, args.request, apply=args.apply, accepted_path=args.accepted)


def _load_json(path: str) -> dict:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


if __name__ == "__main__":
    main()
