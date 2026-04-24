Spike2 data conversion
----------------------

Install NeuroConv with the additional dependencies necessary for reading Spike2 data by Cambridge Electronic Design (CED).

.. code-block:: bash

    pip install "neuroconv[spike2]"

Convert Spike2 data to NWB using
:py:class:`~neuroconv.datainterfaces.ecephys.spike2.spike2datainterface.Spike2RecordingInterface`.

.. code-block:: python

    from datetime import datetime
    from zoneinfo import ZoneInfo
    from pathlib import Path
    from neuroconv.datainterfaces import Spike2RecordingInterface

    # For this interface we need to pass the specific path to the files.
    file_path = f"{ECEPHY_DATA_PATH}/spike2/m365_1sec.smrx"
    # Change the file_path to the location in your system
    interface = Spike2RecordingInterface(file_path=file_path, verbose=False)

    # Extract what metadata we can from the source files
    metadata = interface.get_metadata()
    # For data provenance we add the time zone information to the conversion
    session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    metadata["NWBFile"].update(session_start_time=session_start_time)
    # Add subject information (required for DANDI upload)
    metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    # Choose a path for saving the nwb file and run the conversion
    nwbfile_path = f"{path_to_save_nwbfile}"
    interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

.. note::
    At the moment, Spike2 data conversion is not supported because the python API only supports python 3.9 which we no longer
    support. We are in the process of updating the interface to support python 3.10 and above. Please fill an issue if you
    require this feature so we can assess the priority of this feature. You can use a version an older version of NeuroConv (< 0.7.3>)
    to converter this data in the meanwhile
