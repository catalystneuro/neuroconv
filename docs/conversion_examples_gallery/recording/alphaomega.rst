AlphaOmega conversion
---------------------

Install NeuroConv with the additional dependencies necessary for reading AlphaOmega data.

.. code-block:: bash

    pip install neuroconv[alphaomega]

Convert AlphaOmega data to NWB using :py:class:`~neuroconv.datainterfaces.ecephys.alphaomega.alphaomegadatainterface.AlphaOmegaRecordingInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import AlphaOmegaRecordingInterface
    >>>
    >>> folder_path = f"{ECEPHY_DATA_PATH}/alphaomega/mpx_map_version4/"
    >>> # Change the file_path to the location in your system
    >>> interface = AlphaOmegaRecordingInterface(folder_path=folder_path, verbose=False)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
