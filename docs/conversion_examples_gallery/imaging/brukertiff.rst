Bruker TIFF data conversion
---------------------------

Install NeuroConv with the additional dependencies necessary for reading Bruker TIFF data.

.. code-block:: bash

    pip install "neuroconv[brukertiff]"

**Convert a Bruker session**

A Prairie View session is a folder of OME-TIFF files together with the ``.xml`` configuration that
describes them. Point :py:class:`~neuroconv.converters.BrukerTiffConverter` at that folder.

.. code-block:: python

    >>> from zoneinfo import ZoneInfo
    >>> from neuroconv.converters import BrukerTiffConverter
    >>>
    >>> # The 'folder_path' is the path to the folder containing the OME-TIF image files and the XML configuration file.
    >>> folder_path = OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR32_2023_02_20_Into_the_void_t_series_baseline-000"
    >>> converter = BrukerTiffConverter(folder_path=folder_path)
    >>>
    >>> metadata = converter.get_metadata()
    >>> # For data provenance we can add the time zone information to the conversion if missing
    >>> session_start_time = metadata["NWBFile"]["session_start_time"]
    >>> tzinfo = ZoneInfo("US/Pacific")
    >>> metadata["NWBFile"].update(session_start_time=session_start_time.replace(tzinfo=tzinfo))
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

That call covers any Prairie View session, planar or volumetric, single-channel or multi-channel.
The converter reads the channels from the ``.xml`` and writes one ``ImagingPlane`` and one
``TwoPhotonSeries`` per channel, all referring to the one microscope ``Device``.

**Writing a volumetric session**

A volumetric session can be written two ways, chosen with ``plane_separation_type``. The default,
``"contiguous"``, keeps the volume together: the extractor returns a 4D series
``(samples, height, width, planes)`` and it is written as a single ``TwoPhotonSeries`` per channel
with the per-volume sampling rate.

Passing ``"disjoint"`` splits the volume instead, writing each z-plane as its own 2D
``TwoPhotonSeries`` and ``ImagingPlane``, with each plane carrying its own focal depth. Prefer it
when the planes are far enough apart to be read as separate fields of view rather than one volume.
The setting has no effect on planar sessions.

.. code-block:: python

    >>> from zoneinfo import ZoneInfo
    >>> from neuroconv.converters import BrukerTiffConverter
    >>>
    >>> folder_path = OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR32_2022_11_03_IntoTheVoid_t_series-005"
    >>> converter = BrukerTiffConverter(folder_path=folder_path, plane_separation_type="disjoint")
    >>>
    >>> metadata = converter.get_metadata()
    >>> session_start_time = metadata["NWBFile"]["session_start_time"]
    >>> tzinfo = ZoneInfo("US/Pacific")
    >>> metadata["NWBFile"].update(session_start_time=session_start_time.replace(tzinfo=tzinfo))
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

**Converting a single channel or a single plane**

To write part of a session rather than all of it, use
:py:class:`~neuroconv.datainterfaces.BrukerTiffImagingInterface` directly. ``channel_name`` selects
one channel (``BrukerTiffImagingInterface.get_available_channels(folder_path=...)`` lists what is
available) and ``plane_index`` pins the interface to a single depth plane of a volumetric session.

.. code-block:: python

    >>> from zoneinfo import ZoneInfo
    >>> from neuroconv.datainterfaces import BrukerTiffImagingInterface
    >>>
    >>> folder_path = OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR62_2023_07_06_IntoTheVoid_t_series_Dual_color-000"
    >>> interface = BrukerTiffImagingInterface(folder_path=folder_path, channel_name="Ch1")
    >>>
    >>> metadata = interface.get_metadata()
    >>> session_start_time = metadata["NWBFile"]["session_start_time"]
    >>> tzinfo = ZoneInfo("US/Pacific")
    >>> metadata["NWBFile"].update(session_start_time=session_start_time.replace(tzinfo=tzinfo))
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

**Combining with other data**

To write a Bruker session alongside interfaces from other modalities, build the per-channel
interfaces yourself and combine them with a :py:class:`~neuroconv.ConverterPipe`. Each interface
gets its own auto-suffixed ``metadata_key``, so the imaging planes and series stay namespaced while
the microscope stays shared.

.. code-block:: python

    >>> from zoneinfo import ZoneInfo
    >>> from neuroconv import ConverterPipe
    >>> from neuroconv.datainterfaces import BrukerTiffImagingInterface
    >>>
    >>> folder_path = OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR62_2023_07_06_IntoTheVoid_t_series_Dual_color-000"
    >>> interface_ch1 = BrukerTiffImagingInterface(folder_path=folder_path, channel_name="Ch1")
    >>> interface_ch2 = BrukerTiffImagingInterface(folder_path=folder_path, channel_name="Ch2")
    >>> converter = ConverterPipe(data_interfaces=dict(channel_1=interface_ch1, channel_2=interface_ch2))
    >>>
    >>> metadata = converter.get_metadata()
    >>> session_start_time = metadata["NWBFile"]["session_start_time"]
    >>> tzinfo = ZoneInfo("US/Pacific")
    >>> metadata["NWBFile"].update(session_start_time=session_start_time.replace(tzinfo=tzinfo))
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)
