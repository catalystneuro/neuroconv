# Illustration brief: linking response-series channels to the FiberPhotometryTable

## What this is for

The fiber photometry how-to (`docs/how_to/annotate_fiber_photometry_metadata.rst`) needs one friendly,
conceptual illustration near the top, right after the paragraph that introduces the
`FiberPhotometryTable`. Its job is to make one idea obvious at a glance: a fiber photometry recording is
a set of data channels, and annotation attaches provenance to each channel by linking it to a row of a
table. This is an illustration, not a UML/class diagram. Do NOT reproduce the dense auto-generated
Mermaid `classDiagram` from the ndx-fiber-photometry README; that shows every type and attribute and is
the wrong altitude for a how-to.

## The one concept to convey

Each channel of a `FiberPhotometryResponseSeries` points, through its `fiber_photometry_table_region`, to
one row of a `FiberPhotometryTable`. That row is the channel's provenance: where it was recorded, at what
wavelengths, and with which hardware and indicator.

## The concrete scene to draw

Use the signal + isosbestic example, because it shows two channels mapping to two rows cleanly:

- A `FiberPhotometryResponseSeries` with two channels (two fluorescence traces): a 465 nm calcium signal
  and a 405 nm isosbestic control, recorded through one optical fiber in the VTA (ventral tegmental
  area).
- A `FiberPhotometryTable` with two rows, `vta_465` and `vta_405`.
- Channel 0 links to row `vta_465`; channel 1 links to row `vta_405`. Show these as two arrows from the
  channels down into the matching rows (the link is `fiber_photometry_table_region`).

## What each row should display (real columns, real values)

Keep the column names exact; these are the required columns of the table:

- `location` = VTA
- `excitation_wavelength_in_nm` = 465 (row 1) / 405 (row 2)
- `emission_wavelength_in_nm` = 525 (both)
- `optical_fiber` -> a small "OpticalFiber" chip/box (both rows point at the same fiber here)
- `excitation_source` -> "ExcitationSource 465" / "ExcitationSource 405"
- `photodetector` -> "Photodetector"
- `indicator` -> "GCaMP6s"

Draw the first three as plain values written in the row, and the last four as links to little
device/indicator objects sitting to the side (an arrow from the row cell to the object). That visually
distinguishes "values stored on the row" from "references to shared objects," which is the key mental
model.

## Rough layout (a sketch to make prettier, not to copy literally)

```
   FiberPhotometryResponseSeries   (data: time x 2 channels)

      channel 0            channel 1
    ┌───────────┐        ┌───────────┐
    │  ~signal~ │        │ ~control~ │        two fluorescence traces
    └─────┬─────┘        └─────┬─────┘
          │  fiber_photometry_table_region   │
          ▼                                  ▼
   ┌──────────────────────  FiberPhotometryTable  ──────────────────────┐
   │ row "vta_465"   location=VTA   excitation=465 nm   emission=525 nm  │──▶ OpticalFiber
   │                 optical_fiber · excitation_source · photodetector   │──▶ ExcitationSource 465
   │                 indicator                                           │──▶ Photodetector
   ├─────────────────────────────────────────────────────────────────── │──▶ Indicator (GCaMP6s)
   │ row "vta_405"   location=VTA   excitation=405 nm   emission=525 nm  │   (isosbestic control)
   └────────────────────────────────────────────────────────────────────┘
```

## Style

- Illustrative and light: rounded boxes, soft colors, clear directional arrows. Think "explainer figure,"
  not "engineering schema."
- Two visual groups: the data (the series and its channels) at the top, the provenance (the table and the
  device/indicator objects) below/beside, with the linking arrows crossing between them as the focal
  point.
- Color-code the two channels (e.g. green for the 465 signal, violet/gray for the 405 control) and carry
  that color into their matching rows so the channel-to-row mapping reads instantly.
- Minimal text. Only the labels above; no attribute lists, no types, no cardinalities.

## Deliverable

- An SVG (preferred, crisp at any zoom) plus a PNG fallback, sized to sit inline in a docs page (roughly
  700-900 px wide). Place under `docs/img/` and it will be embedded with an `.. image::` / `.. figure::`
  directive.
- Must read clearly in both light and dark backgrounds if feasible (the docs use the pydata Sphinx
  theme, which has a dark mode).

## Current state and handoff

A temporary ASCII placeholder already sits in the how-to
(`docs/how_to/annotate_fiber_photometry_metadata.rst`), right after the column table, with a source
comment marking it for replacement. Your job is to produce the polished figure described here and swap it
in. Please ask clarifying questions to pin down the design (scene, palette, level of detail, dark-mode
handling) before delivering the final asset rather than guessing.

## Accuracy guardrails

- This illustrates neuroconv's model: keyed table rows, and channels linked to rows via
  `fiber_photometry_table_region`. Do not draw the extension's raw list-based layout
  (`OpticalFibers`/`ExcitationSources` as lists, table-level `location`), which is a different schema.
- The device/indicator objects are shared: multiple rows can point at the same `optical_fiber`. Here both
  rows share one fiber and differ only in excitation wavelength/source. Keep that truthful.
- Column names must match exactly (`excitation_wavelength_in_nm`, `optical_fiber`, `indicator`, etc.).
