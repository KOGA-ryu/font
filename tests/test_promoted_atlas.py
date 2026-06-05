from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from PIL import Image

from glyph_lab.ascii_bridge import ascii_grid_to_layered, import_ascii_grid
from glyph_lab.atlas import generate_pack
from glyph_lab.linework_candidates import write_linework_review
from glyph_lab.promoted_atlas import build_promoted_atlas
from glyph_lab.promotion import promote_candidates


class PromotedAtlasTests(unittest.TestCase):
    def test_build_promoted_atlas_renders_promoted_bitmask_stamps(self):
        with promoted_linework_pack() as pack:
            atlas_path = pack / "atlas.promoted.png"

            result = build_promoted_atlas(pack / "atlas.png", pack / "glyphs.promoted.json", atlas_path)

            self.assertTrue(atlas_path.exists())
            self.assertGreaterEqual(result["generated_count"], 1)
            with Image.open(atlas_path) as image, Image.open(pack / "atlas.png") as base:
                self.assertGreater(image.height, base.height)

    def test_promoted_bridge_char_resolves_without_fallback(self):
        with promoted_linework_pack() as pack:
            mapping = json.loads((pack / "ascii_glyph_mapping.json").read_text(encoding="utf-8"))
            active_tokens = {record["token"] for record in json.loads((pack / "glyphs.promoted.json").read_text())["glyphs"]}

            layered = ascii_grid_to_layered("H", mapping, active_tokens)

            edge = next(layer for layer in layered["layers"] if layer["name"] == "edge")
            self.assertEqual(edge["grid"], ["H"])
            self.assertEqual(layered["metadata"]["warnings"], [])

    def test_import_ascii_grid_with_promoted_glyphs_and_atlas_removes_fallback(self):
        with promoted_linework_pack() as pack:
            atlas_path = pack / "atlas.promoted.png"
            build_promoted_atlas(pack / "atlas.png", pack / "glyphs.promoted.json", atlas_path)
            ascii_path = pack / "ascii.txt"
            ascii_path.write_text("HF\n", encoding="utf-8")
            out = pack / "out_promoted"

            result = import_ascii_grid(
                pack,
                ascii_path,
                pack / "ascii_glyph_mapping.json",
                out,
                glyphs_path=pack / "glyphs.promoted.json",
                atlas_path=atlas_path,
            )

            self.assertTrue((out / "proof_128.png").exists())
            warnings = result["manifest"]["ascii_bridge"]["warnings"]
            self.assertEqual([warning for warning in warnings if warning["type"] == "bridge-fallback"], [])

    def test_cli_build_promoted_atlas_writes_file(self):
        with promoted_linework_pack() as pack:
            atlas_path = pack / "atlas.promoted.png"

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "build-promoted-atlas",
                    "--pack",
                    str(pack),
                    "--glyphs",
                    str(pack / "glyphs.promoted.json"),
                    "--out",
                    str(atlas_path),
                ],
                check=True,
                cwd="/Users/kogaryu/font",
            )

            self.assertTrue(atlas_path.exists())

    def test_cli_import_ascii_grid_uses_promoted_glyphs_and_atlas(self):
        with promoted_linework_pack() as pack:
            atlas_path = pack / "atlas.promoted.png"
            build_promoted_atlas(pack / "atlas.png", pack / "glyphs.promoted.json", atlas_path)
            ascii_path = pack / "ascii.txt"
            ascii_path.write_text("HF\n", encoding="utf-8")
            out = pack / "out_promoted_cli"

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "import-ascii-grid",
                    "--pack",
                    str(pack),
                    "--glyphs",
                    str(pack / "glyphs.promoted.json"),
                    "--atlas",
                    str(atlas_path),
                    "--ascii",
                    str(ascii_path),
                    "--mapping",
                    str(pack / "ascii_glyph_mapping.json"),
                    "--out",
                    str(out),
                ],
                check=True,
                cwd="/Users/kogaryu/font",
            )

            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["ascii_bridge"]["warnings"], [])


def promoted_linework_pack():
    temp = TemporaryDirectory()
    pack = Path(temp.name) / "pack"
    generate_pack(pack)
    write_linework_review(pack)
    accepted = json.loads((pack / "linework_accepted_candidates.json").read_text(encoding="utf-8"))[
        "accepted_candidates"
    ]
    ids = {candidate["id"]: candidate for candidate in accepted}
    items = []
    for token, suffix in (("H", "cap_horizontal_right_3029"), ("F", "vertical_broken_3009")):
        candidate = next(candidate for candidate in ids.values() if candidate["id"].endswith(suffix))
        items.append({"candidate_id": candidate["id"], "token": token})
    request = pack / "promote.json"
    request.write_text(json.dumps({"promote": items}, indent=2) + "\n", encoding="utf-8")
    promote_candidates(pack, request, accepted_path=pack / "linework_accepted_candidates.json")

    class Context:
        def __enter__(self):
            return pack

        def __exit__(self, *_args):
            temp.cleanup()

    return Context()


if __name__ == "__main__":
    unittest.main()
