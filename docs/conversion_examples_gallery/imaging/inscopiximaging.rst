Inscopix imaging data conversion
--------------------------------

Install NeuroConv with the additional dependencies necessary for reading Inscopix data.

.. code-block:: bash

    pip install "neuroconv[inscopix]"

Convert Inscopix imaging data to NWB using :py:class:`~neuroconv.datainterfaces.ophys.inscopix.inscopiximagingdatainterface.InscopixImagingInterface`.

.. code-block:: python
   >>> import sys, platform
   >>> from datetime import datetime
   >>> from zoneinfo import ZoneInfo
   >>> from pathlib import Path
   >>>
   >>> # Check Python version and platform compatibility
   >>> if not (sys.version_info >= (3, 13) or (platform.system() == "Darwin" and platform.machine() == "arm64")):
   ...     from neuroconv.datainterfaces import InscopixImagingInterface
   ...
   ...     file_path = OPHYS_DATA_PATH / "imaging_datasets" / "inscopix" / "movie_128x128x100_part1.isxd"
   ...     interface = InscopixImagingInterface(file_path=file_path, verbose=False)
   ...
   ...     metadata = interface.get_metadata()
   ...     # For data provenance we add the time zone information to the conversion
   ...     session_start_time = datetime(2025, 5, 21, 10, 00, 0, tzinfo=ZoneInfo("Europe/Paris"))
   ...     metadata["NWBFile"].update(session_start_time=session_start_time)
   ...
   ...     # Run the conversion
   ...     nwbfile_path = f"{path_to_save_nwbfile}"
   ...     interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
   >>> else:
   ...     print("Skipped: incompatible environment for Inscopix interface.")
