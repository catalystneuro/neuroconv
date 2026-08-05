GuPPy Fiber Photometry data conversion
---------------------------------------

Install NeuroConv with the additional dependencies necessary for reading GuPPy data.

.. code-block:: bash

    pip install "neuroconv[guppy]"

`GuPPy <https://github.com/LernerLab/GuPPy>`_ is an analysis pipeline that runs on top of an
acquisition format, so a GuPPy conversion covers both: the raw traces and events, plus GuPPy's derived
outputs, written into one NWB file with
:py:class:`~neuroconv.datainterfaces.fiber_photometry.guppy.guppyconverter.GuppyConverter`.

Point the converter at three folders
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``fiber_photometry_folder_path`` holds the raw traces, ``events_folder_path`` the raw behavioral
events, and ``guppy_folder_path`` is GuPPy's ``<session>_output_<N>`` folder. GuPPy writes a session's
traces and events into one folder, so in practice the first two are usually the same path.

``acquisition_format`` selects how the two raw folders are read — ``"tdt"``, ``"csv"``, ``"doric"``,
``"npm"``, or ``"nwb"``. The first four match the :doc:`TDT <tdt_fp>`, :doc:`CSV <csv_fp>`,
:doc:`Doric <doric_fp>`, and :doc:`NPM <npm_fp>` interfaces.

``"nwb"`` covers a session GuPPy processed out of an existing NWB file: both raw folders are the folder
holding that one ``.nwb`` file, and the converter reads its response series and events into a new file
alongside the GuPPy outputs. Only those cross over — anything else the source holds is not carried into
the converted file. The source also already states the fiber photometry provenance chain, so unlike the
other four formats you do not supply it; the converter reads devices, indicators, the
``FiberPhotometryTable`` and each series' region from the source and returns them as editable metadata.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo

    >>> from neuroconv.converters import GuppyConverter

    >>> session_folder = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "Guppy" / "guppy_example_1"
    >>> guppy_folder = session_folder / "guppy_example_1_output_1"

    >>> converter = GuppyConverter(
    ...     fiber_photometry_folder_path=session_folder,
    ...     events_folder_path=session_folder,
    ...     guppy_folder_path=guppy_folder,
    ...     acquisition_format="csv",
    ... )

This session has two recording sites, ``dms`` and ``nac``, each with a signal and an isosbestic control
store, and two behavioral event types, ``nose_poke`` and ``reward_delivery``.

Supply the fiber photometry provenance
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

As with every fiber photometry interface, the hardware chain is yours to supply. The
``FiberPhotometryTable`` carries one row per store, so this two-site isosbestic session has four rows,
and each series' region must name its stores in column order.

The rest of the format — device models, devices, indicators, and the response series blocks — is shared
across the fiber photometry interfaces and documented at :ref:`fiber_photometry_metadata_structure`.

.. code-block:: python

    >>> metadata = converter.get_metadata()

    >>> metadata["DeviceModels"] = {
    ...     "optical_fiber_model": {
    ...         "type": "OpticalFiberModel",
    ...         "name": "optical_fiber_model",
    ...         "manufacturer": "Doric Lenses",
    ...         "numerical_aperture": 0.48,
    ...     },
    ...     "excitation_source_model": {
    ...         "type": "ExcitationSourceModel",
    ...         "name": "excitation_source_model",
    ...         "manufacturer": "Doric Lenses",
    ...         "source_type": "LED",
    ...         "excitation_mode": "one-photon",
    ...     },
    ...     "photodetector_model": {
    ...         "type": "PhotodetectorModel",
    ...         "name": "photodetector_model",
    ...         "manufacturer": "Doric Lenses",
    ...         "detector_type": "photodiode",
    ...     },
    ... }

    >>> # One optical fiber per recording site; the two excitation sources are the two roles.
    >>> metadata["Devices"] = {
    ...     "optical_fiber_dms": {
    ...         "type": "OpticalFiber",
    ...         "name": "optical_fiber_dms",
    ...         "device_model_metadata_key": "optical_fiber_model",
    ...         "fiber_insertion": {"depth_in_mm": 2.8},
    ...     },
    ...     "optical_fiber_nac": {
    ...         "type": "OpticalFiber",
    ...         "name": "optical_fiber_nac",
    ...         "device_model_metadata_key": "optical_fiber_model",
    ...         "fiber_insertion": {"depth_in_mm": 4.2},
    ...     },
    ...     "excitation_source_signal": {
    ...         "type": "ExcitationSource",
    ...         "name": "excitation_source_signal",
    ...         "device_model_metadata_key": "excitation_source_model",
    ...     },
    ...     "excitation_source_control": {
    ...         "type": "ExcitationSource",
    ...         "name": "excitation_source_control",
    ...         "device_model_metadata_key": "excitation_source_model",
    ...     },
    ...     "photodetector": {
    ...         "type": "Photodetector",
    ...         "name": "photodetector",
    ...         "device_model_metadata_key": "photodetector_model",
    ...     },
    ... }

    >>> metadata["FiberPhotometry"]["FiberPhotometryIndicators"] = {
    ...     "gcamp": {"name": "gcamp", "label": "GCaMP7b", "description": "GCaMP7b calcium indicator."},
    ... }

    >>> # One table row per store: site-major, signal before control.
    >>> rows = {}
    >>> for recording_site, depth in (("dms", 2.8), ("nac", 4.2)):
    ...     for role, excitation_wavelength in (("signal", 465.0), ("control", 405.0)):
    ...         rows[f"{recording_site}_{role}"] = {
    ...             "location": recording_site.upper(),
    ...             "excitation_wavelength_in_nm": excitation_wavelength,
    ...             "emission_wavelength_in_nm": 525.0,
    ...             "indicator_metadata_key": "gcamp",
    ...             "optical_fiber_metadata_key": f"optical_fiber_{recording_site}",
    ...             "excitation_source_metadata_key": f"excitation_source_{role}",
    ...             "photodetector_metadata_key": "photodetector",
    ...         }
    >>> metadata["FiberPhotometry"]["FiberPhotometryTable"] = {
    ...     "name": "fiber_photometry_table",
    ...     "description": "Dual-site GCaMP recording with an isosbestic control.",
    ...     "rows": rows,
    ... }

    >>> # Each role's series names its stores' rows in the order they are stacked into its columns.
    >>> for role in ("signal", "control"):
    ...     metadata["FiberPhotometry"][role]["fiber_photometry_table_region"] = [
    ...         f"{recording_site}_{role}" for recording_site in ("dms", "nac")
    ...     ]
    ...     metadata["FiberPhotometry"][role]["fiber_photometry_table_region_description"] = f"The {role} fibers."

Convert GuPPy data to NWB
~~~~~~~~~~~~~~~~~~~~~~~~~~

GuPPy and the acquisition share one clock: GuPPy emits timestamps in seconds since recording start, the
same origin the raw streams use. A CSV session carries no absolute clock origin, so
``session_start_time`` must be supplied explicitly here; a TDT session carries its own and does not.

.. code-block:: python

    >>> metadata["NWBFile"]["session_start_time"] = datetime.now(tz=ZoneInfo("US/Pacific"))
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)
