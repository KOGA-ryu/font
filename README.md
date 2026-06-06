# glyph_lab_v0

First proof slice for a custom semantic glyph-brush system.

This is a no-UI Python tool that treats custom glyphs as measured brush stamps,
not font characters. A 4x4 glyph atlas can be generated, measured, rendered as a
contact sheet, and compiled from an ASCII control grid into PNG proof layers.

This is not an Aseprite plugin, Blender tool, or font editor.

## Flat and layered grids

A flat grid is one token per output cell. It is useful for quick proofs where a
single glyph stamp owns each 4x4 cell.

A layered grid is multiple brush passes per output cell. Separate semantic
layers can place mass/base fill, shadow, highlight, edge, detail, ornament, and
measurement glyphs into the same cell; the compositor renders them in a
deterministic layer order.

The layered proof pipeline is:

```text
glyph pack
-> layered control grid
-> deterministic layer compositor
-> proof PNG + layer PNGs + manifest
```

The first image probe keeps the same proof-first model:

```text
pixels are evidence
-> image_probe measures basic masks/maps
-> layered glyph grid records proof
-> compositor renders proof
```

It is a small evidence extractor, not object recognition. It converts a
grayscale or RGB image into mass, value, and edge evidence layers, maps those
layers to existing glyph tokens, and compiles the generated layered grid through
the same compositor.

The linework image analyzer declares stroke motion during image processing:

```text
image
-> sampled linework evidence
-> per-cell motion declarations
-> motion-aware glyph selection
-> linework layered grid
-> linework pressure layer
-> compositor proof
```

This path writes a dedicated `linework` layer. Each non-empty cell records the
motion it asks for: topology, angle, speed, pressure, stress, dwell, release,
rhythm, continuity, confidence, selected token, and selected glyph. The image
processor declares the motion; the glyph pack answers with the closest reusable
stroke atom.

The same pass derives `linework_pressure`, a second layer for stroke weight. It
marks cells where motion evidence indicates heavier pressure, slower movement,
dwell, terminal stress, corner stress, or repeated accent. It is still
linework, not object shading.

The first profile measurement pass stays grid-based:

```text
silhouette
-> boundary
-> profiles
-> dimensions
-> simple shape classification
```

It extracts contour cells, left/right row profiles, width profiles, basic
dimensions, taper, symmetry error, bulge/neck rows, and a simple
`rectangle`/`circle_or_ellipse`/`taper_column`/`unknown` classification.

The first rhythm pass measures repeated construction evidence:

```text
sampled image grid
-> vertical groove evidence
-> horizontal band evidence
-> spacing/rhythm measurements
-> overlay grid
```

Repeated vertical grooves are flute/rib/fold evidence. Horizontal bands are
moulding/rail/trim evidence. Rhythm measurements help later passes infer known
object families without doing ornament inference or ML.

The first fusion pass combines measured evidence:

```text
profile measurements
-> rhythm measurements
-> fused feature flags
-> object family hints
```

Profile measures shape. Rhythm measures repeated construction. Fusion combines
that evidence into flags such as `tall`, `tapered`, `symmetric`,
`repeated_vertical_grooves`, and `moulding_stack`. Object hints compare those
flags against explicit rules for `fluted_column`, `simple_column`,
`banded_block`, `rail_segment`, `panel`, and `unknown`. There is no ML in this
step.

The art-pass-first measurement path corrects the measurement direction:

```text
rough image measurement
-> art glyph passes
-> cleaned layered proof
-> measuring glyph pass
-> deductions / dimensions / confidence
```

Pixels are rough evidence. Rough measurement can find crop, silhouette, coarse
bounds, and centerline, but final measurements should be read from organized
art evidence. Art glyph passes separate that evidence into linework,
value-gradient, shadow, highlight, colour/material, and texture/detail layers.
Measuring glyphs operate after those passes and final records carry provenance,
source layers, source measurements, method notes, and confidence.

`shadow_depth_hint` is deliberately relative. A single uncalibrated image does
not provide real-world depth without scale, light, and camera data, so v0 writes
relative hints unless a later calibrated reference exists.

The construction scaffold pass models a drawing workflow:

```text
find the largest simple support line
-> attach smaller difficult lines to it
-> measure angles against the support line
-> work from center outward
-> scale the whole construction to fit the target grid
-> add detail
```

