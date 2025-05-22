Inscopix imaging data conversion
--------------------------------

Install NeuroConv with the additional dependencies necessary for reading Inscopix data.

.. code-block:: bash

    pip install "neuroconv[inscopix]"

Convert Inscopix imaging data to NWB using :py:class:`~neuroconv.datainterfaces.ophys.inscopix.inscopiximagingdatainterface.InscopixImagingInterface`.

.. code-block:: python

    >>> import sys, platform
    >>> if sys.version_info >= (3, 13) or (platform.system() == "Darwin" and platform.machine() == "arm64"):
    ...     skip_test = True
    >>> else:
    ...     skip_test = False
    >>> if not skip_test:
    ...     from datetime import datetime
    ...     from zoneinfo import ZoneInfo
    ...     from pathlib import Path
    ...     from neuroconv.datainterfaces import InscopixImagingInterface
    ...
    ...     file_path = OPHYS_DATA_PATH / "imaging_datasets" / "inscopix" / "movie_128x128x100_part1.isxd"
    ...     interface = InscopixImagingInterface(file_path=file_path, verbose=False)
    ...
    ...     metadata = interface.get_metadata()
    ...     # For data provenance we add the time zone information to the conversion
    ...     session_start_time = datetime(2025, 5, 21, 10, 0, 0, tzinfo=ZoneInfo("Europe/Paris"))
    ...     metadata["NWBFile"].update(session_start_time=session_start_time)
    ...
    ...     # Run the conversion
    ...     nwbfile_path = f"{path_to_save_nwbfile}"
    ...     interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
    >>> else:
    ...     print("Skipped: incompatible environment for Inscopix interface. "
    ...           "The isx package is currently not natively supported on macOS with Apple Silicon "
    ...           "(see: https://github.com/inscopix/pyisx?tab=readme-ov-file#install) "
    ...           "The isx package has incompatibility with Python 3.13 - requires Python <3.13, >=3.9 "
    ...           "(see: https://github.com/inscopix/pyisx/issues)")
