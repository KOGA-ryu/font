# Linework Research Notes

The linework system treats a glyph as a 4x4 sample of practiced stroke motion,
not as a copy of an object feature.

These sources define useful variables. They do not define the art direction.
The art direction remains: linework is performed motion made visible.

## Digital Ink

- Wacom WILL ink pipeline:
  `https://developer-docs.wacom.com/docs/sdk-for-ink/tech/pipeline/`
- Wacom WILL overview:
  `https://developer-docs.wacom.com/docs/sdk-for-ink/overview/`

Useful variables:

- position
- phase: begin, update, end
- timestamp
- force / pressure
- radius
- tilt / altitude / azimuth
- velocity derived from position and time

Mapping into glyph metadata:

- `speed_class`
- `pressure_curve`
- `release_style`
- `dwell`
- `acceleration`
- `stress_points`

## Brush Engines

- Krita brush sensors:
  `https://docs.krita.org/en/reference_manual/brushes/brush_settings/tablet_sensors.html`
- Krita brush settings:
  `https://docs.krita.org/en/reference_manual/brushes/brush_settings.html`
- MyPaint concepts:
  `https://www.mypaint.app/en/docs/manuals/v0.9.0/concepts/`
- MyPaint Brushlib:
  `https://github-wiki-see.page/m/mypaint/libmypaint/wiki/Using-Brushlib`

Useful variables:

- pressure
- speed
- drawing angle
- distance
- time
- fade
- tilt
- direction
- dabs / stroke samples

Mapping into glyph metadata:

- `motion_profile`
- `rhythm_role`
- `stroke_confidence`
- `roughness`
- `weight_profile`
- `break_rhythm`

## Drawing Process

- Stroke-based gesture drawing:
  `https://www.sciencedirect.com/science/article/pii/S2096579622000791`
- Drawing choice and experience:
  `https://pmc.ncbi.nlm.nih.gov/articles/PMC8575256/`

Useful idea:

Line drawings communicate through selected, practiced marks. A good glyph
system should infer and compose plausible mark-making behavior, not chase exact
pixel copying.

## Current 4x4 Motion Vocabulary

- `steady_pull`: continuous direct stroke
- `pressed_pull`: heavier slower pass-through stroke
- `angled_pull`: diagonal direct stroke
- `interrupted_pull`: implied motion through a visible gap
- `press_and_stop`: terminal stroke ending
- `direction_change`: hard turn / join
- `rounded_turn`: soft turn / curve approximation
- `repeated_motion`: hatch or repeated mark system

8x8 is not the default. It becomes valid only after the 4x4 coverage report
shows a motion state that cannot be represented with the current cell size.