This is not object-family inference. It extracts a deterministic grid-based
support graph with a `primary_support_line`, anchor points, attached lines,
angle measurements, and a scale fit warning when the form should be drawn
smaller before detail is added.

The linework glyph kit is the bridge between normal ASCII rendering and custom
glyph drawing. The image-to-ASCII workbench can still emit character grids, but
those characters become bridge keys for 4x4 glyph stamps:

```text
math line primitives
-> 4x4 linework glyph candidates
-> review/scoring
-> ASCII bridge palettes
-> image-to-ASCII rough grid
-> custom glyph layered proof
```

This keeps 4x4 linework manageable. Straight lines, offsets, diagonals, caps,
corners, hatching, and crosshatching are generated from geometry instead of
being hand-authored one at a time. Normal ASCII characters such as `-`, `|`,
`/`, `\`, `+`, and temporary bridge keys can piggyback on the ASCII engine while
the rendered mark comes from the custom glyph pack.

Linework means stroke grammar, not object meaning. A crack, contour, fold,
edge, or shadow is an interpretation built from reusable stroke atoms. The
doctrine is locked in [LINEWORK_DOCTRINE.md](LINEWORK_DOCTRINE.md): generated
linework candidates record ports, topology, weight, cap/join behavior, break
rhythm, roughness, and continuity so packages can be reused across layers and
objects.

The motion research notes are in [docs/LINEWORK_RESEARCH.md](docs/LINEWORK_RESEARCH.md).
The code treats each 4x4 glyph as a sample of practiced motion state: speed,
pressure, stress, dwell, release, rhythm, confidence, and acceleration. The
target is not exact pixel copy; it is a reusable motion vocabulary that can
compose convincing linework.

Motion glyph expansion adds reusable pressure and gesture atoms on top of the
basic line/corner/hatch kit. These candidates are intentionally packaged as
generic `detail/motion` glyphs, not object-specific crack, slab, column, or
stone glyphs. The v0 motion packages cover pressed pulls, angled pulls,
direction changes, rounded turns, press-and-stop terminals, and repeated motion
patterns. The image pass declares the motion it sees; the selector chooses the
closest promoted glyph package for that layer.

The brush glyph kit applies the same idea to digital-painting brush behavior:

```text
brush tip / shape
-> spacing and broken stroke variants
-> scatter / spray
-> grain and texture
-> reviewable 4x4 glyph candidates
-> ASCII texture and spray palettes
```

The generated brush families are `hatch`, `crosshatch`, `stipple`, `spray`,
`charcoal`, `dry_brush`, `grain`, `scratch`, `chip`, and `tone_hatch`. These
are modeled after common digital brush controls: tip shape, density, scatter
direction, roughness, coverage, grain, incised marks, chipped-edge damage, tone
gradients, and contour hatching. They are still deterministic 4x4 glyph stamps,
not a paint engine, and they are not hardcoded to a slab, crack, column, or
single object.

## Transform and equivalence model

The transform slice reduces glyph authoring by making one seed stamp generate
measured variants:

```text
seed glyph -> transforms -> variants -> measured features -> selected active pack
```

The review pipeline is:

```text
seed glyph
-> transforms
-> generated variants
-> primitive generation
-> measured features
-> scoring/rejection
-> reviewed candidates
-> future active pack promotion
-> compiler
```

`glyph_lab.transforms` supports 4x4 stamp operations:

- `rotate_90`, `rotate_180`, `rotate_270`
- `flip_horizontal`, `flip_vertical`
- `shift(dx, dy)` with clipping at the 4x4 cell boundary
- `normalize_to_top_left` for texture/noise-style stamps
- `stamp_to_bitmask` and `bitmask_to_stamp`

`glyph_lab.equivalence` canonicalizes stamps by transform group:

- `exact`
- `rotations`
- `mirrors`
- `dihedral8`
- `translations_normalized`

Generated variants keep lineage metadata in a separate file instead of changing
the active glyph pack. Each generated record includes `source_glyph_id`,
`transform_chain`, and `generated: true`, while inheriting role, family, layer,
and palette role unless a demo variant explicitly overrides one.

`glyph_lab.scoring` assigns deterministic `usefulness_score`, `rejection_reason`,
and `review_tags` fields from measured features. `glyph_lab.candidate_filter`
rejects empty non-empty roles, solid non-solid roles, disconnected non-texture
shapes, weak edge/corner connectors, duplicate canonical IDs, and candidates too
similar to already accepted glyphs.

`glyph_lab.primitives` can create deterministic 4x4 candidates from point, line,
block, corner, crack, fill, and bevel primitive families. These candidates are
measured and reviewed, but they are only promoted into `glyphs.json` through an
explicit dry-run-first promotion request.

## Setup

```sh
python3 -m pip install -r requirements.txt
```

## Generate the default pack

```sh
python3 -m glyph_lab.cli init-pack
```

Writes:

- `packs/stone_architecture_4x4/glyphs.json`
- `packs/stone_architecture_4x4/atlas.png`
- `packs/stone_architecture_4x4/contact_sheet.png`
- `packs/stone_architecture_4x4/features.json`
- `packs/stone_architecture_4x4/generated_variants.json`

## Score generated candidates

```sh
python3 -m glyph_lab.cli review-candidates
```

Writes:

- `packs/stone_architecture_4x4/candidate_scores.json`
- `packs/stone_architecture_4x4/accepted_candidates.json`
- `packs/stone_architecture_4x4/rejected_candidates.json`
- `packs/stone_architecture_4x4/review_contact_sheet.png`

## Generate primitive candidates

```sh
python3 -m glyph_lab.cli generate-primitives \
  --pack packs/stone_architecture_4x4
