.. _fiber_photometry_metadata_structure:

Fiber Photometry Metadata Structure
===================================

This document describes the fiber photometry metadata system in NeuroConv, used by the single-series
fiber photometry interfaces built on ``BaseFiberPhotometryInterface`` (currently
``TDTFiberPhotometryInterface`` and ``DoricFiberPhotometryInterface``). It is intended as a reference for
developers contributing new fiber photometry interfaces or modifying existing ones, and to document the
design decisions behind the format.

A single-series interface writes exactly one ``FiberPhotometryResponseSeries`` (the ndx-fiber-photometry
neurodata type), assembled from one or more input *streams* (atomic source signals — a TDT store, a
Doric dataset). That series references a *region* of a ``FiberPhotometryTable``, and each row of the
table references the physical hardware (optical fiber, excitation source, photodetector, filters) and
the indicator that produced the trace — much as an ecephys ``ElectricalSeries`` references a region of
the electrodes table.

The typical conversion is a single interface writing one response series. That one series can still be
multi-channel — a multi-fiber, dual-wavelength recording (a calcium signal and an isosbestic control
per fiber) is usually written as one series whose data columns map to several table rows. NeuroConv
also supports running several fiber photometry interfaces together, each writing its own series into
one shared table (as several ecephys recording interfaces share one electrodes table), but that is the
exception, used when you deliberately want distinct response series rather than channels of one series.
The purpose of the fiber photometry metadata dict is to describe the hardware once and let each
interface point its response series at the table rows it needs.


Design Principles
-----------------

The fiber photometry metadata system follows the same spirit as the ophys and ecephys systems (see
:ref:`ophys_metadata_structure`), specialized to the ndx-fiber-photometry data model:

1. **Its own top-level block.** All fiber photometry metadata lives under ``metadata["FiberPhotometry"]``,
   not nested under ``metadata["Ophys"]``. Fiber photometry is technically an optical method, but — like
   the ecephys/icephys split — it has its own interfaces, its own extension, and its own metadata block.

   .. code-block:: python

       metadata["FiberPhotometry"]["FiberPhotometryIndicators"]["gcamp"]["label"] = "GCaMP7b"

