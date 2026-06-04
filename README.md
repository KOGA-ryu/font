# glyph_lab_v0

First proof slice for a custom semantic glyph-brush system.

This is a no-UI Python tool that treats custom glyphs as measured brush stamps,
not font characters. A 4x4 glyph atlas can be generated, measured, rendered as a
contact sheet, and compiled from an ASCII control grid into PNG proof layers.

This is not an Aseprite plugin, Blender tool, or font editor.

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
measured and reviewed, but they are not promoted into `glyphs.json` in this
slice.

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

## Tests

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
```
