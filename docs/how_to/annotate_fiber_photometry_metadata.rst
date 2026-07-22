.. _annotate_fiber_photometry_metadata:

How to Annotate Fiber Photometry Metadata
=========================================

In general, neuroconv fills in as much metadata as we can extract from the source files. Most fiber
photometry acquisition formats store little beyond the fluorescence traces themselves, so a conversion
you run without adding any metadata writes just those traces, as a single
``FiberPhotometryResponseSeries``, and nothing that describes the nature of each channel:

.. code-block:: python

    from neuroconv.tools.testing import MockFiberPhotometryInterface

    interface = MockFiberPhotometryInterface(stream_names=("signal", "control"), channels_per_stream=1)
    nwbfile = interface.create_nwbfile()

.. admonition:: Resulting structure
   :class: tip

   .. code-block:: text

       acquisition
       └── FiberPhotometryResponseSeries    data (100, 2)     (two channels, nothing describing them)

By itself each channel is just a column of numbers. Nothing records which optical fiber it came from,
where in the brain, at what excitation wavelength, or which indicator it reports. That description is the
provenance you add.

Here we use `ndx-fiber-photometry <https://github.com/catalystneuro/ndx-fiber-photometry>`_, which stores
the metadata for each channel in a ``FiberPhotometryTable``: each channel of the
``FiberPhotometryResponseSeries`` links to one row of the table, and the row carries that channel's
provenance. Annotating a recording is building that table and pointing each channel at its row.

Each row has these columns:

.. list-table::
   :header-rows: 1
   :widths: 27 43 12 18

   * - Column
     - What it records
     - Required
     - Value or link
   * - ``location``
     - Brain region where the fiber sits
     - Yes
     - value
   * - ``excitation_wavelength_in_nm``
     - Excitation wavelength driving this channel
     - Yes
     - value
   * - ``emission_wavelength_in_nm``
     - Emission wavelength collected
     - Yes
     - value
   * - ``optical_fiber``
     - The implanted optical fiber
     - Yes
     - link to ``OpticalFiber``
   * - ``excitation_source``
     - The light source
     - Yes
     - link to ``ExcitationSource``
   * - ``photodetector``
     - The detector
     - Yes
     - link to ``Photodetector``
   * - ``indicator``
     - The fluorescent indicator
     - Yes
     - link to ``Indicator``
   * - ``coordinates``
     - Stereotactic coordinates (AP, ML, DV in mm)
     - No
     - value
   * - ``notes``
     - Free-text notes about the channel
     - No
     - value
   * - ``excitation_filter``
     - Filter on the excitation path
     - No
     - link to ``OpticalFilter``
   * - ``emission_filter``
     - Filter on the emission path
     - No
     - link to ``OpticalFilter``
   * - ``dichroic_mirror``
     - Dichroic mirror in the light path
     - No
     - link to ``DichroicMirror``
   * - ``commanded_voltage_series``
     - Commanded-voltage drive signal
     - No
     - link to ``CommandedVoltageSeries``

A value is stored on the row itself; a link points to a device or indicator defined elsewhere in the
metadata and can be shared across rows. This guide fills only the required columns.

The link, for a one-fiber signal + isosbestic recording, looks like this:

.. code-block:: text

    FiberPhotometryResponseSeries   (time × 2 channels)
       channel 0  ──▶  row "vta_465"
       channel 1  ──▶  row "vta_405"       via fiber_photometry_table_region

    FiberPhotometryTable
    row      location  exc/em   optical_fiber   excitation_source    photodetector      indicator
    ───────  ────────  ───────  ──────────────  ───────────────────  ─────────────────  ────────────────
    vta_465  VTA       465/525  links to fiber  links to source 465  links to detector  links to GCaMP6s
    vta_405  VTA       405/525  links to fiber  links to source 405  links to detector  links to GCaMP6s

..
   PLACEHOLDER FIGURE. This ASCII sketch is temporary. We aim to replace it with a polished, graphical
   illustration of the channel-to-row linkage. The full spec is in
   ``illustration_brief_fiber_photometry_table.md`` in the repo root; the agent producing the figure can
   ask questions to pin down the design before delivering the asset.