```

Writes review-only primitive artifacts:

- `packs/stone_architecture_4x4/primitive_candidates.json`
- `packs/stone_architecture_4x4/primitive_candidate_scores.json`
- `packs/stone_architecture_4x4/primitive_accepted_candidates.json`
- `packs/stone_architecture_4x4/primitive_rejected_candidates.json`
- `packs/stone_architecture_4x4/primitive_review_contact_sheet.png`

## Generate linework candidates

```sh
python3 -m glyph_lab.cli generate-linework \
  --pack packs/stone_architecture_4x4
```

Writes review-only linework artifacts:

- `packs/stone_architecture_4x4/linework_candidates.json`
- `packs/stone_architecture_4x4/linework_candidate_scores.json`
- `packs/stone_architecture_4x4/linework_accepted_candidates.json`
- `packs/stone_architecture_4x4/linework_rejected_candidates.json`
- `packs/stone_architecture_4x4/linework_review_contact_sheet.png`
- `packs/stone_architecture_4x4/ascii_linework_palette.txt`
- `packs/stone_architecture_4x4/ascii_shade_palette.txt`
- `packs/stone_architecture_4x4/ascii_glyph_mapping.json`

Audit the generated motion vocabulary:

```sh
python3 -m glyph_lab.cli linework-coverage \
  --glyphs packs/stone_architecture_4x4/linework_accepted_candidates.json \
  --out packs/stone_architecture_4x4/linework_motion_coverage.json
```

This writes a coverage report grouped by motion package and motion profile. Use
that report before adding package generators or proposing an 8x8 escalation.

## Analyze Image Linework Motion

```sh
python3 -m glyph_lab.cli analyze-linework-image \
  --pack packs/stone_architecture_4x4 \
  --image examples/probe_cracked_stone_slab.png \
  --out out_linework_motion \
  --grid-size 32
```

Writes:

- `out_linework_motion/linework_evidence.json`
- `out_linework_motion/linework_pressure_evidence.json`
- `out_linework_motion/generated_motion_layered_grid.json`
- `out_linework_motion/motion_selection_report.json`
- `out_linework_motion/proof_128.png`
- `out_linework_motion/layers/linework.png`
- `out_linework_motion/layers/linework_pressure.png`
- `out_linework_motion/manifest.json`

If `glyphs.promoted.json` and `atlas.promoted.png` exist, this command uses
them by default. Otherwise it falls back to the active `glyphs.json` and
`atlas.png`. Use `--glyphs` and `--atlas` to override that choice.

Generate a visual layer breakdown for deciding what glyph package to build next:

```sh
python3 -m glyph_lab.cli layer-breakdown \
  --pack packs/stone_architecture_4x4 \
  --image examples/probe_cracked_stone_slab.png \
  --motion-out out_linework_motion_slab \
  --out out_layer_breakdown \
  --grid-size 32
