Bruker TIFF data conversion
---------------------------

Install NeuroConv with the additional dependencies necessary for reading Bruker TIFF data.

.. code-block:: bash

    pip install "neuroconv[brukertiff]"

The unified :py:class:`~neuroconv.datainterfaces.BrukerTiffImagingInterface` reads Bruker
Prairie View OME-TIFF folders. It handles single-plane, volumetric, and multi-channel data
through a single class. Channels are identified by name (e.g. ``"Ch1"``, ``"Ch2"``);
volumetric data is exposed as a 4D series.

**Convert a single-plane single-channel acquisition**

.. code-block:: python

    >>> from zoneinfo import ZoneInfo
    >>> from neuroconv.datainterfaces import BrukerTiffImagingInterface
    >>>
    >>> # The 'folder_path' is the path to the folder containing the OME-TIF image files and the XML configuration file.
    >>> folder_path = OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR32_2023_02_20_Into_the_void_t_series_baseline-000"
    >>> interface = BrukerTiffImagingInterface(folder_path=folder_path)
    >>>
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we can add the time zone information to the conversion if missing
    >>> session_start_time = metadata["NWBFile"]["session_start_time"]
    >>> tzinfo = ZoneInfo("US/Pacific")
    >>> metadata["NWBFile"].update(session_start_time=session_start_time.replace(tzinfo=tzinfo))
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

**Convert a volumetric acquisition**

Volumetric data is returned by the extractor as a 4D series ``(samples, height, width, planes)``,
written as a single ``TwoPhotonSeries`` with the per-volume sampling rate.

.. code-block:: python

    >>> from zoneinfo import ZoneInfo
    >>> from neuroconv.datainterfaces import BrukerTiffImagingInterface
    >>>
    >>> folder_path = OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR32_2022_11_03_IntoTheVoid_t_series-005"
    >>> interface = BrukerTiffImagingInterface(folder_path=folder_path)
    >>>
    >>> metadata = interface.get_metadata()
    >>> session_start_time = metadata["NWBFile"]["session_start_time"]
    >>> tzinfo = ZoneInfo("US/Pacific")
    >>> metadata["NWBFile"].update(session_start_time=session_start_time.replace(tzinfo=tzinfo))
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

**Convert a multi-channel acquisition (recommended convenience path)**

For dual-color or other multi-channel folders, the
:py:class:`~neuroconv.converters.BrukerTiffConverter` auto-detects channels in the folder and
builds one :py:class:`~neuroconv.datainterfaces.BrukerTiffImagingInterface` per channel.
Single-channel folders pass through unchanged.

.. code-block:: python

    >>> from zoneinfo import ZoneInfo
    >>> from neuroconv.converters import BrukerTiffConverter
    >>>
    >>> folder_path = OPHYS_DATA_PATH / "imaging_datasets" / "BrukerTif" / "NCCR62_2023_07_06_IntoTheVoid_t_series_Dual_color-000"
    >>> converter = BrukerTiffConverter(folder_path=folder_path)
    >>>
    >>> metadata = converter.get_metadata()
    >>> session_start_time = metadata["NWBFile"]["session_start_time"]
    >>> tzinfo = ZoneInfo("US/Pacific")
    >>> metadata["NWBFile"].update(session_start_time=session_start_time.replace(tzinfo=tzinfo))
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

**Convert a multi-channel acquisition (manual composition)**

If you need fine-grained control over which channels are written or want to mix in interfaces
from other modalities, instantiate one
:py:class:`~neuroconv.datainterfaces.BrukerTiffImagingInterface` per channel and combine them
with a :py:class:`~neuroconv.ConverterPipe`. Each interface gets its own auto-suffixed
``metadata_key`` so devices, imaging planes, and series are namespaced cleanly.

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

**Disjoint per-plane volumetric output**

By default volumetric data is written as a single 4D ``TwoPhotonSeries``. To instead write each
z-plane as its own 2D ``TwoPhotonSeries`` and ``ImagingPlane`` (the "disjoint" layout, where each
plane carries its own focal depth), pass ``plane_separation_type="disjoint"`` to
:py:class:`~neuroconv.converters.BrukerTiffConverter`.

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
