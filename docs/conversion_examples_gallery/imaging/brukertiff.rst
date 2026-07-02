Bruker TIFF data conversion
---------------------------

Install NeuroConv with the additional dependencies necessary for reading Bruker TIFF data.

.. code-block:: bash

    pip install "neuroconv[brukertiff]"

The unified :py:class:`~neuroconv.datainterfaces.BrukerTiffImagingInterface` reads Bruker
Prairie View OME-TIFF folders. It handles single-plane, volumetric, and multi-channel data
through a single class. Channels are identified by zero-indexed strings (``"0"``, ``"1"``, ...);
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
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

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
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

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
    >>> converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

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
    >>> interface_ch0 = BrukerTiffImagingInterface(folder_path=folder_path, channel_name="0")
    >>> interface_ch1 = BrukerTiffImagingInterface(folder_path=folder_path, channel_name="1")
    >>> converter = ConverterPipe(data_interfaces=dict(channel_0=interface_ch0, channel_1=interface_ch1))
    >>>
    >>> metadata = converter.get_metadata()
    >>> session_start_time = metadata["NWBFile"]["session_start_time"]
    >>> tzinfo = ZoneInfo("US/Pacific")
    >>> metadata["NWBFile"].update(session_start_time=session_start_time.replace(tzinfo=tzinfo))
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

**Disjoint per-plane output (`BrukerTiffMultiPlaneConverter`)**

The unified interface writes volumetric data as a single 4D ``TwoPhotonSeries``. If you
need each z-plane as its own ``TwoPhotonSeries`` (one ``ImagingPlane`` per plane),
:py:class:`~neuroconv.converters.BrukerTiffMultiPlaneConverter` with
``plane_separation_type="disjoint"`` remains the only path. It is kept available for this
case until a ``plane_index`` selector is added to ``BrukerTiffImagingExtractor`` in
roiextractors; once that lands, the same per-plane output will be expressible through the
unified interface composed via :py:class:`~neuroconv.ConverterPipe`.