```

Writes:

- `out_layer_breakdown/layer_breakdown.png`
- `out_layer_breakdown/layer_breakdown.json`

The sheet shows the original, crop, luminance grid, mass mask, edge evidence,
linework layer, linework pressure layer, and final glyph proof. The JSON records
counts, top motion profiles, selected tokens, pressure intensities, and warning
counts. Use this to choose glyph work from layer failures instead of guessing.

The palette files are meant for
`/Users/kogaryu/gameguy-3d-lab/image_to_ascii_workbench_v3`. Use them with
`--palette custom --custom-palette ...` so the ASCII output can act as a rough
glyph-control grid. The mapping JSON records which ASCII bridge key points to
which active or review-only glyph.

## Generate brush candidates

```sh
python3 -m glyph_lab.cli generate-brushes \
  --pack packs/stone_architecture_4x4
```

Writes review-only brush artifacts:

- `packs/stone_architecture_4x4/brush_candidates.json`
- `packs/stone_architecture_4x4/brush_candidate_scores.json`
- `packs/stone_architecture_4x4/brush_accepted_candidates.json`
- `packs/stone_architecture_4x4/brush_rejected_candidates.json`
- `packs/stone_architecture_4x4/brush_review_contact_sheet.png`
- `packs/stone_architecture_4x4/ascii_texture_palette.txt`
- `packs/stone_architecture_4x4/ascii_spray_palette.txt`
- `packs/stone_architecture_4x4/ascii_brush_mapping.json`

Use the texture palette for hatching, crosshatching, tone hatching, charcoal,
dry-brush, grain, scratch, and chipped-edge detail passes. Use the spray palette for
stipple/scatter passes. If the accepted brush set exceeds the printable ASCII
bridge pool, the overflow remains in `brush_accepted_candidates.json` and is
listed under `skipped_bridge_candidates` in `ascii_brush_mapping.json`.

When passing the linework palette on the command line, use the equals form
because the palette may begin with `-`:

```sh
PALETTE="$(tr -d '\n' < packs/stone_architecture_4x4/ascii_linework_palette.txt)"
python3 -m image_to_ascii_workbench.cli input.png \
  --width 32 \
  --height 32 \
  --palette custom \
  --custom-palette="$PALETTE" \
  --edge-mode sobel-hybrid
```

The mapping also aliases the workbench's Unicode Sobel edge output, such as `│`
and `─`, back to the active custom vertical and horizontal glyphs.

`examples/probe_linework_stress.png` is a deterministic high-contrast linework
fixture for this loop. It stresses horizontal bands, broken bands, top cap
lines, broken vertical grooves, and diagonal scratches.

`examples/probe_cracked_stone_slab.png` is a reusable linework/texture stress
fixture. It is meant to exercise stroke grammar, hatching, stipple, and rough
ink behavior, not to justify object-specific glyph packages.

## Import ASCII as custom glyph layers

After the external image-to-ASCII workbench writes a text grid, import it into
`glyph_lab`:

```sh
python3 -m glyph_lab.cli import-ascii-grid \
  --pack packs/stone_architecture_4x4 \
  --ascii out_linework_ascii.txt \
  --mapping packs/stone_architecture_4x4/ascii_glyph_mapping.json \
  --out out_ascii_bridge
