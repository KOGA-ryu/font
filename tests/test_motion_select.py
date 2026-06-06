import unittest

from glyph_lab.motion_select import select_motion_glyph


class MotionSelectTests(unittest.TestCase):
    def test_selects_exact_motion_profile_match(self):
        selected = select_motion_glyph(
            {
                "motion_profile": "angled_pull",
                "stroke_topology": "pass_through_segment",
                "linework_package": "linework.stroke",
                "angle_degrees": 45.0,
                "pressure_curve": "thin",
                "release_style": "clean_exit",
            },
            [
                {
                    "id": "horizontal",
                    "token": "-",
                    "index": 1,
                    "linework_package": "linework.stroke",
                    "stroke_topology": "pass_through_segment",
                    "motion_profile": "steady_pull",
                    "angle_degrees": 0.0,
                    "pressure_curve": "thin",
                    "release_style": "clean_exit",
                },
                {
                    "id": "diagonal",
                    "token": "/",
                    "index": 2,
                    "linework_package": "linework.stroke",
                    "stroke_topology": "pass_through_segment",
                    "motion_profile": "angled_pull",
                    "angle_degrees": 45.0,
                    "pressure_curve": "thin",
                    "release_style": "clean_exit",
                },
            ],
        )

        self.assertEqual(selected["token"], "/")
        self.assertEqual(selected["selection_reason"], "motion-match")

    def test_falls_back_when_no_motion_records_exist(self):
        selected = select_motion_glyph({"angle_degrees": 90.0}, [])

        self.assertEqual(selected["token"], "|")
        self.assertEqual(selected["selection_reason"], "fallback-no-linework-motion-records")


if __name__ == "__main__":
    unittest.main()
