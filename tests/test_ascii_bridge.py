from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from glyph_lab.ascii_bridge import ascii_grid_to_layered, import_ascii_grid, resolve_ascii_char
from glyph_lab.atlas import generate_pack
from glyph_lab.linework_candidates import write_linework_review


class AsciiBridgeTests(unittest.TestCase):
    def test_active_line_chars_map_to_edge_layer(self):
        layered = ascii_grid_to_layered("-|\n/\\", bridge_mapping(), {"-", "|", "/", "\\"})

        edge = next(layer for layer in layered["layers"] if layer["name"] == "edge")

        self.assertEqual(edge["grid"], ["-|", "/\\"])

    def test_unicode_edge_aliases_map_to_active_tokens(self):
        resolved_vertical = resolve_ascii_char("│", bridge_mapping(), {"-", "|"})
        resolved_horizontal = resolve_ascii_char("─", bridge_mapping(), {"-", "|"})

        self.assertEqual(resolved_vertical["token"], "|")
        self.assertEqual(resolved_horizontal["token"], "-")

    def test_bridge_only_key_falls_back_to_active_token(self):
        layered = ascii_grid_to_layered("A", bridge_mapping(), {"-"})

        edge = next(layer for layer in layered["layers"] if layer["name"] == "edge")

        self.assertEqual(edge["grid"], ["-"])
        self.assertEqual(layered["metadata"]["warnings"][0]["type"], "bridge-fallback")

    def test_unknown_ascii_char_records_warning_and_is_skipped(self):
        layered = ascii_grid_to_layered("?", bridge_mapping(), {"-"})

        self.assertEqual(layered["layers"], [])
        self.assertEqual(layered["metadata"]["warnings"][0]["type"], "unmapped-ascii-char")

    def test_import_ascii_grid_writes_layered_grid_and_proof(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            write_linework_review(pack)
            ascii_path = Path(tmp) / "linework.txt"
            ascii_path.write_text("-│\nA+\n", encoding="utf-8")
            out = Path(tmp) / "out_ascii_bridge"

            import_ascii_grid(pack, ascii_path, pack / "ascii_glyph_mapping.json", out)

            self.assertTrue((out / "generated_layered_grid.json").exists())
            self.assertTrue((out / "proof_128.png").exists())
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertIn("ascii_bridge", manifest)

    def test_cli_import_ascii_grid_writes_outputs(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            generate_pack(pack)
            write_linework_review(pack)
            ascii_path = Path(tmp) / "linework.txt"
            ascii_path.write_text("-|\n/+\n", encoding="utf-8")
            out = Path(tmp) / "out_ascii_bridge"

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "import-ascii-grid",
                    "--pack",
                    str(pack),
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

            self.assertTrue((out / "generated_layered_grid.json").exists())
            self.assertTrue((out / "manifest.json").exists())
            self.assertTrue((out / "proof_128.png").exists())


def bridge_mapping():
    return {
        "edge_aliases": {"─": "-", "│": "|"},
        "mapping": {
            "-": {"token": "-", "layer": "edge", "ascii_fallback": "-", "bridge_only": False},
            "|": {"token": "|", "layer": "edge", "ascii_fallback": "|", "bridge_only": False},
            "/": {"token": "/", "layer": "edge", "ascii_fallback": "/", "bridge_only": False},
            "\\": {"token": "\\", "layer": "edge", "ascii_fallback": "\\", "bridge_only": False},
            "+": {"token": "+", "layer": "edge", "ascii_fallback": "+", "bridge_only": False},
            "A": {"token": "", "layer": "edge", "ascii_fallback": "-", "bridge_only": True},
        },
    }


if __name__ == "__main__":
    unittest.main()
