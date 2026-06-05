from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import unittest

from PIL import Image

from glyph_lab.atlas import generate_pack
from glyph_lab.linework_candidates import write_linework_review
from glyph_lab.promoted_atlas import build_promoted_atlas
from glyph_lab.promoted_contact_sheet import generate_promoted_contact_sheet
from glyph_lab.promotion import promote_candidates


class PromotedContactSheetTests(unittest.TestCase):
    def test_promoted_contact_sheet_groups_promoted_glyphs(self):
        with promoted_pack() as pack:
            atlas = pack / "atlas.promoted.png"
            build_promoted_atlas(pack / "atlas.png", pack / "glyphs.promoted.json", atlas)
            sheet = pack / "promoted_contact_sheet.png"

            result = generate_promoted_contact_sheet(pack / "glyphs.promoted.json", atlas, sheet)

            self.assertTrue(sheet.exists())
            self.assertEqual(result["promoted_count"], 2)
            self.assertEqual(result["groups"]["linework"], 2)
            with Image.open(sheet) as image:
                self.assertGreater(image.width, 0)
                self.assertGreater(image.height, 0)

    def test_cli_promoted_contact_sheet_writes_png(self):
        with promoted_pack() as pack:
            atlas = pack / "atlas.promoted.png"
            build_promoted_atlas(pack / "atlas.png", pack / "glyphs.promoted.json", atlas)
            sheet = pack / "promoted_contact_sheet_cli.png"

            subprocess.run(
                [
                    ".venv/bin/python",
                    "-m",
                    "glyph_lab.cli",
                    "promoted-contact-sheet",
                    "--glyphs",
                    str(pack / "glyphs.promoted.json"),
                    "--atlas",
                    str(atlas),
                    "--out",
                    str(sheet),
                ],
                check=True,
                cwd="/Users/kogaryu/font",
            )

            self.assertTrue(sheet.exists())


def promoted_pack():
    temp = TemporaryDirectory()
    pack = Path(temp.name) / "pack"
    generate_pack(pack)
    write_linework_review(pack)
    accepted = json.loads((pack / "linework_accepted_candidates.json").read_text(encoding="utf-8"))[
        "accepted_candidates"
    ]
    items = []
    for token, suffix in (("H", "cap_horizontal_right_3029"), ("F", "vertical_broken_3009")):
        candidate = next(candidate for candidate in accepted if candidate["id"].endswith(suffix))
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
