Plexon2 Recording Conversion
----------------------------

Install NeuroConv with the additional dependencies necessary for reading Plexon acquisition data.

.. code-block:: bash

    pip install neuroconv[plexon2]

.. warning::
    When running plexon2 conversion on platforms other than Windows, you also need to install `wine <https://www.winehq.org/>`_.
    Plexon2 is not supported on Python 3.14 outside Windows at the moment.

    Plexon2 reading through Wine worked in our tests on Ubuntu 24.04 with Wine 9, but failed on Ubuntu 26.04 with Wine 10.
    We are working on migrating to a reader that does not require Wine.
    See `issue #2119 (Remove the Wine dependency from the Plexon2 interface) <https://github.com/catalystneuro/neuroconv/issues/2119>`_ for details.

Convert Plexon2 recording data to NWB using :py:class:`~neuroconv.datainterfaces.ecephys.plexon.plexondatainterface.Plexon2RecordingInterface`.

.. code-block:: python

    from datetime import datetime
    from zoneinfo import ZoneInfo
    from pathlib import Path
    from neuroconv.datainterfaces import Plexon2RecordingInterface

    file_path = f"{ECEPHY_DATA_PATH}/plexon/4chDemoPL2.pl2"
    # Change the file_path to the location in your system
    interface = Plexon2RecordingInterface(file_path=file_path, verbose=False)

    # Extract what metadata we can from the source files
    metadata = interface.get_metadata()
    # For data provenance we add the time zone information to the conversion
    tzinfo = ZoneInfo("Asia/Tokyo")
    session_start_time = metadata["NWBFile"]["session_start_time"]
    metadata["NWBFile"].update(session_start_time=session_start_time.replace(tzinfo=tzinfo))
    # Add subject information (required for DANDI upload)
    metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    # Choose a path for saving the nwb file and run the conversion
    nwbfile_path = f"{path_to_save_nwbfile}"
    interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
