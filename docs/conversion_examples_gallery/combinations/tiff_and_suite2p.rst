Tiff & suite2p
--------------

A common workflow in optical physiology is to record images with a microscope (imaging) and then use a segmentation
algorithm to produce regions of interest and fluorescence traces. The following is an example of who to implement this
workflow in neuroconv for Tiff imaging files segmented using suite2p. This conversion uses the classes
:py:class:`~neuroconv.datainterfaces.ophys.tiff.tiffdatainterface.TiffImagingInterface` and
:py:class:`~neuroconv.datainterfaces.ophys.suite2p.suite2pdatainterface.Suite2pSegmentationInterface`.


.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from neuroconv import ConverterPipe
    >>> from neuroconv.datainterfaces import TiffImagingInterface, Suite2pSegmentationInterface
    >>>
    >>> file_path = OPHYS_DATA_PATH / "imaging_datasets" / "Tif" / "demoMovie.tif"
    >>> interface_tiff = TiffImagingInterface(file_path=file_path, sampling_frequency=15.0, verbose=False)
    >>>
    >>> folder_path= OPHYS_DATA_PATH / "segmentation_datasets" / "suite2p"
    >>> interface_suit2p = Suite2pSegmentationInterface(folder_path=folder_path, verbose=False)
    >>>
    >>> # Now that we have defined the two interfaces we pass them to the ConverterPipe which will coordinate the
    >>> # concurrent conversion of the data
    >>> converter = ConverterPipe(data_interfaces=[interface_tiff, interface_suit2p], verbose=False)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = converter.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> tzinfo = tz.gettz("US/Pacific")
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> nwbfile_out = converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)
