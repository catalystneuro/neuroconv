FicTrac data conversion
--------------------------

Install NeuroConv with the additional dependencies necessary for reading FicTrac data.

.. code-block:: bash

    pip install neuroconv[fictrac]

Convert FicTrac pose estimation data to NWB using :py:class:`~neuroconv.datainterfaces.behavior.fictrac.fictracdatainterface.FicTracDataInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import FicTracDataInterface

    >>> file_path = BEHAVIOR_DATA_PATH / "FicTrac" / "sample" / "sample-20230724_113055.dat"

    >>> interface = FicTracDataInterface(file_path=file_path, verbose=False)

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata)
