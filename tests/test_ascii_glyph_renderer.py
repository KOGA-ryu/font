from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from PIL import Image

from glyph_lab.ascii_glyph_renderer import render_ascii_glyphs
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
                    "--out",
                    str(out),
                    "--scale",
                    "2",
                ],
                check=True,
                cwd="/Users/kogaryu/font",
            )

            self.assertTrue(out.exists())
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


if __name__ == "__main__":
    unittest.main()