```

Writes:

- `out_ascii_bridge/generated_layered_grid.json`
- `out_ascii_bridge/proof_128.png`
- `out_ascii_bridge/layers/*.png`
- `out_ascii_bridge/manifest.json`

For v0, review-only linework and brush bridge keys resolve through their
`ascii_fallback` to active glyph tokens. That means an unpromoted bridge key
like `A` can still render as `-` until the candidate is promoted into a dry-run
glyph pack. The manifest records those fallbacks so the accuracy loop is
visible:

```text
ASCII rough grid
-> active custom glyph proof
-> inspect fallback warnings
-> promote missing line/brush glyphs
-> rerun proof
```

Generate a promotion request from the fallback warnings:

```sh
python3 -m glyph_lab.cli suggest-ascii-promotions \
  --manifest out_ascii_bridge/manifest.json \
  --mapping packs/stone_architecture_4x4/ascii_glyph_mapping.json \
  --accepted packs/stone_architecture_4x4/linework_accepted_candidates.json \
  --out packs/stone_architecture_4x4/linework_promote_candidates.json
```

Then dry-run promotion from the linework accepted file:

```sh
python3 -m glyph_lab.cli promote-candidates \
  --pack packs/stone_architecture_4x4 \
  --accepted packs/stone_architecture_4x4/linework_accepted_candidates.json \
  --request packs/stone_architecture_4x4/linework_promote_candidates.json
```

This writes `glyphs.promoted.json` without mutating `glyphs.json`. Use `--apply`
only after inspecting the promoted pack and report.

Generic motion glyph packages can be stacked immediately after the base
linework promotion:

```sh
python3 -m glyph_lab.cli promote-candidates \
  --pack packs/stone_architecture_4x4 \
  --base-glyphs packs/stone_architecture_4x4/glyphs.promoted.json \
  --accepted packs/stone_architecture_4x4/linework_accepted_candidates.json \
  --request packs/stone_architecture_4x4/linework_motion_promote_candidates.json
```

This adds reusable motion-package tokens for pressure pulls, angled pulls,
direction changes, rounded turns, and terminal stops while keeping
`glyphs.json` untouched.

Brush promotions can be stacked on top of a linework dry-run by using that
promoted file as the base. `suggest-ascii-promotions --base-glyphs` skips
bridge keys that are already real tokens in the base pack:

```sh
python3 -m glyph_lab.cli suggest-ascii-promotions \
  --manifest out_brush_texture_smoke/manifest.json \
  --mapping packs/stone_architecture_4x4/ascii_brush_mapping.json \
  --accepted packs/stone_architecture_4x4/brush_accepted_candidates.json \
  --out packs/stone_architecture_4x4/brush_promote_candidates.json \
  --limit 8 \
  --base-glyphs packs/stone_architecture_4x4/glyphs.promoted.json

python3 -m glyph_lab.cli promote-candidates \
  --pack packs/stone_architecture_4x4 \
  --base-glyphs packs/stone_architecture_4x4/glyphs.promoted.json \
  --accepted packs/stone_architecture_4x4/brush_accepted_candidates.json \
  --request packs/stone_architecture_4x4/brush_promote_candidates.json
```

That cumulative dry-run keeps active `glyphs.json` untouched while letting the
proof pack contain linework and texture brush glyphs at the same time.

Texture/detail package promotions can be stacked after the brush promotion
rounds:

```sh
python3 -m glyph_lab.cli promote-candidates \
  --pack packs/stone_architecture_4x4 \
  --base-glyphs packs/stone_architecture_4x4/glyphs.promoted.json \
  --accepted packs/stone_architecture_4x4/brush_accepted_candidates.json \
  --request packs/stone_architecture_4x4/texture_detail_promote_candidates.json
```

This promotes representative scratch and chip glyphs into the dry-run pack
without mutating `glyphs.json`.

Tone hatch package promotions can be stacked after the texture/detail package:

```sh
python3 -m glyph_lab.cli promote-candidates \
  --pack packs/stone_architecture_4x4 \
  --base-glyphs packs/stone_architecture_4x4/glyphs.promoted.json \
  --accepted packs/stone_architecture_4x4/brush_accepted_candidates.json \
  --request packs/stone_architecture_4x4/tone_hatch_promote_candidates.json
```

This promotes representative gradient, contour, and staggered hatch glyphs into
the dry-run pack without mutating `glyphs.json`.

Build an atlas for the dry-run promoted pack:

```sh
python3 -m glyph_lab.cli build-promoted-atlas \
  --pack packs/stone_architecture_4x4 \
  --glyphs packs/stone_architecture_4x4/glyphs.promoted.json \
  --out packs/stone_architecture_4x4/atlas.promoted.png
```

Then rerun the ASCII import using the promoted glyph metadata and promoted
atlas:

```sh
python3 -m glyph_lab.cli import-ascii-grid \
  --pack packs/stone_architecture_4x4 \
  --glyphs packs/stone_architecture_4x4/glyphs.promoted.json \
  --atlas packs/stone_architecture_4x4/atlas.promoted.png \
  --ascii out_linework_stress/input_ascii.txt \
  --mapping packs/stone_architecture_4x4/ascii_glyph_mapping.json \
  --out out_linework_stress_promoted
```

This proves whether fallback warnings disappear before mutating the active
`glyphs.json`.

Compare the active proof against the promoted proof:

```sh
python3 -m glyph_lab.cli compare-ascii-fallbacks \
  --before out_brush_texture_smoke/manifest.json \
  --after out_brush_texture_promoted/manifest.json \
  --out out_brush_compare \
  --mapping packs/stone_architecture_4x4/ascii_brush_mapping.json \
  --accepted packs/stone_architecture_4x4/brush_accepted_candidates.json \
  --base-glyphs packs/stone_architecture_4x4/glyphs.promoted.json \
  --limit 8
```

Writes:

- `out_brush_compare/fallback_compare.json`
- `out_brush_compare/next_promote_candidates.json` when mapping and accepted
  files are provided

The comparison report records fallback totals before/after, reduction
percentage, fixed bridge keys, top remaining fallback keys, unmapped counts,
and the next evidence-driven promotion request.

Generate a contact sheet for only promoted glyphs:

```sh
python3 -m glyph_lab.cli promoted-contact-sheet \
  --glyphs packs/stone_architecture_4x4/glyphs.promoted.json \
  --atlas packs/stone_architecture_4x4/atlas.promoted.png \
  --out packs/stone_architecture_4x4/promoted_contact_sheet.png
```

The promoted sheet groups linework and brush glyphs so the dry-run pack can be
reviewed without scanning the full active atlas.

## Promote reviewed candidates

Promotion is dry-run first. Write a request file such as
`packs/stone_architecture_4x4/promote_candidates.json`:

```json
{
  "promote": [
    {
      "candidate_id": "4.stone.primitive.point.dot_1_2_2000",
      "notes": "Promote a small damage mark."
    }
  ]
}
```

Run the dry-run:

```sh
python3 -m glyph_lab.cli promote-candidates \
  --pack packs/stone_architecture_4x4 \
  --request packs/stone_architecture_4x4/promote_candidates.json
```

Writes:

- `packs/stone_architecture_4x4/glyphs.promoted.json`
- `packs/stone_architecture_4x4/promotion_report.json`

Apply only after inspecting those files:

```sh
python3 -m glyph_lab.cli promote-candidates \
  --pack packs/stone_architecture_4x4 \
  --request packs/stone_architecture_4x4/promote_candidates.json \
  --apply
```

The safe workflow is:

```text
generate candidates
-> review contact sheet
-> write promote_candidates.json
-> dry-run promotion
-> inspect glyphs.promoted.json and promotion_report.json
-> apply promotion
-> regenerate atlas/features/contact sheet
```

Dry-run does not mutate `glyphs.json`. `--apply` backs up the old file as
`glyphs.backup.<timestamp>.json` before writing the promoted pack.

Use `--base-glyphs` when a promotion request should build from an existing
dry-run file instead of the active pack. This is useful for review passes such
as:

```text
active glyphs
-> linework dry-run promotions
-> brush dry-run promotions using linework as the base
-> promoted atlas
-> ASCII proof with fewer bridge fallbacks
```

## Compile the example grid

```sh
python3 -m glyph_lab.cli compile \
  --pack packs/stone_architecture_4x4 \
  --grid examples/stone_post_grid.txt \
  --out out
```

Writes:

- `out/proof_128.png`
- `out/layers/base_fill.png`
- `out/layers/edge.png`
- `out/layers/shadow.png`
- `out/layers/detail.png`
- `out/manifest.json`

Rules:

- Space means transparent.
- Unknown tokens raise an error with row, column, and character.
- Each control-grid character expands to one 4x4 stamp.
- A 32x32 grid outputs a 128x128 PNG.

## Compile the layered example

```sh
python3 -m glyph_lab.cli compile-layered \
  --pack packs/stone_architecture_4x4 \
  --input examples/layered_stone_post.json \
  --out out_layered
```

Layer order:

1. `background`
2. `mass`
3. `base_fill`
4. `shadow`
5. `highlight`
6. `edge`
7. `detail`
8. `ornament`
9. `measurement`

Writes:

- `out_layered/proof_128.png`
- `out_layered/layers/mass.png`
- `out_layered/layers/base_fill.png`
- `out_layered/layers/shadow.png`
- `out_layered/layers/highlight.png`
- `out_layered/layers/edge.png`
- `out_layered/layers/detail.png`
- `out_layered/layers/ornament.png`
- `out_layered/layers/measurement.png`
- `out_layered/manifest.json`

Layered rules:

- All layer grids must have the declared width and height.
- Space means no glyph on that layer.
- Unknown tokens report layer name, row, column, and character.
- Layer constraint mismatches are recorded as manifest warnings.

## Probe an image into layered glyphs

```sh
python3 -m glyph_lab.cli probe-image \
  --pack packs/stone_architecture_4x4 \
  --image examples/probe_input.png \
  --out out_probe \
  --grid-size 32
```

Writes:

- `out_probe/generated_layered_grid.json`
- `out_probe/probe_measurements.json`
- `out_probe/proof_128.png`
- `out_probe/layers/*.png`
- `out_probe/manifest.json`

The probe:

- loads the image with Pillow
- converts it to grayscale luminance
- auto-crops the non-white area
- samples a 32x32 measurement grid
- extracts a mass mask, value bands, and Sobel-like edge evidence
- maps those evidence layers to active glyph tokens by metadata

## Measure a silhouette profile

```sh
python3 -m glyph_lab.cli measure-profile \
  --image examples/probe_taper_column.png \
  --out out_profile \
  --grid-size 32
```

Writes:

- `out_profile/profile_measurements.json`
- `out_profile/profile_overlay_grid.txt`
- `out_profile/profile_overlay.png`

The profile pass measures the mass mask from a sampled image. It records the
crop box, occupied cell bounds, centerline estimate, left/right/width profiles,
top/middle/bottom widths, taper ratio, symmetry error, row width variance,
likely shape, bulge rows, and neck rows.

## Measure repeated grooves and bands

```sh
python3 -m glyph_lab.cli measure-rhythm \
  --image examples/probe_fluted_column.png \
  --out out_rhythm \
  --grid-size 32
```

Writes:

- `out_rhythm/rhythm_measurements.json`
- `out_rhythm/rhythm_overlay_grid.txt`
- `out_rhythm/rhythm_overlay.png`

The rhythm pass records vertical grooves, horizontal bands, average spacing,
spacing variance, average groove length, groove region bounds, rhythm
confidence, `likely_repeated_grooves`, and `likely_moulding_stack`. The overlay
grid uses `|` for groove centerlines, `=` for bands, `+` for crossings, and `.`
for mass/fill.

## Fuse Measurements Into Object Hints

```sh
python3 -m glyph_lab.cli hint-object \
  --profile out_profile/profile_measurements.json \
  --rhythm out_rhythm/rhythm_measurements.json \
  --out out_hint
```

Writes:

- `out_hint/fused_features.json`
- `out_hint/object_family_hints.json`

Each object hint includes a family, confidence, reasons, missing evidence, and
the measurement sources used.

## Measure from art passes

```sh
python3 -m glyph_lab.cli measure-from-art-passes \
  --probe out_probe/probe_measurements.json \
  --profile out_profile/profile_measurements.json \
  --rhythm out_rhythm/rhythm_measurements.json \
  --layered out_probe/generated_layered_grid.json \
  --out out_measure_art
```

Writes:

- `out_measure_art/final_measurements.json`
- `out_measure_art/art_pass_summary.json`

The command accepts missing probe/profile/rhythm/layered inputs. Missing inputs
produce lower-confidence measurements with missing-evidence notes instead of
pretending the evidence exists.

## Measure a construction scaffold

```sh
python3 -m glyph_lab.cli measure-scaffold \
  --image examples/probe_taper_column.png \
  --out out_scaffold \
  --grid-size 32
```

Writes:

- `out_scaffold/scaffold_measurements.json`
- `out_scaffold/scaffold_overlay_grid.txt`
- `out_scaffold/scaffold_overlay.png`

The overlay uses `|` for the primary vertical support line, `-` for horizontal
attached lines, `+` for anchors, `.` for occupied mass, and `?` for uncertain
attached lines.

## Tests

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
```