How to Annotate a Single Fiber and Channel
------------------------------------------

The simplest case is one fiber and one channel: one table row to fill in, and one series pointing at it.
We build it outward from the series: create the row and point the series at it, add the devices and
reference them from the row, add the models those devices use, then the indicator. Each device and the
indicator is referenced from the row at the step that defines it, and the file is written once at the end.

Start from the interface and its seeded metadata. Pass an explicit ``metadata_key`` to name the
response-series entry, which will be the key under ``metadata["FiberPhotometry"]`` where you write this
series' metadata:

.. code-block:: python

    from neuroconv.tools.testing import MockFiberPhotometryInterface

    metadata_key = "calcium_signal"
    interface = MockFiberPhotometryInterface(
        stream_names="signal", channels_per_stream=1, metadata_key=metadata_key
    )
    metadata = interface.get_metadata()
    fiber_photometry = metadata["FiberPhotometry"]

**Create the row and point the series at it.** A table row describes one fiber × one excitation channel.
Fill in the values it holds itself, its location and wavelengths, then point the series at the row
through ``fiber_photometry_table_region``. The device and indicator references get added as we define
those objects below:

.. code-block:: python

    row_key = "vta_465"
    fiber_photometry["FiberPhotometryTable"] = {
        "name": "fiber_photometry_table",
        "description": "One fiber, one channel.",
        "rows": {
            row_key: {
                "location": "VTA",
                "excitation_wavelength_in_nm": 470.0,
                "emission_wavelength_in_nm": 525.0,
            },
        },
    }
    fiber_photometry[metadata_key]["fiber_photometry_table_region"] = [row_key]
    fiber_photometry[metadata_key]["fiber_photometry_table_region_description"] = "VTA calcium signal."

``row_key`` does two different jobs here. As the key in the table's ``rows`` dict it **names the row**,
the row's data is stored under it. In ``fiber_photometry[metadata_key]["fiber_photometry_table_region"] =
[row_key]`` it is used as a **reference**: this is where the series is linked to the row, by pointing its
region at that key. Using the same variable for both guarantees the link lands on exactly the row we just
named.

..
   NOTE (maintainers): fiber_photometry_table_region_description is a required DynamicTableRegion field
   that neuroconv currently demands but should default at construction (like ecephys's hardcoded
   "electrode_table_region"), see Fix 2 in plan_fiber_photometry_device_model_optional.md. It is included
   here for now so the snippets run; remove it from every recipe once that PR merges.

.. admonition:: The file so far
   :class: note

   The series points at a one-row table, and the row holds the channel's own values: its location and the
   excitation and emission wavelengths.

   .. code-block:: text

       acquisition
       └── FiberPhotometryResponseSeries  ──▶  FiberPhotometryTable · row "vta_465"

       FiberPhotometryTable
       └── vta_465    location=VTA   excitation=470 nm   emission=525 nm

The file now describes where and at what wavelengths the channel was recorded, and the series is bound to
that row. The other half of *what* the channel measured is the sensor being read, the indicator, so we
name that next.

**Add the indicator and point the row at it.** The indicator is the fluorescent sensor the channel reads,
GCaMP6s here, a genetically encoded calcium indicator. It is biology expressed in the tissue, not
hardware, which is why it lives under ``FiberPhotometry`` rather than in the device registry. Define it,
then set the row's ``indicator_metadata_key`` to reference it:

.. code-block:: python

    indicator_key = "gcamp"
    fiber_photometry["FiberPhotometryIndicators"] = {indicator_key: {"name": "gcamp", "label": "GCaMP6s"}}
    fiber_photometry["FiberPhotometryTable"]["rows"][row_key]["indicator_metadata_key"] = indicator_key

.. admonition:: The file so far
   :class: note

   The indicator is defined, and the row now names it, recording what the channel's fluorescence reports.

   .. code-block:: text

       FiberPhotometryIndicators
       └── gcamp  ·  "GCaMP6s"

       FiberPhotometryTable · row "vta_465"
           └── indicator          → gcamp

