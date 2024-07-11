ThorLabs data conversion
------------------------

Install NeuroConv with the additional dependencies necessary for reading ThorLabs imaging data.

.. code-block:: bash

    pip install neuroconv[thor]

Convert single plane single file imaging data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert ScanImage imaging data to NWB using
:py:class:`~neuroconv.datainterfaces.ophys.thor.thorimaginginterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import ThorTiffImagingInterface
    >>>
    >>> file_path = OPHYS_DATA_PATH / "imaging_datasets" / "ThorLabs" / "data"
    >>> interface = ThorTiffImagingInterface(folder_path=folder_path)
    >>>
    >>> metadata = interface.get_metadata()
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> interface.run_conversion(nwbfile_path=f"{path_to_save_nwbfile}", metadata=metadata)
