.. _annotate_fiber_photometry_metadata:

How to Annotate Fiber Photometry Data
=====================================

This guide provides instructions for annotating fiber photometry data using NeuroConv.

Fiber photometry metadata in NWB files describes the equipment and preparation behind each recorded channel:
the **device models** and **device instances** (optical fiber, excitation source(s), photodetector), the
**indicator**, and a ``FiberPhotometryTable`` whose rows tie each channel to the hardware and indicator that
produced it. The recorded signal itself is written as a ``FiberPhotometryResponseSeries``.

A fiber photometry interface populates whatever it can read from your files — the signal traces, and often
the session start time — but the rest of the metadata (the optical hardware, indicator, and table) usually
needs to be provided by you. There are several ways to assemble it; this guide uses a convenient one: start
from ``get_example_metadata()``, which returns a complete, realistic template, and edit the fields to match
your experiment.


Start From a Complete Example
-----------------------------

``get_example_metadata()`` returns a fully specified metadata dictionary with realistic example values.
The example describes a common two-channel setup — a calcium-dependent signal and an isosbestic control —
so construct the interface with one stream per channel.

.. code-block:: python

    import yaml

    from neuroconv.datainterfaces import DoricFiberPhotometryInterface

    interface = DoricFiberPhotometryInterface(
        file_path="path/to/fiber_photometry_data.doric",
        stream_names=["signal", "isosbestic"],  # one stream per recorded channel
    )

    # A complete, editable template with realistic values (not read from your file).
    metadata = interface.get_example_metadata()

    # Inspect the fiber photometry structure. The interface also fills standard NWBFile fields (omitted here).
    fiber_photometry_structure = {key: metadata[key] for key in ("DeviceModels", "Devices", "FiberPhotometry")}
    print(yaml.dump(fiber_photometry_structure, sort_keys=False))

This prints the full structure you will edit:

.. code-block:: yaml

    DeviceModels:
      optical_fiber_model:
        type: OpticalFiberModel
        name: optical_fiber_model
        manufacturer: Doric Lenses
        numerical_aperture: 0.48
      excitation_source_model:
        type: ExcitationSourceModel
        name: excitation_source_model
        manufacturer: Doric Lenses
        source_type: LED
        excitation_mode: one-photon
      photodetector_model:
        type: PhotodetectorModel
        name: photodetector_model
        manufacturer: Doric Lenses
        detector_type: photodiode
    Devices:
      optical_fiber:
        type: OpticalFiber
        name: optical_fiber
        device_model_metadata_key: optical_fiber_model
        fiber_insertion:
          depth_in_mm: 4.0
          insertion_position_ap_in_mm: 3.0
      excitation_source_calcium_signal:
        type: ExcitationSource
        name: excitation_source_calcium_signal
        device_model_metadata_key: excitation_source_model
      excitation_source_isosbestic_control:
        type: ExcitationSource
        name: excitation_source_isosbestic_control
        device_model_metadata_key: excitation_source_model
      photodetector:
        type: Photodetector
        name: photodetector
        device_model_metadata_key: photodetector_model
    FiberPhotometry:
      fiber_photometry_signal_isosbestic:
        name: FiberPhotometryResponseSeries
        description: Fiber photometry response series.
        unit: a.u.
        fiber_photometry_table_region:
        - calcium_signal
        - isosbestic_control
        fiber_photometry_table_region_description: The calcium-dependent signal and isosbestic
          control channels recorded from the optical fiber.
      FiberPhotometryIndicators:
        indicator:
          name: indicator
          label: GCaMP6s
      FiberPhotometryTable:
        name: fiber_photometry_table
        description: Each row describes a single fiber photometry channel, linking it
          to the optical fiber, excitation source, photodetector, and indicator used to
          acquire it.
        rows:
          calcium_signal:
            location: VTA
            excitation_wavelength_in_nm: 470.0
            emission_wavelength_in_nm: 525.0
            indicator_metadata_key: indicator
            optical_fiber_metadata_key: optical_fiber
            excitation_source_metadata_key: excitation_source_calcium_signal
            photodetector_metadata_key: photodetector
          isosbestic_control:
            location: VTA
            excitation_wavelength_in_nm: 405.0
            emission_wavelength_in_nm: 525.0
            indicator_metadata_key: indicator
            optical_fiber_metadata_key: optical_fiber
            excitation_source_metadata_key: excitation_source_isosbestic_control
            photodetector_metadata_key: photodetector