2. **Dict-keyed containers, keyed by ``metadata_key``.** Following the ophys metadata system, every
   container is a dict whose keys are ``metadata_key`` handles. The hardware and biology shared across a
   file (device models, devices, optical fibers, indicators, viral vectors and injections, commanded
   voltage, and the table's rows) are keyed this way, and each interface's response series is keyed by
   its own ``metadata_key``. Keying every level lets several interfaces run in one conversion without
   clashing and merges cleanly across interfaces (dicts merge by key), and it decouples an object's
   routing handle from its NWB ``name``.

3. **Linking is by ``_metadata_key``, resolved at write time.** Entries reference each other with
   ``<thing>_metadata_key`` fields holding the *key* of the referenced entry — a device names its model
   via ``model_metadata_key``, a table row names its optical fiber via ``optical_fiber_metadata_key``,
   and a response series names the table rows it spans via ``fiber_photometry_table_region`` (a list of
   row keys). This matches the ophys convention. At write time each key is resolved through its
   container to the entry's ``name`` and then to the actual NWB object; row references resolve to
   integer row indices (their position in the merged rows dict).

4. **One shared, keyed-row table.** A file has a single ``FiberPhotometryTable``. Every response series
   references a *region* of its rows by row key, so regions never depend on fragile integer indices.

5. **Runnable defaults with honest sentinels.** ``get_metadata()`` returns a complete, editable
   scaffold so an interface runs on zero user metadata. Required fields the user must supply are
   pre-filled with sentinels — ``NaN`` for the required numeric wavelengths and the string
   ``"PLACEHOLDER"`` for required strings — and ``add_to_nwbfile`` warns about any that survive to
   write time (or raises, under ``strict=True``).


Metadata Structure Overview
---------------------------

The complete fiber photometry metadata structure (one interface with ``metadata_key="gcamp_dms"``):

.. code-block:: python

    metadata = {
        "NWBFile": {...},   # Session-level metadata
        "Subject": {...},   # Subject information

        "FiberPhotometry": {

            # ----- Shared containers: dicts keyed by metadata_key (built once per file) -----

            # Device models (paired with device instances below)
            "OpticalFiberModels": {
                "ofm": {"name": "optical_fiber_model", "manufacturer": "Doric Lenses", "numerical_aperture": 0.48},
            },
            "ExcitationSourceModels": {
                "esm": {"name": "excitation_source_model", "manufacturer": "Doric Lenses",
                        "source_type": "LED", "excitation_mode": "one-photon"},
            },
            "PhotodetectorModels": {
                "pdm": {"name": "photodetector_model", "manufacturer": "Doric Lenses", "detector_type": "photodiode"},
            },
            # (also BandOpticalFilterModels, EdgeOpticalFilterModels, DichroicMirrorModels)

            # Device instances (each references its model by model_metadata_key)
            "OpticalFibers": {
                "fiber_dms": {"name": "optical_fiber_dms", "model_metadata_key": "ofm",
                              "fiber_insertion": {"depth_in_mm": 4.2, "insertion_position_ap_in_mm": 0.8}},
            },
            "ExcitationSources": {
                "led_465": {"name": "excitation_source_465", "model_metadata_key": "esm"},
            },
            "Photodetectors": {
                "pd": {"name": "photodetector", "model_metadata_key": "pdm"},
            },
            # (also BandOpticalFilters, EdgeOpticalFilters, DichroicMirrors)

            # Indicators, and optionally the viruses/injections that delivered them
            "FiberPhotometryViruses": {
                "aav_gcamp": {"name": "aav_gcamp", "construct_name": "AAV-GCaMP7b"},
            },
            "FiberPhotometryVirusInjections": {
                "inj_dms": {"name": "injection_dms", "viral_vector_metadata_key": "aav_gcamp"},
            },
            "FiberPhotometryIndicators": {
                "gcamp": {"name": "gcamp", "label": "GCaMP7b",
                          "viral_vector_injection_metadata_key": "inj_dms"},
            },

            # Optional commanded-voltage drive signals (data-bearing; read from a stream)
            "CommandedVoltageSeries": {
                "cv_dms": {"name": "commanded_voltage_dms", "stream_name": "Fi1r", "index": 0,
                           "unit": "volts", "frequency": 211.0},
            },

            # The single shared table, rows keyed by metadata_key. Each row = one fiber x one channel.
            "FiberPhotometryTable": {
                "name": "fiber_photometry_table",
                "description": "Fiber photometry setup.",
                "rows": {
                    "dms_465": {
                        "location": "DMS",
                        "excitation_wavelength_in_nm": 465.0,
                        "emission_wavelength_in_nm": 520.0,
                        "indicator_metadata_key": "gcamp",
                        "optical_fiber_metadata_key": "fiber_dms",
                        "excitation_source_metadata_key": "led_465",
                        "photodetector_metadata_key": "pd",
                        "commanded_voltage_series_metadata_key": "cv_dms",   # optional
                    },
                },
            },

            # ----- Per-interface response series, keyed by metadata_key -----
            "gcamp_dms": {
                "name": "FiberPhotometryResponseSeries",
                "description": "GCaMP7b calcium signal in DMS.",
                "unit": "a.u.",
                "fiber_photometry_table_region": ["dms_465"],     # list of ROW metadata_keys
                "fiber_photometry_table_region_description": "DMS calcium signal.",
            },
        },
    }


The metadata_key Parameter
--------------------------

Every single-series interface accepts a keyword-only ``metadata_key`` parameter, following the same
pattern as the ophys interfaces (see :ref:`ophys_metadata_structure`). When ``None`` (the default),
the interface generates a key from the parameters that make it unique — for fiber photometry, the
``stream_names`` — so two interfaces over different streams get distinct keys automatically:

.. code-block:: python

    interface = TDTFiberPhotometryInterface(folder_path=..., stream_names="_405R")
    interface.metadata_key   # -> "fiber_photometry_405r"

``metadata_key`` scopes only this interface's **response series** entry. The shared containers are keyed
independently: devices, indicators, and table rows each have their own ``metadata_key`` handles, so if
several interfaces are combined they can reference the same optical fiber or table row by key regardless
of their own response-series keys. This split is deliberate — the response series is the interface's own
output (one per interface), while the hardware is shared file-wide.

Note that the response series' NWB ``name`` (``"FiberPhotometryResponseSeries"`` by default) is
distinct from its ``metadata_key``. The key identifies the interface's entry; the ``name`` names the
object written to the file. Combine multiple interfaces in a converter and give each a distinct
``metadata_key`` (and typically a distinct series ``name``) to write several series into one file.


Shared Containers and Metadata-Key Linking
------------------------------------------

Following the ophys system, entries reference each other with ``<thing>_metadata_key`` fields holding
the *key* of the referenced entry (not its NWB name). The reference chain is:

- A **device instance** references its **model**: ``"model_metadata_key": "ofm"``.
- A **virus injection** references its **viral vector**: ``"viral_vector_metadata_key": "aav_gcamp"``.
- An **indicator** optionally references its **injection**:
  ``"viral_vector_injection_metadata_key": "inj_dms"``.
- A **table row** references its **devices and indicator** via ``optical_fiber_metadata_key``,
  ``excitation_source_metadata_key``, ``photodetector_metadata_key``, ``indicator_metadata_key``, and
  optionally ``dichroic_mirror_metadata_key``, ``excitation_filter_metadata_key``,
  ``emission_filter_metadata_key``, and ``commanded_voltage_series_metadata_key``.
- A **response series** references the **table rows** it spans:
  ``"fiber_photometry_table_region": ["dms_465", "dms_405"]`` (a list of row keys).

At write time each ``_metadata_key`` is resolved through its container to the entry's ``name`` and then
to the actual NWB object (e.g. an ``optical_fiber_metadata_key`` resolves to ``OpticalFibers[key]["name"]``
and then ``nwbfile.devices[name]``). The device models and instances come in pairs
(``OpticalFiberModels`` / ``OpticalFibers``, ``ExcitationSourceModels`` / ``ExcitationSources``, and so
on). Optical fibers are the one special case: each carries a nested ``fiber_insertion`` block
(stereotaxic coordinates and insertion geometry), a *contained* component specified inline rather than a
separately-keyed object.


The FiberPhotometryTable and Regions
------------------------------------

A file has exactly one ``FiberPhotometryTable``. Each row describes one fiber × one excitation channel
— its brain ``location``, its excitation/emission wavelengths, the indicator, and the hardware that
recorded it. A multi-fiber, dual-wavelength setup therefore has several rows (e.g. ``dms_465``,
``dms_405``, ``dls_465``, ``dls_405``).

Each ``FiberPhotometryResponseSeries`` references a **region** of the table — the subset of rows whose
channels make up that series' data columns — via ``fiber_photometry_table_region``, a list of **row
metadata keys**. At write time these keys are resolved to integer row indices (their position in the
merged ``rows`` dict), so the region ordering matches the data's channel ordering and no interface needs
to know the absolute index a row landed at. Referencing a row key that is not present in the table is a
loud error. This key-based resolution is what makes multi-interface conversions tractable: interface B
can point its region at rows that interface A contributed, purely by key.


Object Creation and Idempotency
-------------------------------

Like the ophys system, objects are not created when the metadata dict is assembled — they are created
during ``add_to_nwbfile``. The shared containers (devices, indicators, and the table) are built
**once per file**, which matters in the less-common case where several interfaces contribute to one
table:

1. The device/indicator/table helpers are idempotent by NWB name. The interface assembles the whole
   ``FiberPhotometry`` lab-metadata (devices, indicators, viruses, injections, and every table row)
   from its metadata; if a later interface finds it already present, it reuses it and adds only its own
   response series.

2. When several interfaces run together, their metadata is merged before writing (by the converter's
   ``dict_deep_update``, which merges the keyed containers by key), so every interface sees the full set
   of shared rows and devices and whichever runs first can build the complete table.

3. Declaring the same-named shared object with *different* contents in two interfaces is a loud error
   rather than a silent merge, so an authoring mistake surfaces immediately.

Commanded voltage is a special case among the shared containers: it is data-bearing (it reads samples
from a stream, not just static metadata). Each ``CommandedVoltageSeries`` entry names the input
``stream_name`` (and optional channel ``index``) to read; a table row then references the resulting
series through its ``commanded_voltage_series_metadata_key``. This is how frequency-multiplexed setups
associate each demodulated signal with the sinusoidal drive that produced it.


Default Scaffold and Placeholder Sentinels
------------------------------------------

``get_metadata()`` returns the NWBFile basics merged with a default ``FiberPhotometry`` block produced
by :func:`~neuroconv.tools.fiber_photometry.get_default_fiber_photometry_metadata`. The scaffold is a
complete, runnable structure — one placeholder device of each kind, one indicator, one table row, and
one response series entry under the interface's ``metadata_key`` — with required fields pre-filled with
sentinels:

- Required **numeric** fields (``excitation_wavelength_in_nm``, ``emission_wavelength_in_nm``,
  ``numerical_aperture``) default to ``NaN``. The ndx spec forbids null here, so there is no honest
  numeric sentinel; ``NaN`` is used and flagged.
- Required **string** fields (``location``, an indicator ``label``, descriptions) default to the
  distinct sentinel ``"PLACEHOLDER"`` — distinct from a deliberate ``"unknown"`` so that intentionally
  declaring a field unknown silences the warning.

``add_to_nwbfile`` scans for surviving sentinels and emits a ``UserWarning`` naming each unfilled
field (or raises, under ``strict=True``). This lets an interface run end-to-end for a quick test while
nagging about anything that must be set before archiving.