That completes *what* the channel measured. Now we describe *how* it was measured: the hardware that read
the indicator, so a downstream analyst can trace each trace back to the exact fiber, light source, and
detector it came from.

**Add the devices and point the row at them.** A device is the specific physical unit used in this
recording, and it holds the facts about that unit as it was used here. The clearest example is the optical
fiber's ``fiber_insertion``: where in the brain it was implanted, its stereotactic coordinates and depth.
That is often the most experimentally important metadata in the whole chain, it is what lets a downstream
analyst say which brain region each channel reports. An excitation source can carry the power and
intensity it was driven at, and a photodetector its gain, the per-recording configuration a reader needs
to interpret or reproduce the measurement. Define the three devices in the top-level ``Devices`` registry,
then set the row's reference keys to point at them:

.. code-block:: python

    optical_fiber_key = "optical_fiber"
    excitation_source_key = "excitation_source_465"
    photodetector_key = "photodetector"
    metadata["Devices"] = {
        optical_fiber_key: {"type": "OpticalFiber", "name": "optical_fiber",
                            "fiber_insertion": {"depth_in_mm": 4.0, "insertion_position_ap_in_mm": 3.0}},
        excitation_source_key: {"type": "ExcitationSource", "name": "excitation_source_465"},
        photodetector_key: {"type": "Photodetector", "name": "photodetector"},
    }

    row = fiber_photometry["FiberPhotometryTable"]["rows"][row_key]
    row["optical_fiber_metadata_key"] = optical_fiber_key
    row["excitation_source_metadata_key"] = excitation_source_key
    row["photodetector_metadata_key"] = photodetector_key

.. admonition:: The file so far
   :class: note

   The row now resolves to the three physical devices that recorded the channel.

   .. code-block:: text

       Devices
       ├── optical_fiber
       ├── excitation_source_465
       └── photodetector

       FiberPhotometryTable · row "vta_465"
           ├── optical_fiber      → optical_fiber
           ├── excitation_source  → excitation_source_465
           └── photodetector      → photodetector

The devices say which units were used and how, but not their specifications. Those, the fiber's numerical
aperture, the kind of light source, the detector type, are the same across every recording that used the
same equipment, so they belong in a shared device model rather than being repeated on each device. We add
the models next and attach one to each device.

**Add the device models and attach them.** Each model in the top-level ``DeviceModels`` registry carries
the make and specifications of a piece of hardware; the ``type`` field names its concrete
ndx-ophys-devices class. Define the models, then point each device at its model:

.. code-block:: python

    optical_fiber_model_key = "optical_fiber_model"
    excitation_source_model_key = "excitation_source_model"
    photodetector_model_key = "photodetector_model"
    metadata["DeviceModels"] = {
        optical_fiber_model_key: {"type": "OpticalFiberModel", "name": "optical_fiber_model",
                                  "manufacturer": "Doric Lenses", "numerical_aperture": 0.48},
        excitation_source_model_key: {"type": "ExcitationSourceModel", "name": "excitation_source_model",
                                      "manufacturer": "Doric Lenses", "source_type": "LED", "excitation_mode": "one-photon"},
        photodetector_model_key: {"type": "PhotodetectorModel", "name": "photodetector_model",
                                  "manufacturer": "Doric Lenses", "detector_type": "photodiode"},
    }
    metadata["Devices"][optical_fiber_key]["device_model_metadata_key"] = optical_fiber_model_key
    metadata["Devices"][excitation_source_key]["device_model_metadata_key"] = excitation_source_model_key
    metadata["Devices"][photodetector_key]["device_model_metadata_key"] = photodetector_model_key

.. admonition:: The file so far
   :class: note

   Each device now points at a model describing its make and specifications.

   .. code-block:: text

       DeviceModels
       ├── optical_fiber_model       ◀── optical_fiber
       ├── excitation_source_model   ◀── excitation_source_465
       └── photodetector_model       ◀── photodetector

