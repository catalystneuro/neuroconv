ScanImage Legacy (v3.8 and older)
==================================

Install the package with the additional dependencies necessary for reading ScanImage TIFF files (v3.8 and older) using the legacy reader:

.. code-block:: bash

    pip install neuroconv[scanimage_legacy]

Convert ScanImage TIFF files to NWB using :py:class:`~neuroconv.datainterfaces.ophys.scanimage.ScanImageTiffInterface`.

.. code-block:: python

    >>> from neuroconv.datainterfaces import ScanImageTiffInterface
    >>> interface = ScanImageTiffInterface(file_path="my_scanimage_file.tif", fallback_sampling_frequency=30.0)
    >>> metadata = interface.get_metadata()
    >>> interface.run_conversion(nwbfile_path="my_nwbfile.nwb", metadata=metadata)

The ScanImage Legacy interface uses the ``scanimage-tiff-reader`` package for reading legacy ScanImage TIFF files that may not be compatible with the standard TIFF readers.

.. note::
    This interface is specifically for legacy ScanImage files. For newer ScanImage files, use the regular :py:class:`~neuroconv.datainterfaces.ophys.scanimage.ScanImageTiffInterface` with the ``scanimage`` extra instead.
