Thor TIFF data conversion
-------------------------

Install NeuroConv with the additional dependencies necessary for reading Thor TIFF data.

.. code-block:: bash

    pip install "neuroconv[thor]"

Convert Thor TIFF imaging data to NWB using
:py:class:`~neuroconv.datainterfaces.ophys.thor.thordatainterface.ThorImagingInterface`.

.. code-block:: python

    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import ThorImagingInterface
    >>>
    >>> file_path = OPHYS_DATA_PATH / "imaging_datasets" / "ThorlabsTiff" / "single_channel_single_plane" / "20231018-002" / "ChanA_001_001_001_001.tif"
    >>> interface = ThorImagingInterface(file_path=file_path, channel_name="ChanA")
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path)


.. note::

    The :py:class:`~neuroconv.datainterfaces.ophys.thor.thordatainterface.ThorImagingInterface` is designed for
    imaging data acquired using ThorImageLS software and exported to TIFF format.  Note that it is possible that data was acquired with a Thor microscope but not with
    the ThorImageLS software, in which case this interface may not work correctly.
