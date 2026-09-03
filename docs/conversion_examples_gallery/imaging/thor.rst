Thor TIFF data conversion
-------------------------

Install NeuroConv with the additional dependencies necessary for reading Thor TIFF data.

.. code-block:: bash

    pip install "neuroconv[thor]"

Convert a ThorImageLS acquisition
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Point :py:class:`~neuroconv.converters.ThorConverter` at the first OME-TIFF of the acquisition and
every channel named in the accompanying ``Experiment.xml`` is written, one ``ImagingPlane`` and one
``TwoPhotonSeries`` each, all referring to a single ``Device`` named ``ThorMicroscope``.

.. code-block:: python

    >>> from pathlib import Path
    >>> from neuroconv.converters import ThorConverter
    >>>
    >>> file_path = OPHYS_DATA_PATH / "imaging_datasets" / "ThorlabsTiff" / "single_channel_single_plane" / "20231018-002" / "ChanA_001_001_001_001.tif"
    >>> converter = ThorConverter(file_path=file_path)
    >>>
    >>> metadata = converter.get_metadata()
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

NeuroConv aims to automatically add all the metadata annotations that are present in the source format.
It is often the case that crucial information is not available there, such as the anatomical location,
the meaning of the values, or a semantically meaningful description of the data. Follow
:ref:`the ophys how-to <annotate_ophys_metadata>` for a modality-relevant guide to adding
this extra metadata, which makes the data more useful for future users and for the community as a whole.
Its :ref:`section on templates <how_to_annotate_ophys_from_a_template>` starts from scratch, and the
:ref:`reference template <ophys_imaging_metadata_template>` lists every element the metadata accepts.

Convert a single channel
~~~~~~~~~~~~~~~~~~~~~~~~

Use :py:class:`~neuroconv.datainterfaces.ophys.thor.thordatainterface.ThorImagingInterface` to write
one channel, chosen with the `channel_name` argument. To see what is available, use
`ThorConverter.get_available_channels(file_path)`.

.. code-block:: python

    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import ThorImagingInterface
    >>>
    >>> file_path = OPHYS_DATA_PATH / "imaging_datasets" / "ThorlabsTiff" / "single_channel_single_plane" / "20231018-002" / "ChanA_001_001_001_001.tif"
    >>> interface = ThorImagingInterface(file_path=file_path, channel_name="ChanA")
    >>>
    >>> metadata = interface.get_metadata()
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{output_folder}/single_channel.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)


.. note::

    The :py:class:`~neuroconv.datainterfaces.ophys.thor.thordatainterface.ThorImagingInterface` is designed for
    imaging data acquired using ThorImageLS software and exported to TIFF format.  Note that it is possible that data was acquired with a Thor microscope but not with
    the ThorImageLS software, in which case this interface may not work correctly.