**Write the file.** With every referenced key now defined, convert:

.. code-block:: python

    nwbfile = interface.create_nwbfile(metadata=metadata)

.. admonition:: Resulting structure
   :class: tip

   .. code-block:: text

       acquisition
       └── FiberPhotometryResponseSeries    data (100,)   ──▶   FiberPhotometryTable · row "vta_465"

       FiberPhotometryTable   (1 row)
       └── vta_465    location=VTA   excitation=470 nm   emission=525 nm
           ├── optical_fiber      → optical_fiber           (model: optical_fiber_model)
           ├── excitation_source  → excitation_source_465   (model: excitation_source_model)
           ├── photodetector      → photodetector           (model: photodetector_model)
           └── indicator          → gcamp  ·  "GCaMP6s"

Each ``*_metadata_key`` in the row is resolved to the actual NWB object at write time, so you name each
fiber, source, detector, and indicator once in its own block and reference it by key from the row.


How to Annotate a Signal and Isosbestic Control
-----------------------------------------------

The near-universal GCaMP setup records one fiber at two excitation wavelengths, the calcium-dependent
signal (465 nm) and an isosbestic control (405 nm), as the two channels of one series. Use two streams,
add a second excitation source, give the table **two rows** (one per channel), and list **both** row
keys in the region. The region order must match the channel (stream) order.

.. code-block:: python

    metadata_key = "gcamp_vta"
    interface = MockFiberPhotometryInterface(
        stream_names=("signal", "control"), channels_per_stream=1, metadata_key=metadata_key
    )
    metadata = interface.get_metadata()

    # The metadata keys that wire the blocks together. Each is used both where its object is defined and
    # where another block references it, so the linking is explicit rather than matched by eye.
    optical_fiber_model_key = "optical_fiber_model"
    excitation_source_model_key = "excitation_source_model"
    photodetector_model_key = "photodetector_model"
    optical_fiber_key = "optical_fiber"
    signal_source_key = "excitation_source_465"
    control_source_key = "excitation_source_405"
    photodetector_key = "photodetector"
    indicator_key = "gcamp"
    signal_row_key = "vta_465"
    control_row_key = "vta_405"

    metadata["DeviceModels"] = {
        optical_fiber_model_key: {"type": "OpticalFiberModel", "name": "optical_fiber_model",
                                  "manufacturer": "Doric Lenses", "numerical_aperture": 0.48},
        excitation_source_model_key: {"type": "ExcitationSourceModel", "name": "excitation_source_model",
                                      "manufacturer": "Doric Lenses", "source_type": "LED", "excitation_mode": "one-photon"},
        photodetector_model_key: {"type": "PhotodetectorModel", "name": "photodetector_model",
                                  "manufacturer": "Doric Lenses", "detector_type": "photodiode"},
    }
    # One fiber and one detector, but two excitation sources: the 465 nm signal and the 405 nm isosbestic.
    metadata["Devices"] = {
        optical_fiber_key: {"type": "OpticalFiber", "name": "optical_fiber",
                            "device_model_metadata_key": optical_fiber_model_key,
                            "fiber_insertion": {"depth_in_mm": 4.0, "insertion_position_ap_in_mm": 3.0}},
        signal_source_key: {"type": "ExcitationSource", "name": "excitation_source_465",
                            "device_model_metadata_key": excitation_source_model_key},
        control_source_key: {"type": "ExcitationSource", "name": "excitation_source_405",
                             "device_model_metadata_key": excitation_source_model_key},
        photodetector_key: {"type": "Photodetector", "name": "photodetector",
                            "device_model_metadata_key": photodetector_model_key},
    }

    fiber_photometry = metadata["FiberPhotometry"]
    fiber_photometry["FiberPhotometryIndicators"] = {indicator_key: {"name": "gcamp", "label": "GCaMP6s"}}
    fiber_photometry["FiberPhotometryTable"] = {
        "name": "fiber_photometry_table",
        "description": "One fiber, signal + isosbestic control.",
        "rows": {
            signal_row_key: {"location": "VTA", "excitation_wavelength_in_nm": 465.0, "emission_wavelength_in_nm": 525.0,
                             "indicator_metadata_key": indicator_key, "optical_fiber_metadata_key": optical_fiber_key,
                             "excitation_source_metadata_key": signal_source_key,
                             "photodetector_metadata_key": photodetector_key},
            control_row_key: {"location": "VTA", "excitation_wavelength_in_nm": 405.0, "emission_wavelength_in_nm": 525.0,
                              "indicator_metadata_key": indicator_key, "optical_fiber_metadata_key": optical_fiber_key,
                              "excitation_source_metadata_key": control_source_key,
                              "photodetector_metadata_key": photodetector_key},
        },
    }
    fiber_photometry[metadata_key]["description"] = "GCaMP6s signal and isosbestic control in VTA."
    # Region order matches channel (stream) order: signal -> vta_465, control -> vta_405.
    fiber_photometry[metadata_key]["fiber_photometry_table_region"] = [signal_row_key, control_row_key]
    fiber_photometry[metadata_key]["fiber_photometry_table_region_description"] = "Signal (465) and isosbestic (405)."

    nwbfile = interface.create_nwbfile(metadata=metadata)