The pieces reference each other by key, which you can see in the structure above. ``DeviceModels`` and
``Devices`` are top-level registries: each device names its model through ``device_model_metadata_key``. Under
``FiberPhotometry``, the ``FiberPhotometryTable`` has one entry in ``rows`` per recorded channel, and each row
points at the hardware and indicator that produced it through the ``*_metadata_key`` fields
(``optical_fiber_metadata_key``, ``excitation_source_metadata_key``, ``photodetector_metadata_key``,
``indicator_metadata_key``). The response series entry — keyed by ``interface.metadata_key`` (here
``fiber_photometry_signal_isosbestic``, derived from the stream names) — points at its rows through
``fiber_photometry_table_region``. Because everything is referenced by key, you edit each item in exactly one
place: changing ``metadata["Devices"]["optical_fiber"]`` updates every row that names ``optical_fiber``.


Edit the Metadata
-----------------

Overwrite the template values with the real details of your experiment.

.. code-block:: python

    # Device models: the make and specifications of each device.
    metadata["DeviceModels"]["optical_fiber_model"]["manufacturer"] = "Doric Lenses"
    metadata["DeviceModels"]["optical_fiber_model"]["numerical_aperture"] = 0.48
    metadata["DeviceModels"]["photodetector_model"]["detector_type"] = "photodiode"

    # Device instances: where the optical fiber was implanted.
    fiber_insertion = metadata["Devices"]["optical_fiber"]["fiber_insertion"]
    fiber_insertion["depth_in_mm"] = 4.2
    fiber_insertion["insertion_position_ap_in_mm"] = 3.1

    # Indicator.
    metadata["FiberPhotometry"]["FiberPhotometryIndicators"]["indicator"]["label"] = "GCaMP7b"

    # Table rows: the location and wavelengths of each recorded channel.
    rows = metadata["FiberPhotometry"]["FiberPhotometryTable"]["rows"]
    rows["calcium_signal"]["location"] = "VTA"
    rows["calcium_signal"]["excitation_wavelength_in_nm"] = 465.0
    rows["calcium_signal"]["emission_wavelength_in_nm"] = 525.0
    rows["isosbestic_control"]["location"] = "VTA"
    rows["isosbestic_control"]["excitation_wavelength_in_nm"] = 405.0
    rows["isosbestic_control"]["emission_wavelength_in_nm"] = 525.0

    # The response series written by this interface.
    series_metadata = metadata["FiberPhotometry"][interface.metadata_key]
    series_metadata["name"] = "FiberPhotometryResponseSeries"
    series_metadata["description"] = "Dopamine signal recorded from VTA terminals."

.. note::

    The keys are references, so if you rename a device you must update both places: the entry under
    ``metadata["Devices"]`` **and** the ``*_metadata_key`` in every row that points to it. For example,
    renaming ``"optical_fiber"`` means changing that key in ``metadata["Devices"]`` and setting each row's
    ``optical_fiber_metadata_key`` to the new name.


Add Optional Fields
-------------------

The example fills in the required and most common fields, but the ``ndx-fiber-photometry`` and
``ndx-ophys-devices`` specifications define many more optional ones. Add any of them the same way you edit an
existing value — by setting a new key on the relevant entry.

.. code-block:: python

    # Device models and device instances accept additional descriptive fields.
    metadata["DeviceModels"]["optical_fiber_model"]["model_number"] = "Fiber Optic Implant"
    metadata["DeviceModels"]["optical_fiber_model"]["core_diameter_in_um"] = 400.0
    metadata["DeviceModels"]["photodetector_model"]["gain"] = 1.0e10
    metadata["DeviceModels"]["photodetector_model"]["gain_unit"] = "V/W"
    metadata["Devices"]["optical_fiber"]["serial_number"] = "OF-001"

    # So do indicators, table rows, and every other entry.
    indicators = metadata["FiberPhotometry"]["FiberPhotometryIndicators"]
    indicators["indicator"]["description"] = "Calcium indicator expressed in VTA."

    # A table row can record the fiber's stereotactic coordinates (AP, ML, DV in mm). A table column
    # must be present on every row, so add an optional row field to all of them.
    rows["calcium_signal"]["coordinates"] = (3.0, 1.3, -4.2)
    rows["isosbestic_control"]["coordinates"] = (3.0, 1.3, -4.2)


Run the Conversion
------------------

Pass the edited metadata to the conversion.

.. code-block:: python

    interface.run_conversion(
        nwbfile_path="fiber_photometry.nwb",
        metadata=metadata,
    )
