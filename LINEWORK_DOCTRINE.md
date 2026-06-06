# Linework Doctrine

Linework is practiced motion made visible. It is the reusable grammar of drawn
marks.

It is not an object category. It is not a crack, stone edge, chip, fold, hair,
wood grain, shadow, or contour. Those are interpretations that can be built
from linework.

Linework describes what a stroke does inside a cell:

- where it enters
- where it exits
- where it terminates
- what angle it carries
- how much weight it has
- how it caps
- how it joins
- how it breaks
- how rough or clean the mark is
- how it should continue into neighboring cells
- what speed, pressure, dwell, stress, release, and rhythm the stroke implies

The same stroke atom can be used by many subjects. A jagged crack, cloth fold,
contour line, hatch mark, bark vein, or technical construction line may all use
the same underlying linework packages.

The goal is not perfect pixel copy. The goal is to capture the practiced motion
that could have made the mark.

## Separation

Keep these concepts separate:

- `linework`: stroke grammar
- `layer`: where a stroke is applied
- `evidence`: why a stroke is selected
- `object feature`: what the viewer may interpret after composition

Bad package names:

- `stone_slab_crack`
- `column_flute_line`
- `chipped_corner`

Good package names:

- `linework.stroke`
- `linework.terminal`
- `linework.join`
- `linework.curve`
- `linework.weight`
- `linework.break`
- `linework.texture`
- `linework.pattern`

## Package Definitions

### linework.stroke

Basic continuous stroke segments.

Required metadata:

- `stroke_ports`
- `angle_degrees`
- `weight_profile`
- `continuity`

Examples:

- horizontal pass-through
- vertical pass-through
- diagonal pass-through
- offset pass-through

### linework.terminal

How a stroke ends.

Required metadata:

- `stroke_ports`
- `terminal_ports`
- `cap_style`
- `weight_profile`

Examples:

- flat cap
- blunt cap
- tapered cap
- broken cap

### linework.join

How strokes meet, branch, or cross.

Required metadata:

- `stroke_ports`
- `join_style`
- `branch_count`
- `dominant_angle_degrees`

Examples:

- corner
- tee
- cross
- fork
- merge

### linework.curve

Small curve approximations.

Required metadata:

- `stroke_ports`
- `entry_tangent_degrees`
- `exit_tangent_degrees`
- `curvature`

Examples:

- soft corner
- hook
- arc fragment
- curve-to-straight transition

### linework.weight

Same topology, different pressure or ink load.

Required metadata:

- `thickness`
- `weight_profile`
- `coverage`

Examples:

- thin
- medium
- thick
- heavy middle
- heavy terminal
- taper

### linework.break

Interrupted stroke continuity.

Required metadata:

- `intended_continuity`
- `visible_fragments`
- `dropout_ratio`
- `stroke_ports`

Examples:

- dash
- broken pass-through
- scratch
- dotted segment

### linework.texture

Stroke surface quality while preserving topology.

Required metadata:

- `roughness`
- `dropout_ratio`
- `stroke_ports`
- `continuity`

Examples:

- clean ink
- dry brush
- charcoal
- scratchy ink

### linework.pattern

Repeated systems of strokes.

Required metadata:

- `repeat_angle_degrees`
- `spacing_class`
- `density_class`
- `stroke_style`

Examples:

- hatch
- crosshatch
- parallel strokes
- contour hatch
- stippled line

## Layer Assignment

Layers choose how to use linework. Objects do not own linework glyphs.

Examples:

- outline layer may use `linework.stroke`, `linework.terminal`, and
  `linework.join`
- crack layer may use `linework.stroke`, `linework.break`,
  `linework.join`, and `linework.weight`
- hatch layer may use `linework.pattern`
- texture layer may use `linework.texture`

The package stays reusable. The layer records the use.

## Metadata Contract

Each generated linework glyph should describe:

- `linework_package`
- `stroke_topology`
- `stroke_ports`
- `angle_degrees`
- `thickness`
- `weight_profile`
- `cap_style`
- `join_style`
- `break_rhythm`
- `roughness`
- `continuity`
- `motion_profile`
- `speed_class`
- `pressure_curve`
- `stress_points`
- `release_style`
- `dwell`
- `stroke_confidence`
- `rhythm_role`
- `acceleration`

The current motion vocabulary is generated and audited by
`glyph_lab.motion_taxonomy`:

- `steady_pull`
- `pressed_pull`
- `angled_pull`
- `interrupted_pull`
- `press_and_stop`
- `direction_change`
- `rounded_turn`
- `repeated_motion`

Legacy fields such as `connector_sides`, `variant`, and `ascii_fallback` may
remain for bridge compatibility, but they are not the doctrine.

## Coverage

Run motion coverage reports before adding new packages:

```sh
python3 -m glyph_lab.cli linework-coverage \
  --glyphs packs/stone_architecture_4x4/linework_accepted_candidates.json \
  --out packs/stone_architecture_4x4/linework_motion_coverage.json
```

The report shows package counts, motion profile counts, package/profile
coverage, missing expected profiles, and records missing motion fields. This is
the first gate before escalating from 4x4 to 8x8.

## Rule

Linework packages define reusable stroke atoms. Layers decide where atoms are
used. Objects never get one-off glyph packages.