Two channels, so two rows, and the ``fiber_photometry_table_region`` list ``["vta_465", "vta_405"]`` maps
them in order: channel 0 (the 465 nm signal) to ``vta_465``, channel 1 (the 405 nm isosbestic control) to
``vta_405``. The two rows reference the *same* ``optical_fiber``, ``photodetector``, and ``indicator``,
one fiber, one detector, one GCaMP6s, and differ only in their ``excitation_source`` and
``excitation_wavelength_in_nm``. That is exactly what the isosbestic setup is: one measurement site read at
two excitation wavelengths, so everything shared is referenced from both rows and only the
wavelength-specific piece is distinct.

.. admonition:: Resulting structure
   :class: tip

   .. code-block:: text

       acquisition
       └── FiberPhotometryResponseSeries    data (100, 2)   ──▶   FiberPhotometryTable · rows [vta_465, vta_405]

       FiberPhotometryTable   (2 rows)
       ├── vta_465    excitation=465 nm    src → excitation_source_465     (channel 0, the signal)
       └── vta_405    excitation=405 nm    src → excitation_source_405     (channel 1, the isosbestic control)


How to Annotate Multiple Fibers in Different Locations
------------------------------------------------------

The previous section multiplied the table rows along the *excitation-wavelength* axis: one fiber, two
wavelengths. This section multiplies them along the *spatial* axis instead: two physically separate
fibers in two regions (here DMS, the dorsomedial striatum, and DLS, the dorsolateral striatum), each
measuring the same indicator at the same wavelength. Each fiber gets its own ``OpticalFiber`` instance
and its own table row, so the rows now differ in ``optical_fiber`` and ``location`` where the
signal/isosbestic rows differed in ``excitation_wavelength``. Sharing a timebase, the two fibers are the
channels of one series whose region lists both rows.

