import unittest

from glyph_lab.linework_primitives import (
    default_linework_specs,
    hatch_pattern,
    linework_corner,
    linework_line,
    linework_metadata,
    linework_stamp,
    motion_shape,
)
from glyph_lab.measure import measure_stamp
from glyph_lab.transforms import stamp_to_bitmask


class LineworkPrimitiveTests(unittest.TestCase):
    def test_horizontal_top_line_sets_top_row(self):
        stamp = linework_line("horizontal", offset="top")

        self.assertEqual(stamp_to_bitmask(stamp), 0b0000000000001111)

    def test_vertical_right_line_sets_right_column(self):
        stamp = linework_line("vertical", offset="right")

        self.assertEqual(stamp_to_bitmask(stamp), (1 << 3) | (1 << 7) | (1 << 11) | (1 << 15))

    def test_soft_corner_has_lower_density_than_sharp_corner(self):
        sharp = measure_stamp(linework_corner("top_left", radius="sharp"))["density"]
        soft = measure_stamp(linework_corner("top_left", radius="soft"))["density"]

        self.assertLess(soft, sharp)

    def test_cross_hatch_has_more_density_than_light_diagonal_hatch(self):
        cross = measure_stamp(hatch_pattern("cross", density="medium"))["density"]
        diagonal = measure_stamp(hatch_pattern("diagonal_rise", density="light"))["density"]

        self.assertGreater(cross, diagonal)

    def test_linework_metadata_records_angle_and_connector_sides(self):
        metadata = linework_metadata(
            {
                "kind": "line",
                "params": {"direction": "vertical", "offset": "left", "thickness": 1},
            }
        )

        self.assertEqual(metadata["angle_degrees"], 90.0)
        self.assertEqual(metadata["connector_sides"], ["top", "bottom", "left"])
        self.assertEqual(metadata["linework_package"], "linework.stroke")
        self.assertEqual(metadata["stroke_topology"], "pass_through_segment")
        self.assertEqual(
            metadata["stroke_ports"],
            [
                {"side": "top", "lane": "left", "role": "entry"},
                {"side": "bottom", "lane": "left", "role": "exit"},
            ],
        )
        self.assertEqual(metadata["continuity"], "continuous")

    def test_broken_linework_metadata_records_implied_continuity(self):
        metadata = linework_metadata(
            {
                "kind": "line",
                "params": {"direction": "horizontal", "offset": "middle", "broken": True},
            }
        )

        self.assertEqual(metadata["linework_package"], "linework.break")
        self.assertEqual(metadata["break_rhythm"], "middle_dropout")
        self.assertEqual(metadata["continuity"], "implied_through_gap")
        self.assertEqual(metadata["visible_fragments"], 2)
        self.assertGreater(metadata["dropout_ratio"], 0.0)

    def test_hatch_metadata_records_pattern_fields(self):
        metadata = linework_metadata(
            {
                "kind": "hatch",
                "params": {"kind": "diagonal_rise", "density": "dense"},
            }
        )

        self.assertEqual(metadata["linework_package"], "linework.pattern")
        self.assertEqual(metadata["repeat_angle_degrees"], 45.0)
        self.assertEqual(metadata["density_class"], "dense")
        self.assertEqual(metadata["stroke_style"], "clean")

    def test_cap_metadata_records_terminal_port(self):
        metadata = linework_metadata(
            {
                "kind": "cap",
                "params": {"direction": "horizontal", "side": "left"},
            }
        )

        self.assertEqual(metadata["linework_package"], "linework.terminal")
        self.assertEqual(metadata["terminal_ports"], [{"side": "left", "lane": "center", "role": "terminal"}])

    def test_motion_shape_renders_explicit_motion_atom(self):
        stamp = motion_shape("pressed_horizontal_heavy")

        self.assertEqual(measure_stamp(stamp)["density"], 6 / 16)

    def test_motion_metadata_records_package_motion_profile(self):
        metadata = linework_metadata(
            {
                "kind": "motion",
                "params": {"shape": "rounded_turn_top_left"},
            }
        )

        self.assertEqual(metadata["linework_package"], "linework.curve")
        self.assertEqual(metadata["motion_profile"], "rounded_turn")
        self.assertEqual(metadata["stroke_topology"], "soft_corner")
        self.assertEqual(metadata["curvature"], "quarter_turn")

    def test_default_specs_include_generic_motion_profiles(self):
        motion_specs = [spec for spec in default_linework_specs() if spec["kind"] == "motion"]
        profiles = {
            linework_metadata({"kind": "motion", "params": spec["params"]})["motion_profile"]
            for spec in motion_specs
        }

        self.assertIn("pressed_pull", profiles)
        self.assertIn("angled_pull", profiles)
        self.assertIn("direction_change", profiles)
        self.assertIn("rounded_turn", profiles)
        self.assertIn("press_and_stop", profiles)
        self.assertIn("repeated_motion", profiles)

    def test_motion_spec_uses_detail_layer_not_object_specific_edge_role(self):
        spec = next(spec for spec in default_linework_specs() if spec["name"] == "join_corner_stressed")
        stamp = linework_stamp(spec)

        self.assertEqual(spec["role"], "detail")
        self.assertEqual(spec["family"], "motion")
        self.assertGreater(measure_stamp(stamp)["density"], 0)


if __name__ == "__main__":
    unittest.main()
