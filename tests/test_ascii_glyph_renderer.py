from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from PIL import Image

from glyph_lab.ascii_glyph_renderer import image_gate_mask, render_ascii_glyphs
from glyph_lab.atlas import generate_pack, load_atlas_stamps
from glyph_lab.linework_candidates import write_linework_review
from glyph_lab.promoted_atlas import build_promoted_atlas
from glyph_lab.promotion import promote_candidates
from glyph_lab.schema import load_glyphs


class AsciiGlyphRendererTests(unittest.TestCase):
    def test_token_renders_exact_4x4_stamp(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            ascii_path = Path(tmp) / "grid.txt"
            out = Path(tmp) / "render.png"
            ascii_path.write_text("-\n", encoding="utf-8")

            render_ascii_glyphs(
                ascii_path,
                pack / "glyphs.json",
                pack / "atlas.png",
                out,
                scale=1,
                background=(0, 0, 0, 0),
            )

            stamps = load_atlas_stamps(pack / "atlas.png", load_glyphs(pack / "glyphs.json"))
            with Image.open(out) as rendered:
                self.assertEqual(rendered.convert("RGBA").tobytes(), stamps["-"].tobytes())

    def test_space_renders_blank_cell(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            ascii_path = Path(tmp) / "grid.txt"
            out = Path(tmp) / "render.png"
            ascii_path.write_text(" \n", encoding="utf-8")

            render_ascii_glyphs(ascii_path, pack / "glyphs.json", pack / "atlas.png", out, scale=1)

            with Image.open(out) as rendered:
                self.assertEqual(rendered.size, (4, 4))
                self.assertEqual(set(_pixels(rendered)), {(255, 255, 255, 255)})

    def test_unknown_token_fails_with_location(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            ascii_path = Path(tmp) / "grid.txt"
            ascii_path.write_text("-?\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Unknown glyph token '\\?' at row 1, column 2"):
                render_ascii_glyphs(ascii_path, pack / "glyphs.json", pack / "atlas.png", Path(tmp) / "render.png")

    def test_mapping_resolves_unicode_edge_aliases(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            ascii_path = Path(tmp) / "grid.txt"
            mapping_path = Path(tmp) / "mapping.json"
            out = Path(tmp) / "render.png"
            ascii_path.write_text("─│\n", encoding="utf-8")
            mapping_path.write_text(
                json.dumps(
                    {
                        "mapping": {
                            "-": {"token": "-", "layer": "edge", "ascii_fallback": "-"},
                            "|": {"token": "|", "layer": "edge", "ascii_fallback": "|"},
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = render_ascii_glyphs(
                ascii_path,
                pack / "glyphs.json",
                pack / "atlas.png",
                out,
                mapping_path=mapping_path,
                scale=1,
            )

            self.assertEqual(result["token_counts"], {"-": 1, "|": 1})
            self.assertEqual(result["fallback_counts"], {"─": 1, "│": 1})
            self.assertTrue(out.exists())

    def test_output_size_uses_grid_cell_size_and_scale(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            ascii_path = Path(tmp) / "grid.txt"
            out = Path(tmp) / "render.png"
            ascii_path.write_text("-|\n/+\n", encoding="utf-8")

            result = render_ascii_glyphs(ascii_path, pack / "glyphs.json", pack / "atlas.png", out, scale=3)

            self.assertEqual(result["output_width"], 24)
            self.assertEqual(result["output_height"], 24)
            with Image.open(out) as rendered:
                self.assertEqual(rendered.size, (24, 24))

    def test_border_difference_gate_blanks_background_cells(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            gate_image = Path(tmp) / "gate.png"
            ascii_path = Path(tmp) / "grid.txt"
            out = Path(tmp) / "render.png"
            _write_gate_fixture(gate_image)
            ascii_path.write_text("----\n----\n----\n----\n", encoding="utf-8")

            result = render_ascii_glyphs(
                ascii_path,
                pack / "glyphs.json",
                pack / "atlas.png",
                out,
                gate_image_path=gate_image,
                gate_threshold=30,
                gate_dilate=0,
                scale=1,
            )

            self.assertLess(result["token_counts"]["-"], 16)
            self.assertGreater(result["gate"]["gated_token_cells"], 0)
            self.assertEqual(result["gate"]["kept_cells"], 4)

    def test_gate_skips_unknown_tokens_outside_mask(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            gate_image = Path(tmp) / "gate.png"
            ascii_path = Path(tmp) / "grid.txt"
            out = Path(tmp) / "render.png"
            _write_gate_fixture(gate_image)
            ascii_path.write_text("????\n?--?\n?--?\n????\n", encoding="utf-8")

            result = render_ascii_glyphs(
                ascii_path,
                pack / "glyphs.json",
                pack / "atlas.png",
                out,
                gate_image_path=gate_image,
                gate_threshold=30,
                gate_dilate=0,
                scale=1,
            )

            self.assertEqual(result["token_counts"], {"-": 4})
            self.assertEqual(result["gate"]["gated_token_cells"], 12)

    def test_image_gate_mask_can_use_alpha(self):
        with TemporaryDirectory() as tmp:
            gate_image = Path(tmp) / "alpha.png"
            image = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
            pixels = image.load()
            pixels[1, 1] = (255, 255, 255, 255)
            image.save(gate_image)

            mask = image_gate_mask(gate_image, 4, 4, mode="alpha", threshold=1, dilate=0)

            self.assertTrue(mask[1][1])
            self.assertEqual(sum(1 for row in mask for value in row if value), 1)

    def test_image_gate_mask_can_use_black_mode(self):
        with TemporaryDirectory() as tmp:
            gate_image = Path(tmp) / "black.png"
            image = Image.new("RGB", (4, 4), (230, 230, 230))
            pixels = image.load()
            pixels[1, 1] = (5, 5, 5)
            pixels[2, 2] = (90, 90, 90)
            image.save(gate_image)

            mask = image_gate_mask(gate_image, 4, 4, mode="black", threshold=40, dilate=0)

            self.assertTrue(mask[1][1])
            self.assertFalse(mask[2][2])
            self.assertEqual(sum(1 for row in mask for value in row if value), 1)

    def test_image_gate_mask_can_use_sample_colors(self):
        with TemporaryDirectory() as tmp:
            gate_image = Path(tmp) / "colors.png"
            image = Image.new("RGB", (4, 4), (240, 240, 240))
            pixels = image.load()
            pixels[1, 1] = (30, 70, 150)
            pixels[2, 2] = (118, 66, 34)
            pixels[3, 3] = (80, 160, 80)
            image.save(gate_image)

            mask = image_gate_mask(
                gate_image,
                4,
                4,
                mode="sample-colors",
                threshold=12,
                dilate=0,
                sample_colors=[(31, 72, 148), (120, 64, 32)],
            )

            self.assertTrue(mask[1][1])
            self.assertTrue(mask[2][2])
            self.assertFalse(mask[3][3])
            self.assertEqual(sum(1 for row in mask for value in row if value), 2)

    def test_sample_colors_gate_requires_samples(self):
        with TemporaryDirectory() as tmp:
            gate_image = Path(tmp) / "colors.png"
            Image.new("RGB", (4, 4), (240, 240, 240)).save(gate_image)

            with self.assertRaisesRegex(ValueError, "requires at least one eyedropper sample color"):
                image_gate_mask(gate_image, 4, 4, mode="sample-colors", threshold=12, dilate=0)

    def test_image_gate_mask_can_use_include_boxes(self):
        with TemporaryDirectory() as tmp:
            gate_image = Path(tmp) / "colors.png"
            Image.new("RGB", (4, 4), (30, 70, 150)).save(gate_image)

            mask = image_gate_mask(
                gate_image,
                4,
                4,
                mode="sample-colors",
                threshold=1,
                dilate=0,
                sample_colors=[(30, 70, 150)],
                include_boxes=[(0, 0, 2, 4)],
            )

            self.assertTrue(all(row[0] and row[1] for row in mask))
            self.assertTrue(all(not row[2] and not row[3] for row in mask))
            self.assertEqual(sum(1 for row in mask for value in row if value), 8)

    def test_image_gate_mask_rejects_invalid_include_box(self):
        with TemporaryDirectory() as tmp:
            gate_image = Path(tmp) / "colors.png"
            Image.new("RGB", (4, 4), (30, 70, 150)).save(gate_image)

            with self.assertRaisesRegex(ValueError, "gate include box"):
                image_gate_mask(
                    gate_image,
                    4,
                    4,
                    mode="sample-colors",
                    threshold=1,
                    dilate=0,
                    sample_colors=[(30, 70, 150)],
                    include_boxes=[(2, 0, 2, 4)],
                )

    def test_render_sample_colors_gate_loads_eyedropper_json(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            ascii_path = Path(tmp) / "grid.txt"
            gate_image = Path(tmp) / "colors.png"
            samples_path = Path(tmp) / "samples.json"
            out = Path(tmp) / "render.png"
            ascii_path.write_text("----\n----\n----\n----\n", encoding="utf-8")
            image = Image.new("RGB", (4, 4), (240, 240, 240))
            image.putpixel((1, 1), (30, 70, 150))
            image.save(gate_image)
            samples_path.write_text(
                json.dumps(
                    {
                        "palette_samples": {
                            "source_image": str(gate_image),
                            "samples": [{"label": "blue", "rgba": [31, 72, 148, 255]}],
                        }
                    }
                ),
                encoding="utf-8",
            )

            result = render_ascii_glyphs(
                ascii_path,
                pack / "glyphs.json",
                pack / "atlas.png",
                out,
                gate_image_path=gate_image,
                gate_mode="sample-colors",
                gate_threshold=12,
                gate_dilate=0,
                gate_samples_path=samples_path,
                gate_samples_key="palette_samples",
                scale=1,
            )

            self.assertEqual(result["token_counts"]["-"], 1)
            self.assertEqual(result["gate"]["sample_count"], 1)
            self.assertEqual(result["gate"]["samples"], str(samples_path))

    def test_gate_fill_token_covers_all_kept_mask_cells(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            ascii_path = Path(tmp) / "grid.txt"
            gate_image = Path(tmp) / "gate.png"
            out = Path(tmp) / "render.png"
            _write_gate_fixture(gate_image)
            ascii_path.write_text("    \n    \n    \n    \n", encoding="utf-8")

            result = render_ascii_glyphs(
                ascii_path,
                pack / "glyphs.json",
                pack / "atlas.png",
                out,
                gate_image_path=gate_image,
                gate_threshold=30,
                gate_dilate=0,
                gate_fill_token="-",
                scale=1,
            )

            self.assertEqual(result["token_counts"], {"-": 4})
            self.assertEqual(result["fallback_counts"], {})
            self.assertEqual(result["gate"]["kept_cells"], 4)
            self.assertEqual(result["gate"]["filled_cells"], 4)
            self.assertEqual(result["gate"]["fill_token"], "-")

    def test_gate_fill_token_requires_gate_image(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            ascii_path = Path(tmp) / "grid.txt"
            ascii_path.write_text("    \n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "gate fill token requires --gate-image"):
                render_ascii_glyphs(
                    ascii_path,
                    pack / "glyphs.json",
                    pack / "atlas.png",
                    Path(tmp) / "render.png",
                    gate_fill_token="-",
                )

    def test_solid_ink_mode_tints_stamp(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            ascii_path = Path(tmp) / "grid.txt"
            out = Path(tmp) / "render.png"
            ascii_path.write_text("#\n", encoding="utf-8")

            result = render_ascii_glyphs(
                ascii_path,
                pack / "glyphs.json",
                pack / "atlas.png",
                out,
                ink_mode="solid",
                ink_color="#000000",
                scale=1,
            )

            self.assertEqual(result["ink"]["mode"], "solid")
            with Image.open(out) as rendered:
                self.assertEqual(set(_pixels(rendered)), {(0, 0, 0, 255)})

    def test_solid_ink_mode_requires_color(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            ascii_path = Path(tmp) / "grid.txt"
            ascii_path.write_text("#\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "solid ink mode requires --ink-color"):
                render_ascii_glyphs(
                    ascii_path,
                    pack / "glyphs.json",
                    pack / "atlas.png",
                    Path(tmp) / "render.png",
                    ink_mode="solid",
                )

    def test_sampled_ink_mode_uses_gate_image_cell_color(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            ascii_path = Path(tmp) / "grid.txt"
            gate_image = Path(tmp) / "colors.png"
            out = Path(tmp) / "render.png"
            ascii_path.write_text("##\n##\n", encoding="utf-8")
            image = Image.new("RGBA", (2, 2), (0, 0, 0, 255))
            image.putpixel((0, 0), (70, 45, 21, 255))
            image.putpixel((1, 0), (85, 61, 37, 255))
            image.putpixel((0, 1), (52, 31, 21, 255))
            image.putpixel((1, 1), (77, 53, 41, 255))
            image.save(gate_image)

            result = render_ascii_glyphs(
                ascii_path,
                pack / "glyphs.json",
                pack / "atlas.png",
                out,
                gate_image_path=gate_image,
                gate_mode="alpha",
                gate_threshold=1,
                gate_dilate=0,
                ink_mode="sampled",
                scale=1,
            )

            self.assertEqual(result["ink"]["mode"], "sampled")
            with Image.open(out) as rendered:
                self.assertEqual(rendered.getpixel((0, 0)), (70, 45, 21, 255))
                self.assertEqual(rendered.getpixel((4, 0)), (85, 61, 37, 255))
                self.assertEqual(rendered.getpixel((0, 4)), (52, 31, 21, 255))
                self.assertEqual(rendered.getpixel((4, 4)), (77, 53, 41, 255))

    def test_sampled_ink_can_reduce_to_small_palette(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            ascii_path = Path(tmp) / "grid.txt"
            gate_image = Path(tmp) / "colors.png"
            out = Path(tmp) / "render.png"
            ascii_path.write_text("##\n##\n", encoding="utf-8")
            image = Image.new("RGBA", (2, 2), (0, 0, 0, 255))
            image.putpixel((0, 0), (70, 45, 21, 255))
            image.putpixel((1, 0), (85, 61, 37, 255))
            image.putpixel((0, 1), (28, 72, 150, 255))
            image.putpixel((1, 1), (34, 80, 160, 255))
            image.save(gate_image)

            result = render_ascii_glyphs(
                ascii_path,
                pack / "glyphs.json",
                pack / "atlas.png",
                out,
                gate_image_path=gate_image,
                gate_mode="alpha",
                gate_threshold=1,
                gate_dilate=0,
                ink_mode="sampled",
                ink_palette_size=2,
                scale=1,
            )

            self.assertEqual(result["ink"]["reduced_palette_size"], 2)
            self.assertEqual(len(result["ink"]["reduced_palette"]), 2)
            with Image.open(out) as rendered:
                colors = {pixel[:3] for pixel in _pixels(rendered)}
                self.assertLessEqual(len(colors), 2)
                self.assertNotEqual(colors, {(70, 45, 21), (85, 61, 37), (28, 72, 150), (34, 80, 160)})

    def test_sampled_local_ink_ignores_black_and_uses_nearby_color(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            ascii_path = Path(tmp) / "grid.txt"
            gate_image = Path(tmp) / "local.png"
            out = Path(tmp) / "render.png"
            ascii_path.write_text("#\n", encoding="utf-8")
            image = Image.new("RGBA", (5, 5), (30, 70, 150, 255))
            image.putpixel((2, 2), (0, 0, 0, 255))
            image.save(gate_image)

            result = render_ascii_glyphs(
                ascii_path,
                pack / "glyphs.json",
                pack / "atlas.png",
                out,
                gate_image_path=gate_image,
                gate_mode="alpha",
                gate_threshold=1,
                gate_dilate=0,
                ink_mode="sampled-local",
                ink_sample_radius=2,
                ink_ignore_luminance=20,
                scale=1,
            )

            self.assertEqual(result["ink"]["mode"], "sampled-local")
            with Image.open(out) as rendered:
                self.assertEqual(set(_pixels(rendered)), {(30, 70, 150, 255)})

    def test_sampled_local_ink_can_filter_to_palette_colors(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            ascii_path = Path(tmp) / "grid.txt"
            gate_image = Path(tmp) / "local.png"
            samples_path = Path(tmp) / "samples.json"
            out = Path(tmp) / "render.png"
            ascii_path.write_text("#\n", encoding="utf-8")
            image = Image.new("RGBA", (5, 5), (20, 120, 40, 255))
            image.putpixel((2, 2), (0, 0, 0, 255))
            image.putpixel((2, 1), (30, 70, 150, 255))
            image.save(gate_image)
            samples_path.write_text(
                json.dumps(
                    {
                        "palette_samples": {
                            "source_image": str(gate_image),
                            "samples": [{"label": "blue", "rgba": [30, 70, 150, 255]}],
                        }
                    }
                ),
                encoding="utf-8",
            )

            render_ascii_glyphs(
                ascii_path,
                pack / "glyphs.json",
                pack / "atlas.png",
                out,
                gate_image_path=gate_image,
                gate_mode="alpha",
                gate_threshold=1,
                gate_dilate=0,
                gate_samples_path=samples_path,
                gate_samples_key="palette_samples",
                ink_mode="sampled-local",
                ink_sample_radius=2,
                ink_ignore_luminance=20,
                ink_palette_threshold=4,
                scale=1,
            )

            with Image.open(out) as rendered:
                self.assertEqual(set(_pixels(rendered)), {(30, 70, 150, 255)})

    def test_threshold_sampled_ink_uses_only_threshold_matching_source_pixels(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            ascii_path = Path(tmp) / "grid.txt"
            gate_image = Path(tmp) / "threshold_colors.png"
            out = Path(tmp) / "render.png"
            ascii_path.write_text("#\n", encoding="utf-8")
            image = Image.new("RGBA", (4, 4), (0, 220, 0, 255))
            for xy in (
                (0, 0),
                (1, 0),
                (2, 0),
                (3, 0),
                (0, 1),
                (1, 1),
                (2, 1),
                (3, 1),
                (0, 2),
                (1, 2),
                (2, 2),
                (3, 2),
            ):
                image.putpixel(xy, (24, 0, 0, 255))
            image.save(gate_image)

            result = render_ascii_glyphs(
                ascii_path,
                pack / "glyphs.json",
                pack / "atlas.png",
                out,
                gate_image_path=gate_image,
                gate_mode="black",
                gate_threshold=40,
                gate_dilate=0,
                gate_fill_token="#",
                ink_mode="threshold-sampled",
                scale=1,
            )

            self.assertEqual(result["ink"]["mode"], "threshold-sampled")
            self.assertEqual(result["ink"]["threshold_mode"], "black")
            with Image.open(out) as rendered:
                self.assertEqual(set(_pixels(rendered)), {(24, 0, 0, 255)})

    def test_promoted_token_renders_from_promoted_atlas(self):
        with promoted_linework_pack() as pack:
            ascii_path = pack / "grid.txt"
            atlas_path = pack / "atlas.promoted.png"
            out = pack / "render.png"
            ascii_path.write_text("H\n", encoding="utf-8")
            build_promoted_atlas(pack / "atlas.png", pack / "glyphs.promoted.json", atlas_path)

            render_ascii_glyphs(ascii_path, pack / "glyphs.promoted.json", atlas_path, out, scale=1)

            self.assertTrue(out.exists())
            with Image.open(out) as rendered:
                self.assertEqual(rendered.size, (4, 4))
                self.assertGreater(len(set(_pixels(rendered))), 1)

    def test_cli_render_ascii_glyphs_writes_png(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            ascii_path = Path(tmp) / "grid.txt"
            out = Path(tmp) / "render.png"
            ascii_path.write_text("-|\n", encoding="utf-8")

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "render-ascii-glyphs",
                    "--ascii",
                    str(ascii_path),
                    "--glyphs",
                    str(pack / "glyphs.json"),
                    "--atlas",
                    str(pack / "atlas.png"),
                    "--gate-image",
                    str(_write_gate_fixture(Path(tmp) / "gate.png")),
                    "--gate-mask-out",
                    str(Path(tmp) / "gate_mask.png"),
                    "--out",
                    str(out),
                    "--scale",
                    "2",
                ],
                check=True,
                cwd="/Users/kogaryu/font",
            )

            self.assertTrue(out.exists())
            self.assertTrue((Path(tmp) / "gate_mask.png").exists())
            with Image.open(out) as rendered:
                self.assertEqual(rendered.size, (16, 8))


def promoted_linework_pack():
    temp = TemporaryDirectory()
    pack = Path(temp.name) / "pack"
    generate_pack(pack)
    write_linework_review(pack)
    accepted = json.loads((pack / "linework_accepted_candidates.json").read_text(encoding="utf-8"))[
        "accepted_candidates"
    ]
    candidate = next(candidate for candidate in accepted if candidate["id"].endswith("cap_horizontal_right_3029"))
    request = pack / "promote.json"
    request.write_text(
        json.dumps({"promote": [{"candidate_id": candidate["id"], "token": "H"}]}, indent=2) + "\n",
        encoding="utf-8",
    )
    promote_candidates(pack, request, accepted_path=pack / "linework_accepted_candidates.json")

    class Context:
        def __enter__(self):
            return pack

        def __exit__(self, *_args):
            temp.cleanup()

    return Context()


def _pixels(image: Image.Image) -> list[tuple[int, int, int, int]]:
    rgba = image.convert("RGBA")
    data = rgba.tobytes()
    return [tuple(data[index : index + 4]) for index in range(0, len(data), 4)]


def _write_gate_fixture(path: Path) -> Path:
    image = Image.new("RGB", (4, 4), (20, 30, 40))
    pixels = image.load()
    for y in (1, 2):
        for x in (1, 2):
            pixels[x, y] = (220, 190, 80)
    image.save(path)
    return path


if __name__ == "__main__":
    unittest.main()