.. code-block:: python

    metadata_key = "gcamp_striatum"
    interface = MockFiberPhotometryInterface(
        stream_names=("dms", "dls"), channels_per_stream=1, metadata_key=metadata_key
    )
    metadata = interface.get_metadata()

    # The metadata keys that wire the blocks together.
    optical_fiber_model_key = "optical_fiber_model"
    excitation_source_model_key = "excitation_source_model"
    photodetector_model_key = "photodetector_model"
    dms_fiber_key = "optical_fiber_dms"
    dls_fiber_key = "optical_fiber_dls"
    excitation_source_key = "excitation_source_465"
    photodetector_key = "photodetector"
    indicator_key = "gcamp"
    dms_row_key = "dms_465"
    dls_row_key = "dls_465"

    metadata["DeviceModels"] = {
        optical_fiber_model_key: {"type": "OpticalFiberModel", "name": "optical_fiber_model",
                                  "manufacturer": "Doric Lenses", "numerical_aperture": 0.48},
        excitation_source_model_key: {"type": "ExcitationSourceModel", "name": "excitation_source_model",
                                      "manufacturer": "Doric Lenses", "source_type": "LED", "excitation_mode": "one-photon"},
        photodetector_model_key: {"type": "PhotodetectorModel", "name": "photodetector_model",
                                  "manufacturer": "Doric Lenses", "detector_type": "photodiode"},
    }
    # Two optical fibers, one per region; a shared excitation source and detector.
    metadata["Devices"] = {
        dms_fiber_key: {"type": "OpticalFiber", "name": "optical_fiber_dms",
                        "device_model_metadata_key": optical_fiber_model_key,
                        "fiber_insertion": {"depth_in_mm": 4.2, "insertion_position_ap_in_mm": 0.8}},
        dls_fiber_key: {"type": "OpticalFiber", "name": "optical_fiber_dls",
                        "device_model_metadata_key": optical_fiber_model_key,
                        "fiber_insertion": {"depth_in_mm": 4.0, "insertion_position_ap_in_mm": 0.5}},
        excitation_source_key: {"type": "ExcitationSource", "name": "excitation_source_465",
                                "device_model_metadata_key": excitation_source_model_key},
        photodetector_key: {"type": "Photodetector", "name": "photodetector",
                            "device_model_metadata_key": photodetector_model_key},
    }

    fiber_photometry = metadata["FiberPhotometry"]
    fiber_photometry["FiberPhotometryIndicators"] = {indicator_key: {"name": "gcamp", "label": "GCaMP6s"}}
    fiber_photometry["FiberPhotometryTable"] = {
        "name": "fiber_photometry_table",
        "description": "Two fibers in two regions.",
        "rows": {
            dms_row_key: {"location": "DMS", "excitation_wavelength_in_nm": 465.0, "emission_wavelength_in_nm": 525.0,
                          "indicator_metadata_key": indicator_key, "optical_fiber_metadata_key": dms_fiber_key,
                          "excitation_source_metadata_key": excitation_source_key,
                          "photodetector_metadata_key": photodetector_key},
            dls_row_key: {"location": "DLS", "excitation_wavelength_in_nm": 465.0, "emission_wavelength_in_nm": 525.0,
                          "indicator_metadata_key": indicator_key, "optical_fiber_metadata_key": dls_fiber_key,
                          "excitation_source_metadata_key": excitation_source_key,
                          "photodetector_metadata_key": photodetector_key},
        },
    }
    fiber_photometry[metadata_key]["description"] = "GCaMP6s in DMS and DLS."
    fiber_photometry[metadata_key]["fiber_photometry_table_region"] = [dms_row_key, dls_row_key]
    fiber_photometry[metadata_key]["fiber_photometry_table_region_description"] = "DMS and DLS fibers."

    nwbfile = interface.create_nwbfile(metadata=metadata)

Two fibers, so two rows, and the ``fiber_photometry_table_region`` list ``["dms_465", "dls_465"]`` maps the
channels in order: channel 0 (the DMS fiber) to ``dms_465``, channel 1 (the DLS fiber) to ``dls_465``.
This time the rows reference *different* ``optical_fiber`` objects (``optical_fiber_dms`` vs
``optical_fiber_dls``) and differ in ``location``, while sharing the same ``excitation_source``,
``photodetector``, and ``indicator``. That is the mirror image of the signal/isosbestic case: there the
rows shared the fiber and varied the wavelength; here they share the wavelength and vary the fiber, and in
both the row's ``*_metadata_key`` fields are what wire each channel to the objects it should point at.

.. admonition:: Resulting structure
   :class: tip

   .. code-block:: text

       FiberPhotometryTable   (2 rows)
       ├── dms_465    location=DMS    fiber → optical_fiber_dms
       └── dls_465    location=DLS    fiber → optical_fiber_dls

The table now has one row per fiber, and rows scale with fibers, not with wavelengths. Real setups
usually combine both axes: N fibers each recorded at a signal and an isosbestic wavelength give 2N rows,
one per (fiber, wavelength) channel.
