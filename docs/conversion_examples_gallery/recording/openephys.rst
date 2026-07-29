OpenEphys data conversion
-------------------------

OpenEphys supports two data formats: the `Binary (.dat) format <https://open-ephys.github.io/gui-docs/User-Manual/Data-formats/Binary-format.html#binaryformat>`_
and the `Open Ephys (.continuous) format <https://open-ephys.github.io/gui-docs/User-Manual/Data-formats/Open-Ephys-format.html>`_.
The :py:class:`~neuroconv.datainterfaces.ecephys.openephys.openephysdatainterface.OpenEphysRecordingInterface`
supports both formats and auto-detects which one to use based on the files present in the folder.

Install NeuroConv with the additional dependencies necessary for reading OpenEphys data.

.. code-block:: bash

    pip install "neuroconv[openephys]"

Convert OpenEphys data to NWB using :py:class:`~neuroconv.datainterfaces.ecephys.openephys.openephysdatainterface.OpenEphysRecordingInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>>
    >>> from neuroconv.datainterfaces import OpenEphysRecordingInterface
    >>>
    >>> folder_path = f"{ECEPHY_DATA_PATH}/openephysbinary/v0.4.4.1_with_video_tracking"
    >>> # Change the folder_path to the appropriate location in your system
    >>> interface = OpenEphysRecordingInterface(folder_path=folder_path)
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # session_start_time is required for conversion. If it cannot be inferred
    >>> # automatically from the source files you must supply one.
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "./saved_file.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

OpenEphysBinaryConverter
~~~~~~~~~~~~~~~~~~~~~~~~

For multi-stream OpenEphys binary recordings (e.g. Neuropixels with AP, LFP, and analog streams),
use :py:class:`~neuroconv.converters.OpenEphysBinaryConverter` to convert all streams at once.
When AP and LFP streams come from the same probe, the converter automatically shares electrode
table rows between them.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from neuroconv.converters import OpenEphysBinaryConverter
    >>>
    >>> folder_path = f"{ECEPHY_DATA_PATH}/openephysbinary/v0.6.x_neuropixels_with_sync"
    >>> # Change the folder_path to the appropriate location in your system
    >>> converter = OpenEphysBinaryConverter(folder_path=folder_path)
    >>> # Extract what metadata we can from the source files
    >>> metadata = converter.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = output_folder / "my_openephys_binary_converter_session.nwb"
    >>> converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

.. note::

    The ``OpenEphysBinaryConverter`` only supports the Binary (.dat) format. There is currently no converter for the
    Open Ephys (.continuous) format. If you need multi-stream conversion support for Open Ephys (.continuous) format data, please
    `open an issue <https://github.com/catalystneuro/neuroconv/issues>`_.
