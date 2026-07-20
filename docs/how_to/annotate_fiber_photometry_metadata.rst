.. _annotate_fiber_photometry_metadata:

How to Annotate Fiber Photometry Data
=====================================

This guide provides instructions for annotating fiber photometry data using NeuroConv.

Fiber photometry metadata in NWB files describes the equipment and preparation behind each recorded channel:
the **device models** and **device instances** (optical fiber, excitation source(s), photodetector), the
**indicator**, and a ``FiberPhotometryTable`` whose rows tie each channel to the hardware and indicator that
produced it. The recorded signal itself is written as a ``FiberPhotometryResponseSeries``.

A fiber photometry interface reads the signal traces (and, where available, the session start time) from your
files, but it cannot read the optical hardware, indicator, or table — none of that is embedded in the data.
You supply it. Rather than build the whole structure by hand, start from ``get_example_metadata()``, which
returns a complete, realistic template, and edit the fields to match your experiment.


Start From a Complete Example
-----------------------------

``get_example_metadata()`` returns a fully specified metadata dictionary with realistic placeholder values.
The example describes a common two-channel setup — a calcium-dependent signal and an isosbestic control —
so construct the interface with one stream per channel.

.. code-block:: python

    from neuroconv.datainterfaces import DoricFiberPhotometryInterface

    interface = DoricFiberPhotometryInterface(
        file_path="path/to/fiber_photometry_data.doric",
        stream_names=["signal", "isosbestic"],  # one stream per recorded channel
    )

    # A complete, editable template with realistic values (not read from your file).
    metadata = interface.get_example_metadata()

    # The template is organized into a few linked pieces:
    # - metadata["DeviceModels"]            -> the model/specifications of each device
    # - metadata["Devices"]                 -> the physical device instances, each linked to a model
    # - metadata["FiberPhotometry"]["FiberPhotometryIndicators"] -> the indicator(s)
    # - metadata["FiberPhotometry"]["FiberPhotometryTable"]["rows"] -> one row per recorded channel
    # - metadata["FiberPhotometry"][interface.metadata_key]        -> this interface's response series

The pieces reference each other by key. Each ``FiberPhotometryTable`` row points at the hardware and indicator
that produced it through ``*_metadata_key`` fields (``optical_fiber_metadata_key``,
``excitation_source_metadata_key``, ``photodetector_metadata_key``, ``indicator_metadata_key``), each device
points at its model through ``device_model_metadata_key``, and the response series points at its rows through
``fiber_photometry_table_region``. Because of this wiring, you edit each thing in exactly one place: changing
``metadata["Devices"]["optical_fiber"]`` updates every row that names ``optical_fiber``.


Edit the Metadata
-----------------

Overwrite the template values with the real details of your experiment. Only edit the values — leave the keys
in place, since they are what wire the pieces together.

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


Run the Conversion
------------------

Pass the edited metadata to the conversion.

.. code-block:: python

    interface.run_conversion(
        nwbfile_path="fiber_photometry.nwb",
        metadata=metadata,
    )

To build the NWB file in memory instead of writing it to disk (for example, to add more data before saving),
use ``interface.create_nwbfile(metadata=metadata)``.
