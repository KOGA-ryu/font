from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ascii_bridge import import_ascii_grid
from .ascii_compare import compare_ascii_fallbacks
from .ascii_glyph_renderer import render_ascii_glyphs
from .ascii_promotion import write_ascii_promotion_request
from .attachments import build_attachment_recipe
from .atlas import generate_pack
from .body_ascii import render_body_ascii_proof
from .brush_candidates import write_brush_review
from .color_family_layers import render_color_family_layers
from .compiler import compile_grid
from .compositor import compile_layered_grid
from .contact_sheet import generate_contact_sheet
from .candidate_filter import write_candidate_review
from .eyedropper import parse_grid_size, parse_point, write_eyedropper_json
from .extraction_sequence import render_extraction_sequence
from .foreground_mask import FOREGROUND_MODES
from .generate_candidates import write_primitive_review
from .grooves import measure_rhythm_image
from .humanoid_regions import classify_humanoid_regions
from .image_to_layers import probe_image_to_layers
from .layer_breakdown import write_layer_breakdown
from .layer_recipe import render_layer_recipe
from .linework_analyzer import analyze_linework_image
from .linework_candidates import write_linework_review
from .mannequin import build_mannequin_recipe
from .mannequin_proof import render_mannequin_proof
from .mannequin_template import generate_mannequin_template
from .measurement_pass import write_art_pass_measurements
from .motion_taxonomy import write_linework_motion_coverage
from .object_hints import write_object_hints
from .profiles import measure_profile_image
from .promotion import promote_candidates
from .promoted_contact_sheet import generate_promoted_contact_sheet
from .promoted_atlas import build_promoted_atlas
from .reference_render import render_reference_style
from .reference_style import build_reference_style_recipe
from .review_export import generate_review_contact_sheet
from .scaffold import measure_scaffold_image
from .skeleton_fit import fit_skeleton
from .sprite_parts import classify_sprite_parts
from .threshold_layers import DEFAULT_THRESHOLDS, parse_thresholds, render_threshold_color_layers


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

    linework_image_parser = subparsers.add_parser(
        "analyze-linework-image",
        help="analyze image linework into a motion-declared layered grid",
    )
    linework_image_parser.add_argument("--pack", default=str(DEFAULT_PACK))
    linework_image_parser.add_argument("--image", required=True)
    linework_image_parser.add_argument("--out", default="out_linework_motion")
    linework_image_parser.add_argument("--grid-size", type=int, default=32)
    linework_image_parser.add_argument("--glyphs")
    linework_image_parser.add_argument("--atlas")

    breakdown_parser = subparsers.add_parser(
        "layer-breakdown",
        help="render a visual breakdown of image evidence and glyph layers",
    )
    breakdown_parser.add_argument("--pack", default=str(DEFAULT_PACK))
    breakdown_parser.add_argument("--image", required=True)
    breakdown_parser.add_argument("--motion-out")
    breakdown_parser.add_argument("--out", default="out_layer_breakdown")
    breakdown_parser.add_argument("--grid-size", type=int, default=32)

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

    linework_coverage_parser = subparsers.add_parser(
        "linework-coverage",
        help="write a motion-taxonomy coverage report for linework records",
    )
    linework_coverage_parser.add_argument("--glyphs", required=True)
    linework_coverage_parser.add_argument("--out", required=True)

    mannequin_template_parser = subparsers.add_parser(
        "generate-mannequin-template",
        help="generate a deterministic front-view mannequin template and region map",
    )
    mannequin_template_parser.add_argument("--out", required=True)
    mannequin_template_parser.add_argument("--width", type=int, default=128)
    mannequin_template_parser.add_argument("--height", type=int, default=192)
    mannequin_template_parser.add_argument("--scale", type=int, default=2)
    mannequin_template_parser.add_argument("--view", choices=["front", "side"], default="front")

    brush_parser = subparsers.add_parser("generate-brushes", help="generate texture brush glyph review artifacts")
    brush_parser.add_argument("--pack", default=str(DEFAULT_PACK))

    eyedropper_parser = subparsers.add_parser("eyedropper-sample", help="sample image colors into JSON")
    eyedropper_parser.add_argument("--image", required=True)
    eyedropper_parser.add_argument("--out", required=True)
    eyedropper_parser.add_argument(
        "--point",
        action="append",
        default=[],
        help="sample point as x,y or label:x,y; repeat for multiple samples",
    )
    eyedropper_parser.add_argument("--grid-size", help="also sample grid cell centers as WIDTHxHEIGHT")
    eyedropper_parser.add_argument("--base-json", help="merge samples into an existing JSON object")
    eyedropper_parser.add_argument("--json-key", default="eyedropper_samples")

    ascii_parser = subparsers.add_parser("import-ascii-grid", help="import ASCII output as a layered glyph grid")
    ascii_parser.add_argument("--pack", default=str(DEFAULT_PACK))
    ascii_parser.add_argument("--ascii", required=True)
    ascii_parser.add_argument("--mapping", required=True)
    ascii_parser.add_argument("--glyphs")
    ascii_parser.add_argument("--atlas")
    ascii_parser.add_argument("--out", default="out_ascii_bridge")

    ascii_render_parser = subparsers.add_parser(
        "render-ascii-glyphs",
        help="render an ASCII token grid directly with 4x4 glyph atlas stamps",
    )
    ascii_render_parser.add_argument("--ascii", required=True)
    ascii_render_parser.add_argument("--glyphs", required=True)
    ascii_render_parser.add_argument("--atlas", required=True)
    ascii_render_parser.add_argument("--mapping")
    ascii_render_parser.add_argument("--gate-image")
    ascii_render_parser.add_argument(
        "--gate-mode",
        choices=["alpha", "black", "luminance", "border-difference", "sample-colors"],
        default="border-difference",
    )
    ascii_render_parser.add_argument("--gate-threshold", type=int, default=32)
    ascii_render_parser.add_argument("--gate-dilate", type=int, default=1)
    ascii_render_parser.add_argument("--gate-mask-out")
    ascii_render_parser.add_argument("--gate-samples", help="eyedropper JSON for sample-colors gate mode")
    ascii_render_parser.add_argument("--gate-sample-key", default="eyedropper_samples")
    ascii_render_parser.add_argument(
        "--gate-include-box",
        action="append",
        default=[],
        help="limit kept gate cells to source-image box x0,y0,x1,y1; repeat for multiple boxes",
    )
    ascii_render_parser.add_argument(
        "--gate-fill-token",
        help="force this glyph token into every kept gate-mask cell, including ASCII spaces",
    )
    ascii_render_parser.add_argument(
        "--ink-mode",
        choices=["atlas", "solid", "sampled", "sampled-local", "threshold-sampled"],
        default="atlas",
        help=(
            "atlas keeps glyph colors, solid uses --ink-color, sampled uses the gate image cell color, "
            "sampled-local searches nearby non-black source pixels, threshold-sampled samples source pixels "
            "inside the current gate threshold cell"
        ),
    )
    ascii_render_parser.add_argument("--ink-color", help="solid ink color as #RRGGBB")
    ascii_render_parser.add_argument("--ink-sample-radius", type=int, default=6)
    ascii_render_parser.add_argument("--ink-ignore-luminance", type=int, default=40)
    ascii_render_parser.add_argument(
        "--ink-palette-threshold",
        type=int,
        help="for sampled-local, keep nearby colors within this RGB distance of --gate-samples colors",
    )
    ascii_render_parser.add_argument(
        "--ink-palette-size",
        type=int,
        help="reduce sampled ink to this many deterministic colors before rendering",
    )
    ascii_render_parser.add_argument("--out", required=True)
    ascii_render_parser.add_argument("--scale", type=int, default=4)

    body_ascii_parser = subparsers.add_parser(
        "render-body-ascii-proof",
        help="render a shaded mannequin body through the ASCII glyph proof pipeline",
    )
    body_ascii_parser.add_argument("--pack", default=str(DEFAULT_PACK))
    body_ascii_parser.add_argument("--mannequin", required=True)
    body_ascii_parser.add_argument("--out", required=True)
    body_ascii_parser.add_argument("--glyphs")
    body_ascii_parser.add_argument("--atlas")
    body_ascii_parser.add_argument("--mapping")
    body_ascii_parser.add_argument("--shade-ramp")
    body_ascii_parser.add_argument("--grid-width", type=int, default=128)
    body_ascii_parser.add_argument("--grid-height", type=int, default=192)
    body_ascii_parser.add_argument("--palette-size", type=int, default=8)
    body_ascii_parser.add_argument("--palette-theme", choices=["source", "maroon"], default="source")
    body_ascii_parser.add_argument("--min-cell-coverage", type=float, default=0.05)
    body_ascii_parser.add_argument("--scale", type=int, default=2)

    layer_recipe_parser = subparsers.add_parser(
        "render-layer-recipe",
        help="render mask-first color layers from a JSON recipe",
    )
    layer_recipe_parser.add_argument("--recipe", required=True)
    layer_recipe_parser.add_argument("--out", required=True)

    threshold_layers_parser = subparsers.add_parser(
        "render-threshold-color-layers",
        help="render cumulative and delta threshold layers color-sampled from the source image",
    )
    threshold_layers_parser.add_argument("--pack", default=str(DEFAULT_PACK))
    threshold_layers_parser.add_argument("--image", required=True)
    threshold_layers_parser.add_argument("--out", required=True)
    threshold_layers_parser.add_argument("--thresholds", default=",".join(str(value) for value in DEFAULT_THRESHOLDS))
    threshold_layers_parser.add_argument("--width", type=int, default=128)
    threshold_layers_parser.add_argument("--height", type=int, default=128)
    threshold_layers_parser.add_argument("--fill-token", default="#")
    threshold_layers_parser.add_argument("--glyphs")
    threshold_layers_parser.add_argument("--atlas")
    threshold_layers_parser.add_argument("--mapping")
    threshold_layers_parser.add_argument("--foreground-mode", choices=sorted(FOREGROUND_MODES), default="auto")
    threshold_layers_parser.add_argument("--foreground-alpha-threshold", type=int, default=1)
    threshold_layers_parser.add_argument("--foreground-background-threshold", type=int, default=28)
    threshold_layers_parser.add_argument("--scale", type=int, default=2)

    color_family_parser = subparsers.add_parser(
        "render-color-family-layers",
        help="render generic color-family masks and source-colored glyph layers",
    )
    color_family_parser.add_argument("--pack", default=str(DEFAULT_PACK))
    color_family_parser.add_argument("--image", required=True)
    color_family_parser.add_argument("--out", required=True)
    color_family_parser.add_argument("--families", default="auto")
    color_family_parser.add_argument("--width", type=int, default=128)
    color_family_parser.add_argument("--height", type=int, default=128)
    color_family_parser.add_argument("--fill-token", default="#")
    color_family_parser.add_argument("--glyphs")
    color_family_parser.add_argument("--atlas")
    color_family_parser.add_argument("--mapping")
    color_family_parser.add_argument("--background-threshold", type=int, default=28)
    color_family_parser.add_argument("--min-cell-coverage", type=float, default=0.18)
    color_family_parser.add_argument("--foreground-mode", choices=sorted(FOREGROUND_MODES), default="auto")
    color_family_parser.add_argument("--foreground-alpha-threshold", type=int, default=1)
    color_family_parser.add_argument("--foreground-background-threshold", type=int)
    color_family_parser.add_argument("--scale", type=int, default=2)

    sequence_parser = subparsers.add_parser(
        "render-extraction-sequence",
        help="run foreground, threshold, and color-family extraction in one repeatable pass",
    )
    sequence_parser.add_argument("--pack", default=str(DEFAULT_PACK))
    sequence_parser.add_argument("--image", required=True)
    sequence_parser.add_argument("--out", required=True)
    sequence_parser.add_argument("--thresholds", default=",".join(str(value) for value in DEFAULT_THRESHOLDS))
    sequence_parser.add_argument("--families", default="auto")
    sequence_parser.add_argument("--width", type=int, default=128)
    sequence_parser.add_argument("--height", type=int, default=128)
    sequence_parser.add_argument("--fill-token", default="#")
    sequence_parser.add_argument("--glyphs")
    sequence_parser.add_argument("--atlas")
    sequence_parser.add_argument("--mapping")
    sequence_parser.add_argument("--background-threshold", type=int, default=28)
    sequence_parser.add_argument("--min-cell-coverage", type=float, default=0.18)
    sequence_parser.add_argument("--foreground-mode", choices=sorted(FOREGROUND_MODES), default="auto")
    sequence_parser.add_argument("--foreground-alpha-threshold", type=int, default=1)
    sequence_parser.add_argument("--foreground-background-threshold", type=int)
    sequence_parser.add_argument("--scale", type=int, default=2)

    reference_style_parser = subparsers.add_parser(
        "reference-style-recipe",
        help="convert a reference image into an editable glyph style recipe",
    )
    reference_style_parser.add_argument("--image", required=True)
    reference_style_parser.add_argument("--out", required=True)
    reference_style_parser.add_argument("--width", type=int, default=128)
    reference_style_parser.add_argument("--height", type=int, default=128)
    reference_style_parser.add_argument("--grid-size", type=int)
    reference_style_parser.add_argument("--families", default="auto")
    reference_style_parser.add_argument("--palette-size", type=int, default=3)
    reference_style_parser.add_argument("--outline-threshold", type=int, default=48)
    reference_style_parser.add_argument("--background-threshold", type=int, default=28)
    reference_style_parser.add_argument("--foreground-mode", choices=sorted(FOREGROUND_MODES), default="auto")
    reference_style_parser.add_argument("--foreground-alpha-threshold", type=int, default=1)
    reference_style_parser.add_argument("--foreground-background-threshold", type=int)
    reference_style_parser.add_argument("--fill-token", default="#")
    reference_style_parser.add_argument("--min-layer-cells", type=int, default=1)

    reference_render_parser = subparsers.add_parser(
        "render-reference-style",
        help="render a reference style recipe into glyph layers and a final PNG",
    )
    reference_render_parser.add_argument("--recipe", required=True)
    reference_render_parser.add_argument("--out", required=True)
    reference_render_parser.add_argument("--pack", default=str(DEFAULT_PACK))
    reference_render_parser.add_argument("--glyphs")
    reference_render_parser.add_argument("--atlas")
    reference_render_parser.add_argument("--mapping")
    reference_render_parser.add_argument("--scale", type=int, default=2)

    sprite_parts_parser = subparsers.add_parser(
        "classify-sprite-parts",
        help="classify generic humanoid sprite part layers from color and geometry evidence",
    )
    sprite_parts_parser.add_argument("--image", required=True)
    sprite_parts_parser.add_argument("--out", required=True)
    sprite_parts_parser.add_argument("--width", type=int, default=128)
    sprite_parts_parser.add_argument("--height", type=int, default=128)
    sprite_parts_parser.add_argument("--grid-size", type=int)
    sprite_parts_parser.add_argument("--foreground-mode", choices=sorted(FOREGROUND_MODES), default="auto")
    sprite_parts_parser.add_argument("--foreground-alpha-threshold", type=int, default=1)
    sprite_parts_parser.add_argument("--foreground-background-threshold", type=int, default=28)
    sprite_parts_parser.add_argument("--background-threshold", type=int, default=28)
    sprite_parts_parser.add_argument("--min-cell-coverage", type=float, default=0.14)
    sprite_parts_parser.add_argument("--scale", type=int, default=2)

    humanoid_regions_parser = subparsers.add_parser(
        "classify-humanoid-regions",
        help="extract humanoid body-object lanes from a region-color mannequin image",
    )
    humanoid_regions_parser.add_argument("--image", required=True)
    humanoid_regions_parser.add_argument("--out", required=True)
    humanoid_regions_parser.add_argument("--foreground-mode", choices=sorted(FOREGROUND_MODES), default="auto")
    humanoid_regions_parser.add_argument("--foreground-alpha-threshold", type=int, default=1)
    humanoid_regions_parser.add_argument("--foreground-background-threshold", type=int, default=22)
    humanoid_regions_parser.add_argument("--background-threshold", type=int, default=22)
    humanoid_regions_parser.add_argument("--scale", type=int, default=2)

    mannequin_parser = subparsers.add_parser(
        "build-mannequin",
        help="build a reusable mannequin recipe from humanoid region lanes",
    )
    mannequin_parser.add_argument("--regions", required=True)
    mannequin_parser.add_argument("--out", required=True)
    mannequin_parser.add_argument("--pose", default="reference_pose")

    mannequin_proof_parser = subparsers.add_parser(
        "render-mannequin-proof",
        help="render visual proof images from a mannequin recipe",
    )
    mannequin_proof_parser.add_argument("--mannequin", required=True)
    mannequin_proof_parser.add_argument("--out", required=True)
    mannequin_proof_parser.add_argument("--scale", type=int, default=2)

    skeleton_fit_parser = subparsers.add_parser(
        "fit-skeleton",
        help="measure anatomical skeleton joints against mannequin body-part masks",
    )
    skeleton_fit_parser.add_argument("--mannequin", required=True)
    skeleton_fit_parser.add_argument("--out", required=True)
    skeleton_fit_parser.add_argument("--scale", type=int, default=1)

    attachments_parser = subparsers.add_parser(
        "build-attachments",
        help="build attachment silhouettes from generic sprite part lanes",
    )
    attachments_parser.add_argument("--parts", required=True)
    attachments_parser.add_argument("--out", required=True)
    attachments_parser.add_argument("--mannequin")

    promoted_atlas_parser = subparsers.add_parser("build-promoted-atlas", help="build an atlas for promoted glyphs")
    promoted_atlas_parser.add_argument("--pack", default=str(DEFAULT_PACK))
    promoted_atlas_parser.add_argument("--glyphs", required=True)
    promoted_atlas_parser.add_argument("--out", required=True)

    promoted_sheet_parser = subparsers.add_parser(
        "promoted-contact-sheet",
        help="generate a contact sheet for promoted glyphs only",
    )
    promoted_sheet_parser.add_argument("--glyphs", required=True)
    promoted_sheet_parser.add_argument("--atlas", required=True)
    promoted_sheet_parser.add_argument("--out", required=True)

    compare_parser = subparsers.add_parser(
        "compare-ascii-fallbacks",
        help="compare ASCII bridge fallback warnings before and after promotion",
    )
    compare_parser.add_argument("--before", required=True)
    compare_parser.add_argument("--after", required=True)
    compare_parser.add_argument("--out", required=True)
    compare_parser.add_argument("--mapping")
    compare_parser.add_argument("--accepted")
    compare_parser.add_argument("--limit", type=int)
    compare_parser.add_argument("--base-glyphs")

    suggest_parser = subparsers.add_parser(
        "suggest-ascii-promotions",
        help="write a promotion request from ASCII bridge fallback warnings",
    )
    suggest_parser.add_argument("--manifest", required=True)
    suggest_parser.add_argument("--mapping", required=True)
    suggest_parser.add_argument("--accepted", required=True)
    suggest_parser.add_argument("--out", required=True)
    suggest_parser.add_argument("--limit", type=int)
    suggest_parser.add_argument("--base-glyphs")

    promote_parser = subparsers.add_parser("promote-candidates", help="promote reviewed candidates")
    promote_parser.add_argument("--pack", default=str(DEFAULT_PACK))
    promote_parser.add_argument("--request", required=True)
    promote_parser.add_argument("--accepted")
    promote_parser.add_argument("--base-glyphs")
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

    if args.command == "analyze-linework-image":
        analyze_linework_image(
            args.image,
            pack,
            args.out,
            grid_size=args.grid_size,
            glyphs_path=args.glyphs,
            atlas_path=args.atlas,
        )
        return

    if args.command == "layer-breakdown":
        write_layer_breakdown(
            args.image,
            pack,
            args.out,
            motion_out_dir=args.motion_out,
            grid_size=args.grid_size,
        )
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

    if args.command == "linework-coverage":
        write_linework_motion_coverage(args.glyphs, args.out)
        return

    if args.command == "generate-mannequin-template":
        generate_mannequin_template(args.out, width=args.width, height=args.height, scale=args.scale, view=args.view)
        return

    if args.command == "generate-brushes":
        write_brush_review(pack)
        return

    if args.command == "eyedropper-sample":
        write_eyedropper_json(
            args.image,
            args.out,
            points=[parse_point(point) for point in args.point],
            grid_size=parse_grid_size(args.grid_size) if args.grid_size else None,
            base_json_path=args.base_json,
            json_key=args.json_key,
        )
        return

    if args.command == "import-ascii-grid":
        import_ascii_grid(pack, args.ascii, args.mapping, args.out, glyphs_path=args.glyphs, atlas_path=args.atlas)
        return

    if args.command == "render-ascii-glyphs":
        render_ascii_glyphs(
            args.ascii,
            args.glyphs,
            args.atlas,
            args.out,
            mapping_path=args.mapping,
            gate_image_path=args.gate_image,
            gate_mode=args.gate_mode,
            gate_threshold=args.gate_threshold,
            gate_dilate=args.gate_dilate,
            gate_mask_output_path=args.gate_mask_out,
            gate_samples_path=args.gate_samples,
            gate_samples_key=args.gate_sample_key,
            gate_include_boxes=[parse_box(box) for box in args.gate_include_box],
            gate_fill_token=args.gate_fill_token,
            ink_mode=args.ink_mode,
            ink_color=args.ink_color,
            ink_sample_radius=args.ink_sample_radius,
            ink_ignore_luminance=args.ink_ignore_luminance,
            ink_palette_threshold=args.ink_palette_threshold,
            ink_palette_size=args.ink_palette_size,
            scale=args.scale,
        )
        return

    if args.command == "render-body-ascii-proof":
        glyphs_path = Path(args.glyphs) if args.glyphs else _preferred_pack_file(pack, "glyphs.promoted.json", "glyphs.json")
        atlas_path = Path(args.atlas) if args.atlas else _preferred_pack_file(pack, "atlas.promoted.png", "atlas.png")
        mapping_path = Path(args.mapping) if args.mapping else _optional_pack_file(pack, "ascii_brush_mapping.json")
        shade_ramp_path = Path(args.shade_ramp) if args.shade_ramp else _optional_pack_file(pack, "ascii_shade_palette.txt")
        render_body_ascii_proof(
            args.mannequin,
            args.out,
            glyphs_path=glyphs_path,
            atlas_path=atlas_path,
            mapping_path=mapping_path,
            shade_ramp_path=shade_ramp_path,
            grid_width=args.grid_width,
            grid_height=args.grid_height,
            palette_size=args.palette_size,
            palette_theme=args.palette_theme,
            min_cell_coverage=args.min_cell_coverage,
            scale=args.scale,
        )
        return

    if args.command == "render-layer-recipe":
        render_layer_recipe(args.recipe, args.out)
        return

    if args.command == "render-threshold-color-layers":
        glyphs_path = Path(args.glyphs) if args.glyphs else _preferred_pack_file(pack, "glyphs.promoted.json", "glyphs.json")
        atlas_path = Path(args.atlas) if args.atlas else _preferred_pack_file(pack, "atlas.promoted.png", "atlas.png")
        mapping_path = Path(args.mapping) if args.mapping else _optional_pack_file(pack, "ascii_brush_mapping.json")
        render_threshold_color_layers(
            args.image,
            glyphs_path,
            atlas_path,
            args.out,
            thresholds=parse_thresholds(args.thresholds),
            grid_width=args.width,
            grid_height=args.height,
            fill_token=args.fill_token,
            mapping_path=mapping_path,
            foreground_mode=args.foreground_mode,
            foreground_alpha_threshold=args.foreground_alpha_threshold,
            foreground_background_threshold=args.foreground_background_threshold,
            scale=args.scale,
        )
        return

    if args.command == "render-color-family-layers":
        glyphs_path = Path(args.glyphs) if args.glyphs else _preferred_pack_file(pack, "glyphs.promoted.json", "glyphs.json")
        atlas_path = Path(args.atlas) if args.atlas else _preferred_pack_file(pack, "atlas.promoted.png", "atlas.png")
        mapping_path = Path(args.mapping) if args.mapping else _optional_pack_file(pack, "ascii_brush_mapping.json")
        render_color_family_layers(
            args.image,
            glyphs_path,
            atlas_path,
            args.out,
            families=args.families,
            grid_width=args.width,
            grid_height=args.height,
            fill_token=args.fill_token,
            mapping_path=mapping_path,
            background_threshold=args.background_threshold,
            min_cell_coverage=args.min_cell_coverage,
            foreground_mode=args.foreground_mode,
            foreground_alpha_threshold=args.foreground_alpha_threshold,
            foreground_background_threshold=args.foreground_background_threshold,
            scale=args.scale,
        )
        return

    if args.command == "render-extraction-sequence":
        render_extraction_sequence(
            args.image,
            pack,
            args.out,
            thresholds=args.thresholds,
            families=args.families,
            grid_width=args.width,
            grid_height=args.height,
            fill_token=args.fill_token,
            glyphs_path=args.glyphs,
            atlas_path=args.atlas,
            mapping_path=args.mapping,
            background_threshold=args.background_threshold,
            min_cell_coverage=args.min_cell_coverage,
            foreground_mode=args.foreground_mode,
            foreground_alpha_threshold=args.foreground_alpha_threshold,
            foreground_background_threshold=args.foreground_background_threshold,
            scale=args.scale,
        )
        return

    if args.command == "reference-style-recipe":
        grid_width = args.grid_size if args.grid_size else args.width
        grid_height = args.grid_size if args.grid_size else args.height
        build_reference_style_recipe(
            args.image,
            args.out,
            grid_width=grid_width,
            grid_height=grid_height,
            families=args.families,
            palette_size=args.palette_size,
            outline_threshold=args.outline_threshold,
            background_threshold=args.background_threshold,
            foreground_mode=args.foreground_mode,
            foreground_alpha_threshold=args.foreground_alpha_threshold,
            foreground_background_threshold=args.foreground_background_threshold,
            fill_token=args.fill_token,
            min_layer_cells=args.min_layer_cells,
        )
        return

    if args.command == "render-reference-style":
        glyphs_path = Path(args.glyphs) if args.glyphs else _preferred_pack_file(pack, "glyphs.promoted.json", "glyphs.json")
        atlas_path = Path(args.atlas) if args.atlas else _preferred_pack_file(pack, "atlas.promoted.png", "atlas.png")
        mapping_path = Path(args.mapping) if args.mapping else _optional_pack_file(pack, "ascii_brush_mapping.json")
        render_reference_style(
            args.recipe,
            args.out,
            glyphs_path,
            atlas_path,
            mapping_path=mapping_path,
            scale=args.scale,
        )
        return

    if args.command == "classify-sprite-parts":
        grid_width = args.grid_size if args.grid_size else args.width
        grid_height = args.grid_size if args.grid_size else args.height
        classify_sprite_parts(
            args.image,
            args.out,
            grid_width=grid_width,
            grid_height=grid_height,
            foreground_mode=args.foreground_mode,
            foreground_alpha_threshold=args.foreground_alpha_threshold,
            foreground_background_threshold=args.foreground_background_threshold,
            background_threshold=args.background_threshold,
            min_cell_coverage=args.min_cell_coverage,
            scale=args.scale,
        )
        return

    if args.command == "classify-humanoid-regions":
        classify_humanoid_regions(
            args.image,
            args.out,
            foreground_mode=args.foreground_mode,
            foreground_alpha_threshold=args.foreground_alpha_threshold,
            foreground_background_threshold=args.foreground_background_threshold,
            background_threshold=args.background_threshold,
            scale=args.scale,
        )
        return

    if args.command == "build-mannequin":
        build_mannequin_recipe(args.regions, args.out, pose=args.pose)
        return

    if args.command == "render-mannequin-proof":
        render_mannequin_proof(args.mannequin, args.out, scale=args.scale)
        return

    if args.command == "fit-skeleton":
        fit_skeleton(args.mannequin, args.out, scale=args.scale)
        return

    if args.command == "build-attachments":
        build_attachment_recipe(args.parts, args.out, mannequin_path=args.mannequin)
        return

    if args.command == "build-promoted-atlas":
        build_promoted_atlas(pack / "atlas.png", args.glyphs, args.out)
        return

    if args.command == "promoted-contact-sheet":
        generate_promoted_contact_sheet(args.glyphs, args.atlas, args.out)
        return

    if args.command == "compare-ascii-fallbacks":
        compare_ascii_fallbacks(
            args.before,
            args.after,
            args.out,
            mapping_path=args.mapping,
            accepted_path=args.accepted,
            limit=args.limit,
            base_glyphs_path=args.base_glyphs,
        )
        return

    if args.command == "suggest-ascii-promotions":
        write_ascii_promotion_request(
            args.manifest,
            args.mapping,
            args.accepted,
            args.out,
            limit=args.limit,
            base_glyphs_path=args.base_glyphs,
        )
        return

    if args.command == "promote-candidates":
        promote_candidates(
            pack,
            args.request,
            apply=args.apply,
            accepted_path=args.accepted,
            base_glyphs_path=args.base_glyphs,
        )


def _load_json(path: str) -> dict:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _preferred_pack_file(pack: Path, preferred_name: str, fallback_name: str) -> Path:
    preferred = pack / preferred_name
    return preferred if preferred.exists() else pack / fallback_name


def _optional_pack_file(pack: Path, name: str) -> Path | None:
    path = pack / name
    return path if path.exists() else None


def parse_box(value: str) -> tuple[int, int, int, int]:
    parts = value.split(",")
    if len(parts) != 4:
        raise ValueError(f"gate include box must be x0,y0,x1,y1, got {value!r}")
    try:
        x0, y0, x1, y1 = (int(part) for part in parts)
    except ValueError as exc:
        raise ValueError(f"gate include box values must be integers, got {value!r}") from exc
    if x0 < 0 or y0 < 0 or x1 <= x0 or y1 <= y0:
        raise ValueError(f"gate include box must have positive size, got {value!r}")
    return x0, y0, x1, y1


if __name__ == "__main__":
    main()
