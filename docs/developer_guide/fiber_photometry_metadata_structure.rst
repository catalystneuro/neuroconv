.. _fiber_photometry_metadata_structure:

Fiber Photometry Metadata Structure
===================================

This document describes the fiber photometry metadata system in NeuroConv, used by the single-series
fiber photometry interfaces (TDT, Doric, and others) built on ``BaseFiberPhotometryInterface``. It is
intended as a reference for developers contributing new fiber photometry interfaces or modifying
existing ones, and to document the design decisions behind the format.

A single-series interface writes exactly one ``FiberPhotometryResponseSeries`` (the ndx-fiber-photometry
neurodata type), assembled from one or more input *streams* (atomic source signals — a TDT store, a
Doric dataset). That response series references rows of a shared ``FiberPhotometryTable``, and each
row references the physical hardware (optical fiber, excitation source, photodetector, filters) and
the indicator that produced the trace. Because a recording usually contains several response series
(a calcium signal and an isosbestic control per fiber, across several fibers), a conversion typically
runs several interfaces together, all contributing to one shared table — exactly like several ecephys
recording interfaces sharing one electrodes table. The purpose of the fiber photometry metadata dict
is to describe that shared hardware once and let each interface point its response series at the rows
it needs.


Design Principles
-----------------

The fiber photometry metadata system follows the same spirit as the ophys and ecephys systems (see
:ref:`ophys_metadata_structure`), specialized to the ndx-fiber-photometry data model:

1. **Its own top-level block.** All fiber photometry metadata lives under ``metadata["FiberPhotometry"]``,
   not nested under ``metadata["Ophys"]``. Fiber photometry is technically an optical method, but — like
   the ecephys/icephys split — it has its own interfaces, its own extension, and its own metadata block.

   .. code-block:: python

       metadata["FiberPhotometry"]["FiberPhotometryIndicators"][0]["label"] = "GCaMP7b"

2. **Shared containers are name-keyed lists; the response series is keyed by ``metadata_key``.**
   The hardware and biology shared across an entire file (device models, devices, optical fibers,
   indicators, viral vectors and injections, commanded voltage, and the table itself) are stored as
   **lists of named entries**. Each interface's own response series is stored under its
   ``metadata_key`` (a dict entry). The shared lists are merged across interfaces by
   ``dict_deep_update`` (which deduplicates list entries by their ``"name"``), so declaring the same
   optical fiber in two interfaces collapses to one entry, exactly as ecephys does for
   ``metadata["Ecephys"]["Device"]``.

3. **Linking is by name, resolved at write time.** Entries reference each other with plain
   ``"name"`` strings — a device names its model, a table row names its optical fiber and indicator,
   and a response series names the table rows it spans. There are no ``_metadata_key`` indirection
   fields as in the ophys system; the ndx-fiber-photometry objects have names, so metadata references
   them by name directly. Table-row references in particular are resolved to integer row indices at
   write time, mirroring how ecephys resolves electrode regions by ``channel_name``.

