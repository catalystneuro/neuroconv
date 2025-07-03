Femtonics imaging data conversion
---------------------------------

Install NeuroConv with the additional dependencies necessary for reading Femtonics data.

.. code-block:: bash

    pip install "neuroconv[femtonics]"

Convert Femtonics imaging data to NWB using :py:class:`~neuroconv.datainterfaces.ophys.femtonics.femtonicsimaginginterface.FemtonicsImagingInterface``

.. code-block:: python
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import FemtonicsImagingInterface
    >>>
    >>> file_path = OPHYS_DATA_PATH / "imaging_datasets" / "Femtonics" / "moser_lab_mec" / "p29.mesc"
    >>> interface = FemtonicsImagingInterface(file_path=file_path, munit_name="MUnit_0", channel_name="UG")
    >>>
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
