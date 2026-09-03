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

``acquisition_format`` selects how the raw traces are read — ``"tdt"``, ``"csv"``, ``"doric"``, or
``"npm"``, matching the :doc:`TDT <tdt_fp>`, :doc:`CSV <csv_fp>`, :doc:`Doric <doric_fp>`, and
:doc:`NPM <npm_fp>` interfaces. The events are read the same way, except for the ones that did not come
from the acquisition system: GuPPy's custom-event import writes the events it imported back out as
one-column ``timestamps`` CSVs, which then sit in the session folder beside whatever the rig recorded.
``events_folder_path`` is scanned for those files, so a session whose ``storesList.csv`` lists stores
from two sources at once — the tank's epocs and an imported ``licks.csv``, say — needs nothing extra
declared.

GuPPy also reads NWB as an input format. If your session is **already in NWB**, see
:ref:`guppy_existing_nwbfile` below.

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

NeuroConv aims to automatically add all the metadata annotations that are present in the source format.
It is often the case that crucial information is not available there, such as the anatomical location,
the meaning of the values, or a semantically meaningful description of the data. Follow
:ref:`the fiber photometry how-to <annotate_fiber_photometry_metadata>` for a modality-relevant guide to adding
this extra metadata, which makes the data more useful for future users and for the community as a whole.
Its :ref:`section on templates <how_to_annotate_from_a_template>` starts from scratch, and the
:ref:`reference template <fiber_photometry_metadata_template>` lists every element the metadata accepts.

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

.. _guppy_existing_nwbfile:

Adding GuPPy outputs to an existing NWB file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When GuPPy processed a session out of an NWB file, use
:py:class:`~neuroconv.datainterfaces.fiber_photometry.guppy.guppydatainterface.GuppyInterface`
directly rather than the converter: hand it the file and it adds GuPPy's outputs to it.

Each recording site is linked to the rows its fibers occupy in the file's own
``FiberPhotometryTable``.

.. code-block:: python

    from pynwb import read_nwb

    from neuroconv.datainterfaces import GuppyInterface
    from neuroconv.tools.nwb_helpers import configure_and_write_nwbfile

    interface = GuppyInterface(folder_path=guppy_folder)

    nwbfile = read_nwb(path=source_nwbfile_path)
    interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())
    configure_and_write_nwbfile(nwbfile=nwbfile, nwbfile_path=nwbfile_path, backend="hdf5")

Writing to a *new* path exports the source with the GuPPy outputs added; the original file is left
alone.

The events registry references an ``EventsTable`` of the onsets GuPPy analyzed, written into
``nwbfile.events`` — the same table whether the interface runs here or inside ``GuppyConverter``.
Events the file already holds are left as they are. The name of GuPPy's table is editable, at
``metadata["FiberPhotometry"]["Guppy"][metadata_key]["Events"]["name"]``.