4. **One shared, row-indexed table.** A file has a single ``FiberPhotometryTable``. Every response
   series references a *region* of its rows. Rows must carry a ``name`` so regions can be specified by
   name rather than fragile integer indices.

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

            # ----- Shared, name-keyed lists (built once per file, deduped by "name") -----

            # Device models (paired with device instances below)
            "OpticalFiberModels": [
                {"name": "optical_fiber_model", "manufacturer": "Doric Lenses", "numerical_aperture": 0.48},
            ],
            "ExcitationSourceModels": [
                {"name": "excitation_source_model", "manufacturer": "Doric Lenses",
                 "source_type": "LED", "excitation_mode": "one-photon"},
            ],
            "PhotodetectorModels": [
                {"name": "photodetector_model", "manufacturer": "Doric Lenses", "detector_type": "photodiode"},
            ],
            # (also BandOpticalFilterModels, EdgeOpticalFilterModels, DichroicMirrorModels)

            # Device instances (each references its model by name)
            "OpticalFibers": [
                {"name": "optical_fiber_dms", "model": "optical_fiber_model",
                 "fiber_insertion": {"depth_in_mm": 4.2, "insertion_position_ap_in_mm": 0.8}},
            ],
            "ExcitationSources": [
                {"name": "excitation_source_465", "model": "excitation_source_model"},
            ],
            "Photodetectors": [
                {"name": "photodetector", "model": "photodetector_model"},
            ],
            # (also BandOpticalFilters, EdgeOpticalFilters, DichroicMirrors)

            # Indicators, and optionally the viruses/injections that delivered them
            "FiberPhotometryViruses": [
                {"name": "aav_gcamp", "construct_name": "AAV-GCaMP7b"},
            ],
            "FiberPhotometryVirusInjections": [
                {"name": "injection_dms", "viral_vector": "aav_gcamp"},   # references a virus by name
            ],
            "FiberPhotometryIndicators": [
                {"name": "gcamp", "label": "GCaMP7b",
                 "viral_vector_injection": "injection_dms"},              # references an injection by name
            ],

            # Optional commanded-voltage drive signals (data-bearing; read from a stream)
            "CommandedVoltageSeries": [
                {"name": "commanded_voltage_dms", "stream_name": "Fi1r", "index": 0,
                 "unit": "volts", "frequency": 211.0},
            ],

            # The single shared table. Each row = one fiber x one excitation channel.
            "FiberPhotometryTable": {
                "name": "fiber_photometry_table",
                "description": "Fiber photometry setup.",
                "rows": [
                    {
                        "name": "dms_465",                        # row name (referenced by regions)
                        "location": "DMS",
                        "excitation_wavelength_in_nm": 465.0,
                        "emission_wavelength_in_nm": 520.0,
                        "indicator": "gcamp",                     # references an indicator by name
                        "optical_fiber": "optical_fiber_dms",     # references a device by name
                        "excitation_source": "excitation_source_465",
                        "photodetector": "photodetector",
                        "commanded_voltage_series": "commanded_voltage_dms",  # optional
                    },
                ],
            },

            # ----- Per-interface response series, keyed by metadata_key -----
            "gcamp_dms": {
                "name": "FiberPhotometryResponseSeries",
                "description": "GCaMP7b calcium signal in DMS.",
                "unit": "a.u.",
                "fiber_photometry_table_region": ["dms_465"],     # list of ROW NAMES
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

``metadata_key`` scopes only this interface's **response series** entry. It does *not* scope the shared
containers: devices, indicators, and table rows live in the shared lists and are named independently,
so several interfaces reference the same optical fiber or table row by name regardless of their keys.
This split is deliberate — the response series is the interface's own output (one per interface),
while the hardware is shared file-wide.

Note that the response series' NWB ``name`` (``"FiberPhotometryResponseSeries"`` by default) is
distinct from its ``metadata_key``. The key identifies the interface's entry; the ``name`` names the
object written to the file. Combine multiple interfaces in a converter and give each a distinct
``metadata_key`` (and typically a distinct series ``name``) to write several series into one file.


Shared Containers and Name-Based Linking
----------------------------------------

Unlike the ophys system's ``_metadata_key`` indirection, fiber photometry entries reference each
other with plain ``"name"`` strings, because the underlying ndx-fiber-photometry / ndx-ophys-devices
objects are themselves named and referenced by name. The reference chain is:

- A **device instance** names its **model**: ``"model": "optical_fiber_model"``.
- A **virus injection** names its **viral vector**: ``"viral_vector": "aav_gcamp"``.
- An **indicator** optionally names its **injection**: ``"viral_vector_injection": "injection_dms"``.
- A **table row** names its **devices and indicator**: ``"optical_fiber"``, ``"excitation_source"``,
  ``"photodetector"``, ``"indicator"``, and optionally ``"dichroic_mirror"``,
  ``"excitation_filter"``, ``"emission_filter"``, and ``"commanded_voltage_series"``.
- A **response series** names the **table rows** it spans:
  ``"fiber_photometry_table_region": ["dms_465", "dms_405"]``.

The device models and instances come in pairs (``OpticalFiberModels`` / ``OpticalFibers``,
``ExcitationSourceModels`` / ``ExcitationSources``, and so on). Optical fibers are the one special
case: each carries a nested ``fiber_insertion`` block (stereotaxic coordinates and insertion
geometry), which is a *contained* component specified inline rather than a separately-named object.


The FiberPhotometryTable and Regions
------------------------------------

A file has exactly one ``FiberPhotometryTable``. Each row describes one fiber × one excitation channel
— its brain ``location``, its excitation/emission wavelengths, the indicator, and the hardware that
recorded it. A multi-fiber, dual-wavelength setup therefore has several rows (e.g. ``dms_465``,
``dms_405``, ``dls_465``, ``dls_405``).

Each ``FiberPhotometryResponseSeries`` references a **region** of the table — the subset of rows whose
channels make up that series' data columns — via ``fiber_photometry_table_region``, a list of **row
names**. At write time these names are resolved to integer row indices (their position in the merged
``rows`` list), so the region ordering matches the data's channel ordering and no interface needs to
know the absolute index a row landed at. Referencing a row name that is not present in the table is a
loud error. This name-based resolution is what makes multi-interface conversions tractable: interface
B can point its region at rows that interface A contributed, purely by name.


Object Creation and Idempotency
-------------------------------

Like the ophys system, objects are not created when the metadata dict is assembled — they are created
during ``add_to_nwbfile``. Because several interfaces share one table and one set of devices, the
shared containers are built **once per file**:

1. The device/indicator/table helpers are idempotent by name. The first interface to run assembles the
   whole ``FiberPhotometry`` lab-metadata (devices, indicators, viruses, injections, and every table
   row) from the merged metadata; subsequent interfaces find it already present and reuse it, then add
   only their own response series.

2. Because the metadata is merged across interfaces before writing (by the converter's
   ``dict_deep_update``), every interface sees the full set of shared rows and devices, so whichever
   runs first can build the complete table.

3. Declaring the same-named shared object with *different* contents in two interfaces is a loud error
   rather than a silent merge, so an authoring mistake surfaces immediately.

Commanded voltage is a special case among the shared containers: it is data-bearing (it reads samples
from a stream, not just static metadata). Each ``CommandedVoltageSeries`` entry names the input
``stream_name`` (and optional channel ``index``) to read; a table row then references the resulting
series by name through its ``commanded_voltage_series`` field. This is how frequency-multiplexed
setups associate each demodulated signal with the sinusoidal drive that produced it.


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


Relationship to the Deprecated Multi-Series Format
--------------------------------------------------

The original ``TDTFiberPhotometryInterface`` wrote *every* stream at once as multiple response series
from a single interface. That behavior is deprecated (reachable by constructing without
``stream_names``) and retains the previous metadata format: nested under
``metadata["Ophys"]["FiberPhotometry"]`` with response series given as a list and table regions given
as integer indices. New interfaces should use the single-series format described here — top-level
``metadata["FiberPhotometry"]``, one response series per interface under its ``metadata_key``, and
regions given by row name.
