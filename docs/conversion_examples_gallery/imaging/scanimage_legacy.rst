ScanImage Legacy (v3.8 and older)
==================================

Install the package with the additional dependencies necessary for reading ScanImage TIFF files (v3.8 and older) using the legacy reader:

.. code-block:: bash

    pip install neuroconv[scanimage_legacy]

Convert ScanImage TIFF files to NWB using :py:class:`~neuroconv.datainterfaces.ophys.scanimage.ScanImageTiffInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import ScanImageLegacyImagingInterface
    >>>
    >>> file_path = OPHYS_DATA_PATH / "imaging_datasets" / "Tif" / "sample_scanimage.tiff"
    >>>
    >>> # The fallback_sampling_frequency is only needed if the sampling frequency
    >>> # cannot be extracted from the file metadata
    >>> interface = ScanImageLegacyImagingInterface(
    ...     file_path=file_path,
    ...     fallback_sampling_frequency=30.0,  # Optional: only if not in metadata
    ... )
    >>>
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)


The ScanImageLegacyImagingInterface interface uses the ``scanimage-tiff-reader`` package for reading legacy ScanImage TIFF files that may not be compatible with the standard TIFF readers.

.. note::
    This interface is specifically for legacy ScanImage files. For newer ScanImage files, use the regular :py:class:`~neuroconv.datainterfaces.ophys.scanimage.ScanImageTiffInterface` with the ``scanimage`` extra instead.
