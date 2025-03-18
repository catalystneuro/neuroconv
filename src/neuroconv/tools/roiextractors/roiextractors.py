import math
import warnings
from collections import defaultdict
from copy import deepcopy
from typing import Literal, Optional

import numpy as np
import psutil

# from hdmf.common import VectorData
from hdmf.data_utils import DataChunkIterator
from pydantic import FilePath
from pynwb import NWBFile
from pynwb.base import Images
from pynwb.device import Device
from pynwb.image import GrayscaleImage
from pynwb.ophys import (
    DfOverF,
    Fluorescence,
    ImageSegmentation,
    ImagingPlane,
    OnePhotonSeries,
    OpticalChannel,
    PlaneSegmentation,
    RoiResponseSeries,
    TwoPhotonSeries,
)
from roiextractors import (
    ImagingExtractor,
    MultiSegmentationExtractor,
    SegmentationExtractor,
)

from .imagingextractordatachunkiterator import ImagingExtractorDataChunkIterator
from ..hdmf import SliceableDataChunkIterator
from ..nwb_helpers import get_default_nwbfile_metadata, get_module, make_or_load_nwbfile
from ...utils import (
    DeepDict,
    calculate_regular_series_rate,
    dict_deep_update,
)
from ...utils.str_utils import human_readable_size


def _get_default_ophys_metadata() -> DeepDict:
    """Fill default metadata for Device and ImagingPlane."""
    metadata = get_default_nwbfile_metadata()

    default_device = dict(name="Microscope")

    default_optical_channel = dict(
        name="OpticalChannel",
        emission_lambda=np.nan,
        description="An optical channel of the microscope.",
    )

    default_imaging_plane = dict(
        name="ImagingPlane",
        description="The plane or volume being imaged by the microscope.",
        excitation_lambda=np.nan,
        indicator="unknown",
        location="unknown",
        device=default_device["name"],
        optical_channel=[default_optical_channel],
    )

    metadata.update(
        Ophys=dict(
            Device=[default_device],
            ImagingPlane=[default_imaging_plane],
        ),
    )

    return metadata


def _get_default_segmentation_metadata() -> DeepDict:
    """Fill default metadata for segmentation."""
    metadata = _get_default_ophys_metadata()

    default_fluorescence_roi_response_series = dict(
        name="RoiResponseSeries", description="Array of raw fluorescence traces.", unit="n.a."
    )

    default_fluorescence = dict(
        name="Fluorescence",
        PlaneSegmentation=dict(
            raw=default_fluorescence_roi_response_series,
        ),
        BackgroundPlaneSegmentation=dict(
            neuropil=dict(name="neuropil", description="Array of neuropil traces.", unit="n.a."),
        ),
    )

    default_dff_roi_response_series = dict(
        name="RoiResponseSeries",
        description="Array of df/F traces.",
        unit="n.a.",
    )

    default_df_over_f = dict(
        name="DfOverF",
        PlaneSegmentation=dict(
            dff=default_dff_roi_response_series,
        ),
    )

    default_image_segmentation = dict(
        name="ImageSegmentation",
        plane_segmentations=[
            dict(
                name="PlaneSegmentation",
                description="Segmented ROIs",
                imaging_plane=metadata["Ophys"]["ImagingPlane"][0]["name"],
            ),
            dict(
                name="BackgroundPlaneSegmentation",
                description="Segmented Background Components",
                imaging_plane=metadata["Ophys"]["ImagingPlane"][0]["name"],
            ),
        ],
    )

    default_segmentation_images = dict(
        name="SegmentationImages",
        description="The summary images of the segmentation.",
        PlaneSegmentation=dict(
            correlation=dict(name="correlation", description="The correlation image."),
        ),
    )

    metadata["Ophys"].update(
        dict(
            Fluorescence=default_fluorescence,
            DfOverF=default_df_over_f,
            ImageSegmentation=default_image_segmentation,
            SegmentationImages=default_segmentation_images,
        ),
    )

    return metadata


def get_nwb_imaging_metadata(
    imgextractor: ImagingExtractor,
    photon_series_type: Literal["OnePhotonSeries", "TwoPhotonSeries"] = "TwoPhotonSeries",
) -> dict:
    """
    Convert metadata from the ImagingExtractor into nwb specific metadata.

    Parameters
    ----------
    imgextractor : ImagingExtractor
        The imaging extractor to get metadata from.
    photon_series_type : {'OnePhotonSeries', 'TwoPhotonSeries'}, optional
        The type of photon series to create metadata for.

    Returns
    -------
    dict
        Dictionary containing metadata for devices, imaging planes, and photon series
        specific to the imaging data.
    """
    metadata = _get_default_ophys_metadata()

    channel_name_list = imgextractor.get_channel_names() or (
        ["OpticalChannel"]
        if imgextractor.get_num_channels() == 1
        else [f"OpticalChannel{idx}" for idx in range(imgextractor.get_num_channels())]
    )

    imaging_plane = metadata["Ophys"]["ImagingPlane"][0]
    for index, channel_name in enumerate(channel_name_list):
        if index == 0:
            imaging_plane["optical_channel"][index]["name"] = channel_name
        else:
            imaging_plane["optical_channel"].append(
                dict(
                    name=channel_name,
                    emission_lambda=np.nan,
                    description="An optical channel of the microscope.",
                )
            )

    one_photon_description = "Imaging data from one-photon excitation microscopy."
    two_photon_description = "Imaging data from two-photon excitation microscopy."
    photon_series_metadata = dict(
        name=photon_series_type,
        description=two_photon_description if photon_series_type == "TwoPhotonSeries" else one_photon_description,
        unit="n.a.",
        imaging_plane=imaging_plane["name"],
        dimension=list(imgextractor.get_image_size()),
    )
    metadata["Ophys"].update({photon_series_type: [photon_series_metadata]})

    return metadata


def add_devices_to_nwbfile(nwbfile: NWBFile, metadata: Optional[dict] = None) -> NWBFile:
    """
    Add optical physiology devices from metadata.
    The metadata concerning the optical physiology should be stored in metadata["Ophys]["Device"]
    This function handles both a text specification of the device to be built and an actual pynwb.Device object.

    """
    metadata_copy = {} if metadata is None else deepcopy(metadata)
    default_metadata = _get_default_ophys_metadata()
    metadata_copy = dict_deep_update(default_metadata, metadata_copy, append_list=False)
    device_metadata = metadata_copy["Ophys"]["Device"]

    for device in device_metadata:
        device_name = device["name"] if isinstance(device, dict) else device.name
        if device_name not in nwbfile.devices:
            device = Device(**device) if isinstance(device, dict) else device
            nwbfile.add_device(device)

    return nwbfile


def _create_imaging_plane_from_metadata(nwbfile: NWBFile, imaging_plane_metadata: dict) -> ImagingPlane:
    """
    Private auxiliary function to create an ImagingPlane object from pynwb using the imaging_plane_metadata.

    Parameters
    ----------
    nwbfile : NWBFile
        An previously defined -in memory- NWBFile.

    imaging_plane_metadata : dict
        The metadata to create the ImagingPlane object.

    Returns
    -------
    ImagingPlane
        The created ImagingPlane.
    """

    device_name = imaging_plane_metadata["device"]
    imaging_plane_metadata["device"] = nwbfile.devices[device_name]

    imaging_plane_metadata["optical_channel"] = [
        OpticalChannel(**metadata) for metadata in imaging_plane_metadata["optical_channel"]
    ]

    imaging_plane = ImagingPlane(**imaging_plane_metadata)

    return imaging_plane


def add_imaging_plane_to_nwbfile(
    nwbfile: NWBFile,
    metadata: dict,
    imaging_plane_name: Optional[str] = None,
) -> NWBFile:
    """
    Adds the imaging plane specified by the metadata to the nwb file.
    The imaging plane that is added is the one located in metadata["Ophys"]["ImagingPlane"][imaging_plane_index]

    Parameters
    ----------
    nwbfile : NWBFile
        An previously defined -in memory- NWBFile.
    metadata : dict
        The metadata in the nwb conversion tools format.
    imaging_plane_name: str
        The name of the imaging plane to be added.

    Returns
    -------
    NWBFile
        The nwbfile passed as an input with the imaging plane added.
    """

    # Set the defaults and required infrastructure
    metadata_copy = deepcopy(metadata)
    default_metadata = _get_default_ophys_metadata()
    metadata_copy = dict_deep_update(default_metadata, metadata_copy, append_list=False)
    add_devices_to_nwbfile(nwbfile=nwbfile, metadata=metadata_copy)

    default_imaging_plane_name = default_metadata["Ophys"]["ImagingPlane"][0]["name"]
    imaging_plane_name = imaging_plane_name or default_imaging_plane_name
    existing_imaging_planes = nwbfile.imaging_planes

    if imaging_plane_name not in existing_imaging_planes:
        imaging_plane_metadata = next(
            (
                imaging_plane_metadata
                for imaging_plane_metadata in metadata_copy["Ophys"]["ImagingPlane"]
                if imaging_plane_metadata["name"] == imaging_plane_name
            ),
            None,
        )
        if imaging_plane_metadata is None:
            raise ValueError(
                f"Metadata for Imaging Plane '{imaging_plane_name}' not found in metadata['Ophys']['ImagingPlane']."
            )

        imaging_plane = _create_imaging_plane_from_metadata(
            nwbfile=nwbfile, imaging_plane_metadata=imaging_plane_metadata
        )
        nwbfile.add_imaging_plane(imaging_plane)

    return nwbfile


def add_image_segmentation_to_nwbfile(nwbfile: NWBFile, metadata: dict) -> NWBFile:
    """
    Adds the image segmentation specified by the metadata to the nwb file.

    Parameters
    ----------
    nwbfile : NWBFile
        The nwbfile to add the image segmentation to.
    metadata: dict
        The metadata to create the image segmentation from.

    Returns
    -------
    NWBFile
        The NWBFile passed as an input with the image segmentation added.
    """
    # Set the defaults and required infrastructure
    metadata_copy = deepcopy(metadata)
    default_metadata = _get_default_segmentation_metadata()
    metadata_copy = dict_deep_update(default_metadata, metadata_copy, append_list=False)

    image_segmentation_metadata = metadata_copy["Ophys"]["ImageSegmentation"]
    image_segmentation_name = image_segmentation_metadata["name"]

    ophys = get_module(nwbfile, "ophys")

    # Check if the image segmentation already exists in the NWB file
    if image_segmentation_name not in ophys.data_interfaces:
        ophys.add(ImageSegmentation(name=image_segmentation_name))

    return nwbfile


def add_photon_series_to_nwbfile(
    imaging: ImagingExtractor,
    nwbfile: NWBFile,
    metadata: Optional[dict] = None,
    photon_series_type: Literal["TwoPhotonSeries", "OnePhotonSeries"] = "TwoPhotonSeries",
    photon_series_index: int = 0,
    parent_container: Literal["acquisition", "processing/ophys"] = "acquisition",
    iterator_type: Optional[str] = "v2",
    iterator_options: Optional[dict] = None,
    always_write_timestamps: bool = False,
) -> NWBFile:
    """
    Auxiliary static method for nwbextractor.

    Adds photon series from ImagingExtractor to NWB file object.
    The photon series can be added to the NWB file either as a TwoPhotonSeries
    or OnePhotonSeries object.

    Parameters
    ----------
    imaging : ImagingExtractor
        The imaging extractor to get the data from.
    nwbfile : NWBFile
        The nwbfile to add the photon series to.
    metadata: dict
        The metadata for the photon series.
    photon_series_type: {'OnePhotonSeries', 'TwoPhotonSeries'}, optional
        The type of photon series to add, default is TwoPhotonSeries.
    photon_series_index: int, default: 0
        The metadata for the photon series is a list of the different photon series to add.
        Specify which element of the list with this parameter.
    parent_container: {'acquisition', 'processing/ophys'}, optional
        The container where the photon series is added, default is nwbfile.acquisition.
        When 'processing/ophys' is chosen, the photon series is added to ``nwbfile.processing['ophys']``.
    iterator_type: str, default: 'v2'
        The type of iterator to use when adding the photon series to the NWB file.
    iterator_options: dict, optional
    always_write_timestamps : bool, default: False
        Set to True to always write timestamps.
        By default (False), the function checks if the timestamps are uniformly sampled, and if so, stores the data
        using a regular sampling rate instead of explicit timestamps. If set to True, timestamps will be written
        explicitly, regardless of whether the sampling rate is uniform.

    Returns
    -------
    NWBFile
        The NWBFile passed as an input with the photon series added.
    """

    iterator_options = iterator_options or dict()

    metadata_copy = {} if metadata is None else deepcopy(metadata)
    assert photon_series_type in [
        "OnePhotonSeries",
        "TwoPhotonSeries",
    ], "'photon_series_type' must be either 'OnePhotonSeries' or 'TwoPhotonSeries'."
    metadata_copy = dict_deep_update(
        get_nwb_imaging_metadata(imaging, photon_series_type=photon_series_type), metadata_copy, append_list=False
    )

    if photon_series_type == "TwoPhotonSeries" and "OnePhotonSeries" in metadata_copy["Ophys"]:
        warnings.warn(
            "Received metadata for both 'OnePhotonSeries' and 'TwoPhotonSeries', make sure photon_series_type is specified correctly."
        )

    assert parent_container in [
        "acquisition",
        "processing/ophys",
    ], "'parent_container' must be either 'acquisition' or 'processing/ophys'."

    # Tests if TwoPhotonSeries//OnePhotonSeries already exists in acquisition
    photon_series_metadata = metadata_copy["Ophys"][photon_series_type][photon_series_index]
    photon_series_name = photon_series_metadata["name"]

    if parent_container == "acquisition" and photon_series_name in nwbfile.acquisition:
        raise ValueError(f"{photon_series_name} already added to nwbfile.acquisition.")
    elif parent_container == "processing/ophys":
        ophys = get_module(nwbfile, name="ophys")
        if photon_series_name in ophys.data_interfaces:
            raise ValueError(f"{photon_series_name} already added to nwbfile.processing['ophys'].")

    # Add the image plane to nwb
    imaging_plane_name = photon_series_metadata["imaging_plane"]
    add_imaging_plane_to_nwbfile(nwbfile=nwbfile, metadata=metadata_copy, imaging_plane_name=imaging_plane_name)
    imaging_plane = nwbfile.get_imaging_plane(name=imaging_plane_name)
    photon_series_kwargs = deepcopy(photon_series_metadata)
    photon_series_kwargs.update(imaging_plane=imaging_plane)

    # Add the data
    frames_to_iterator = _imaging_frames_to_hdmf_iterator(
        imaging=imaging,
        iterator_type=iterator_type,
        iterator_options=iterator_options,
    )
    photon_series_kwargs.update(data=frames_to_iterator)

    # Add dimension
    photon_series_kwargs.update(dimension=imaging.get_image_size())

    # Add timestamps or rate
    if always_write_timestamps:
        timestamps = imaging.frame_to_time(np.arange(imaging.get_num_frames()))
        photon_series_kwargs.update(timestamps=timestamps)
    else:
        imaging_has_timestamps = imaging.has_time_vector()
        if imaging_has_timestamps:
            timestamps = imaging.frame_to_time(np.arange(imaging.get_num_frames()))
            estimated_rate = calculate_regular_series_rate(series=timestamps)
            starting_time = timestamps[0]
        else:
            estimated_rate = float(imaging.get_sampling_frequency())
            starting_time = 0.0

        if estimated_rate:
            photon_series_kwargs.update(rate=estimated_rate, starting_time=starting_time)
        else:
            photon_series_kwargs.update(timestamps=timestamps)

    # Add the photon series to the nwbfile (either as OnePhotonSeries or TwoPhotonSeries)
    photon_series = dict(
        OnePhotonSeries=OnePhotonSeries,
        TwoPhotonSeries=TwoPhotonSeries,
    )[
        photon_series_type
    ](**photon_series_kwargs)

    if parent_container == "acquisition":
        nwbfile.add_acquisition(photon_series)
    elif parent_container == "processing/ophys":
        ophys = get_module(nwbfile, name="ophys")
        ophys.add(photon_series)

    return nwbfile


def _check_if_imaging_fits_into_memory(imaging: ImagingExtractor) -> None:
    """
    Raise an error if the full traces of an imaging extractor are larger than available memory.

    Parameters
    ----------
    imaging : ImagingExtractor
        An imaging extractor object from roiextractors.

    Raises
    ------
    MemoryError
    """
    element_size_in_bytes = imaging.get_dtype().itemsize
    image_size = imaging.get_image_size()
    num_frames = imaging.get_num_frames()

    traces_size_in_bytes = num_frames * math.prod(image_size) * element_size_in_bytes
    available_memory_in_bytes = psutil.virtual_memory().available

    if traces_size_in_bytes > available_memory_in_bytes:
        message = (
            f"Memory error, full TwoPhotonSeries data is {human_readable_size(traces_size_in_bytes, binary=True)} but "
            f"only {human_readable_size(available_memory_in_bytes, binary=True)} are available! "
            "Please use iterator_type='v2'."
        )
        raise MemoryError(message)


def _imaging_frames_to_hdmf_iterator(
    imaging: ImagingExtractor,
    iterator_type: Optional[str] = "v2",
    iterator_options: Optional[dict] = None,
):
    """
    Private auxiliary method to wrap frames from an ImagingExtractor into a DataChunkIterator.

    Parameters
    ----------
    imaging : ImagingExtractor
        The imaging extractor to get the data from.
    iterator_type : {"v2", "v1",  None}, default: 'v2'
        The type of DataChunkIterator to use.
        'v1' is the original DataChunkIterator of the hdmf data_utils.
        'v2' is the locally developed SpikeInterfaceRecordingDataChunkIterator, which offers full control over chunking.
        None: write the TimeSeries with no memory chunking.
    iterator_options : dict, optional
        Dictionary of options for the iterator.
        For 'v1' this is the same as the options for the DataChunkIterator.
        For 'v2', see
        https://hdmf.readthedocs.io/en/stable/hdmf.data_utils.html#hdmf.data_utils.GenericDataChunkIterator
        for the full list of options.

    Returns
    -------
    DataChunkIterator
        The frames of the imaging extractor wrapped in an iterator object.
    """

    def data_generator(imaging):
        for i in range(imaging.get_num_frames()):
            yield imaging.get_frames(frame_idxs=[i]).squeeze().T

    assert iterator_type in ["v1", "v2", None], "'iterator_type' must be either 'v1', 'v2' (recommended), or None."
    iterator_options = dict() if iterator_options is None else iterator_options

    if iterator_type is None:
        _check_if_imaging_fits_into_memory(imaging=imaging)
        return imaging.get_video().transpose((0, 2, 1))

    if iterator_type == "v1":
        if "buffer_size" not in iterator_options:
            iterator_options.update(buffer_size=10)
        return DataChunkIterator(data=data_generator(imaging), **iterator_options)

    return ImagingExtractorDataChunkIterator(imaging_extractor=imaging, **iterator_options)


def add_imaging_to_nwbfile(
    imaging: ImagingExtractor,
    nwbfile: NWBFile,
    metadata: Optional[dict] = None,
    photon_series_type: Literal["TwoPhotonSeries", "OnePhotonSeries"] = "TwoPhotonSeries",
    photon_series_index: int = 0,
    iterator_type: Optional[str] = "v2",
    iterator_options: Optional[dict] = None,
    parent_container: Literal["acquisition", "processing/ophys"] = "acquisition",
    always_write_timestamps: bool = False,
) -> NWBFile:
    """
    Add imaging data from an ImagingExtractor object to an NWBFile.

    Parameters
    ----------
    imaging : ImagingExtractor
        The extractor object containing the imaging data.
    nwbfile : NWBFile
        The NWB file where the imaging data will be added.
    metadata : dict, optional
        Metadata for the NWBFile, by default None.
    photon_series_type : {"TwoPhotonSeries", "OnePhotonSeries"}, optional
        The type of photon series to be added, by default "TwoPhotonSeries".
    photon_series_index : int, optional
        The index of the photon series in the provided imaging data, by default 0.
    iterator_type : str, optional
        The type of iterator to use for adding the data. Commonly used to manage large datasets, by default "v2".
    iterator_options : dict, optional
        Additional options for controlling the iteration process, by default None.
    parent_container : {"acquisition", "processing/ophys"}, optional
        Specifies the parent container to which the photon series should be added, either as part of "acquisition" or
        under the "processing/ophys" module, by default "acquisition".
    always_write_timestamps : bool, default: False
        Set to True to always write timestamps.
        By default (False), the function checks if the timestamps are uniformly sampled, and if so, stores the data
        using a regular sampling rate instead of explicit timestamps. If set to True, timestamps will be written
        explicitly, regardless of whether the sampling rate is uniform.

    Returns
    -------
    NWBFile
        The NWB file with the imaging data added

    """
    add_devices_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
    nwbfile = add_photon_series_to_nwbfile(
        imaging=imaging,
        nwbfile=nwbfile,
        metadata=metadata,
        photon_series_type=photon_series_type,
        photon_series_index=photon_series_index,
        iterator_type=iterator_type,
        iterator_options=iterator_options,
        parent_container=parent_container,
        always_write_timestamps=always_write_timestamps,
    )

    return nwbfile


def write_imaging_to_nwbfile(
    imaging: ImagingExtractor,
    nwbfile_path: Optional[FilePath] = None,
    nwbfile: Optional[NWBFile] = None,
    metadata: Optional[dict] = None,
    overwrite: bool = False,
    verbose: bool = False,
    iterator_type: str = "v2",
    iterator_options: Optional[dict] = None,
    photon_series_type: Literal["TwoPhotonSeries", "OnePhotonSeries"] = "TwoPhotonSeries",
):
    """
    Primary method for writing an ImagingExtractor object to an NWBFile.

    Parameters
    ----------
    imaging: ImagingExtractor
        The imaging extractor object to be written to nwb
    nwbfile_path: FilePath
        Path for where to write or load (if overwrite=False) the NWBFile.
        If specified, the context will always write to this location.
    nwbfile: NWBFile, optional
        If passed, this function will fill the relevant fields within the NWBFile object.
        E.g., calling::

            write_recording(recording=my_recording_extractor, nwbfile=my_nwbfile)

        will result in the appropriate changes to the my_nwbfile object.
        If neither 'nwbfile_path' nor 'nwbfile' are specified, an NWBFile object will be automatically generated
        and returned by the function.
    metadata: dict, optional
        Metadata dictionary with information used to create the NWBFile when one does not exist or overwrite=True.
    overwrite: bool, optional
        Whether to overwrite the NWBFile if one exists at the nwbfile_path.
        The default is False (append mode).
    verbose: bool, optional
        If 'nwbfile_path' is specified, informs user after a successful write operation.
        The default is True.
    iterator_type: {"v2", "v1",  None}, default: 'v2'
        The type of DataChunkIterator to use.
        'v1' is the original DataChunkIterator of the hdmf data_utils.
        'v2' is the locally developed SpikeInterfaceRecordingDataChunkIterator, which offers full control over chunking.
        None: write the TimeSeries with no memory chunking.
    iterator_options : dict, optional
        Dictionary of options for the iterator.
        For 'v1' this is the same as the options for the DataChunkIterator.
        For 'v2', see
        https://hdmf.readthedocs.io/en/stable/hdmf.data_utils.html#hdmf.data_utils.GenericDataChunkIterator
        for the full list of options.
    """
    assert (
        nwbfile_path is None or nwbfile is None
    ), "Either pass a nwbfile_path location, or nwbfile object, but not both!"
    if nwbfile is not None:
        assert isinstance(nwbfile, NWBFile), "'nwbfile' should be of type pynwb.NWBFile"

    iterator_options = iterator_options or dict()

    if metadata is None:
        metadata = dict()
    if hasattr(imaging, "nwb_metadata"):
        metadata = dict_deep_update(imaging.nwb_metadata, metadata, append_list=False)

    with make_or_load_nwbfile(
        nwbfile_path=nwbfile_path, nwbfile=nwbfile, metadata=metadata, overwrite=overwrite, verbose=verbose
    ) as nwbfile_out:
        add_imaging_to_nwbfile(
            imaging=imaging,
            nwbfile=nwbfile,
            metadata=metadata,
            photon_series_type=photon_series_type,
            iterator_type=iterator_type,
            iterator_options=iterator_options,
        )
    return nwbfile_out


def get_nwb_segmentation_metadata(sgmextractor: SegmentationExtractor) -> dict:
    """
    Convert metadata from the segmentation into nwb specific metadata.

    Parameters
    ----------
    segmentation_extractor : SegmentationExtractor
        The segmentation extractor to get metadata from.

    Returns
    -------
    dict
        Dictionary containing metadata for devices, imaging planes, image segmentation,
        and fluorescence data specific to the segmentation.
    """
    metadata = _get_default_segmentation_metadata()
    # Optical Channel name:
    for i in range(sgmextractor.get_num_channels()):
        ch_name = sgmextractor.get_channel_names()[i]
        if i == 0:
            metadata["Ophys"]["ImagingPlane"][0]["optical_channel"][i]["name"] = ch_name
        else:
            metadata["Ophys"]["ImagingPlane"][0]["optical_channel"].append(
                dict(
                    name=ch_name,
                    emission_lambda=np.nan,
                    description=f"{ch_name} description",
                )
            )

    plane_segmentation_name = metadata["Ophys"]["ImageSegmentation"]["plane_segmentations"][0]["name"]
    for trace_name, trace_data in sgmextractor.get_traces_dict().items():
        # raw traces have already default name ("RoiResponseSeries")
        if trace_name in ["raw", "dff"]:
            continue
        if trace_data is not None and len(trace_data.shape) != 0:
            metadata["Ophys"]["Fluorescence"][plane_segmentation_name][trace_name] = dict(
                name=trace_name.capitalize(),
                description=f"description of {trace_name} traces",
            )

    return metadata


def add_plane_segmentation_to_nwbfile(
    segmentation_extractor: SegmentationExtractor,
    nwbfile: NWBFile,
    metadata: Optional[dict],
    plane_segmentation_name: Optional[str] = None,
    include_roi_centroids: bool = True,
    include_roi_acceptance: bool = True,
    mask_type: Optional[str] = "image",  # Optional[Literal["image", "pixel"]]
    iterator_options: Optional[dict] = None,
) -> NWBFile:
    """
    Adds the plane segmentation specified by the metadata to the image segmentation.

    If the plane segmentation already exists in the image segmentation, it is not added again.

    Parameters
    ----------
    segmentation_extractor : SegmentationExtractor
        The segmentation extractor to get the results from.
    nwbfile : NWBFile
        The NWBFile to add the plane segmentation to.
    metadata : dict, optional
        The metadata for the plane segmentation.
    plane_segmentation_name : str, optional
        The name of the plane segmentation to be added.
    include_roi_centroids : bool, default: True
        Whether to include the ROI centroids on the PlaneSegmentation table.
        If there are a very large number of ROIs (such as in whole-brain recordings),
        you may wish to disable this for faster write speeds.
    include_roi_acceptance : bool, default: True
        Whether to include if the detected ROI was 'accepted' or 'rejected'.
        If there are a very large number of ROIs (such as in whole-brain recordings), you may wish to disable this for
        faster write speeds.
    mask_type : str, default: 'image'
        There are three types of ROI masks in NWB, 'image', 'pixel', and 'voxel'.

        * 'image' masks have the same shape as the reference images the segmentation was applied to, and weight each pixel
          by its contribution to the ROI (typically boolean, with 0 meaning 'not in the ROI').
        * 'pixel' masks are instead indexed by ROI, with the data at each index being the shape of the image by the number
          of pixels in each ROI.
        * 'voxel' masks are instead indexed by ROI, with the data at each index being the shape of the volume by the number
          of voxels in each ROI.

        Specify your choice between these two as mask_type='image', 'pixel', 'voxel', or None.
        If None, the mask information is not written to the NWB file.
    iterator_options : dict, optional
        The options to use when iterating over the image masks of the segmentation extractor.

    Returns
    -------
    NWBFile
        The nwbfile passed as an input with the plane segmentation added.
    """

    default_plane_segmentation_index = 0
    roi_ids = segmentation_extractor.get_roi_ids()
    if include_roi_acceptance:
        accepted_ids = [int(roi_id in segmentation_extractor.get_accepted_list()) for roi_id in roi_ids]
        rejected_ids = [int(roi_id in segmentation_extractor.get_rejected_list()) for roi_id in roi_ids]
    else:
        accepted_ids, rejected_ids = None, None
    if mask_type == "image":
        image_or_pixel_masks = segmentation_extractor.get_roi_image_masks()
    elif mask_type == "pixel" or mask_type == "voxel":
        image_or_pixel_masks = segmentation_extractor.get_roi_pixel_masks()
    elif mask_type is None:
        image_or_pixel_masks = None
    else:
        raise AssertionError(
            "Keyword argument 'mask_type' must be one of either 'image', 'pixel', 'voxel', "
            f"or None (to not write any masks)! Received '{mask_type}'."
        )
    if include_roi_centroids:
        tranpose_image_convention = (1, 0) if len(segmentation_extractor.get_image_size()) == 2 else (1, 0, 2)
        roi_locations = segmentation_extractor.get_roi_locations()[tranpose_image_convention, :].T
    else:
        roi_locations = None

    nwbfile = _add_plane_segmentation(
        background_or_roi_ids=roi_ids,
        image_or_pixel_masks=image_or_pixel_masks,
        accepted_ids=accepted_ids,
        rejected_ids=rejected_ids,
        roi_locations=roi_locations,
        default_plane_segmentation_index=default_plane_segmentation_index,
        nwbfile=nwbfile,
        metadata=metadata,
        plane_segmentation_name=plane_segmentation_name,
        include_roi_centroids=include_roi_centroids,
        include_roi_acceptance=include_roi_acceptance,
        mask_type=mask_type,
        iterator_options=iterator_options,
    )
    return nwbfile


def _add_plane_segmentation(
    background_or_roi_ids: list,
    image_or_pixel_masks: np.ndarray,
    default_plane_segmentation_index: int,
    nwbfile: NWBFile,
    metadata: Optional[dict],
    plane_segmentation_name: Optional[str] = None,
    include_roi_centroids: bool = False,
    roi_locations: Optional[np.ndarray] = None,
    include_roi_acceptance: bool = False,
    accepted_ids: Optional[list] = None,
    rejected_ids: Optional[list] = None,
    mask_type: Optional[str] = "image",  # Optional[Literal["image", "pixel"]]
    iterator_options: Optional[dict] = None,
) -> NWBFile:

    iterator_options = iterator_options or dict()

    # Set the defaults and required infrastructure
    metadata_copy = deepcopy(metadata)
    default_metadata = _get_default_segmentation_metadata()
    metadata_copy = dict_deep_update(default_metadata, metadata_copy, append_list=False)

    image_segmentation_metadata = metadata_copy["Ophys"]["ImageSegmentation"]
    plane_segmentation_name = (
        plane_segmentation_name
        or default_metadata["Ophys"]["ImageSegmentation"]["plane_segmentations"][default_plane_segmentation_index][
            "name"
        ]
    )

    plane_segmentation_metadata = next(
        (
            plane_segmentation_metadata
            for plane_segmentation_metadata in image_segmentation_metadata["plane_segmentations"]
            if plane_segmentation_metadata["name"] == plane_segmentation_name
        ),
        None,
    )
    if plane_segmentation_metadata is None:
        raise ValueError(
            f"Metadata for Plane Segmentation '{plane_segmentation_name}' not found in metadata['Ophys']['ImageSegmentation']['plane_segmentations']."
        )

    imaging_plane_name = plane_segmentation_metadata["imaging_plane"]
    add_imaging_plane_to_nwbfile(nwbfile=nwbfile, metadata=metadata_copy, imaging_plane_name=imaging_plane_name)
    add_image_segmentation_to_nwbfile(nwbfile=nwbfile, metadata=metadata_copy)

    ophys = get_module(nwbfile, "ophys")
    image_segmentation_name = image_segmentation_metadata["name"]
    image_segmentation = ophys.get_data_interface(image_segmentation_name)

    # Check if the plane segmentation already exists in the image segmentation
    if plane_segmentation_name not in image_segmentation.plane_segmentations:
        roi_ids = background_or_roi_ids

        imaging_plane = nwbfile.imaging_planes[imaging_plane_name]
        plane_segmentation_kwargs = deepcopy(plane_segmentation_metadata)
        plane_segmentation_kwargs.update(imaging_plane=imaging_plane)
        if mask_type is None:
            plane_segmentation = PlaneSegmentation(id=roi_ids, **plane_segmentation_kwargs)
        elif mask_type == "image":
            plane_segmentation = PlaneSegmentation(id=roi_ids, **plane_segmentation_kwargs)
            plane_segmentation.add_column(
                name="image_mask",
                description="Image masks for each ROI.",
                data=image_or_pixel_masks.T,
            )
        elif mask_type == "pixel" or mask_type == "voxel":
            pixel_masks = image_or_pixel_masks
            num_pixel_dims = pixel_masks[0].shape[1]

            assert num_pixel_dims in [3, 4], (
                "The segmentation extractor returned a pixel mask that is not 3- or 4- dimensional! "
                "Please open a ticket with https://github.com/catalystneuro/roiextractors/issues"
            )
            if mask_type == "pixel" and num_pixel_dims == 4:
                warnings.warn(
                    "Specified mask_type='pixel', but ROIExtractors returned 4-dimensional masks. "
                    "Using mask_type='voxel' instead."
                )
                mask_type = "voxel"
            if mask_type == "voxel" and num_pixel_dims == 3:
                warnings.warn(
                    "Specified mask_type='voxel', but ROIExtractors returned 3-dimensional masks. "
                    "Using mask_type='pixel' instead."
                )
                mask_type = "pixel"

            mask_type_kwarg = f"{mask_type}_mask"
            plane_segmentation = PlaneSegmentation(**plane_segmentation_kwargs)

            for roi_id, pixel_mask in zip(roi_ids, pixel_masks):
                plane_segmentation.add_roi(**{"id": roi_id, mask_type_kwarg: [tuple(x) for x in pixel_mask]})

        if include_roi_centroids:
            # ROIExtractors uses height x width x (depth), but NWB uses width x height x depth
            plane_segmentation.add_column(
                name="ROICentroids",
                description="The x, y, (z) centroids of each ROI.",
                data=roi_locations,
            )

        if include_roi_acceptance:
            plane_segmentation.add_column(
                name="Accepted",
                description="1 if ROI was accepted or 0 if rejected as a cell during segmentation operation.",
                data=accepted_ids,
            )
            plane_segmentation.add_column(
                name="Rejected",
                description="1 if ROI was rejected or 0 if accepted as a cell during segmentation operation.",
                data=rejected_ids,
            )

        image_segmentation.add_plane_segmentation(plane_segmentations=[plane_segmentation])
    return nwbfile


def add_background_plane_segmentation_to_nwbfile(
    segmentation_extractor: SegmentationExtractor,
    nwbfile: NWBFile,
    metadata: Optional[dict],
    background_plane_segmentation_name: Optional[str] = None,
    mask_type: Optional[str] = "image",  # Optional[Literal["image", "pixel"]]
    iterator_options: Optional[dict] = None,
    compression_options: Optional[dict] = None,  # TODO: remove completely after 10/1/2024
) -> NWBFile:
    """
    Add background plane segmentation data from a SegmentationExtractor object to an NWBFile.

    Parameters
    ----------
    segmentation_extractor : SegmentationExtractor
        The extractor object containing background segmentation data.
    nwbfile : NWBFile
        The NWB file to which the background plane segmentation will be added.
    metadata : dict, optional
        Metadata for the NWBFile, by default None.
    background_plane_segmentation_name : str, optional
        The name of the background PlaneSegmentation object to be added, by default None.
    mask_type : str, optional
        Type of mask to use for segmentation; options are "image", "pixel", or "voxel", by default "image".
    iterator_options : dict, optional
        Options for iterating over the segmentation data, by default None.
    compression_options : dict, optional
        Deprecated: options for compression; will be removed after 2024-10-01, by default None.

    Returns
    -------
    NWBFile
        The NWBFile with the added background plane segmentation data.
    """
    # TODO: remove completely after 10/1/2024
    if compression_options is not None:
        warnings.warn(
            message=(
                "Specifying compression methods and their options at the level of tool functions has been deprecated. "
                "Please use the `configure_backend` tool function for this purpose."
            ),
            category=DeprecationWarning,
            stacklevel=2,
        )

    default_plane_segmentation_index = 1
    background_ids = segmentation_extractor.get_background_ids()
    if mask_type == "image":
        image_or_pixel_masks = segmentation_extractor.get_background_image_masks()
    elif mask_type == "pixel" or mask_type == "voxel":
        image_or_pixel_masks = segmentation_extractor.get_background_pixel_masks()
    elif mask_type is None:
        image_or_pixel_masks = None
    else:
        raise AssertionError(
            "Keyword argument 'mask_type' must be one of either 'image', 'pixel', 'voxel', "
            f"or None (to not write any masks)! Received '{mask_type}'."
        )
    nwbfile = _add_plane_segmentation(
        background_or_roi_ids=background_ids,
        image_or_pixel_masks=image_or_pixel_masks,
        default_plane_segmentation_index=default_plane_segmentation_index,
        nwbfile=nwbfile,
        metadata=metadata,
        plane_segmentation_name=background_plane_segmentation_name,
        mask_type=mask_type,
        iterator_options=iterator_options,
    )
    return nwbfile


def add_fluorescence_traces_to_nwbfile(
    segmentation_extractor: SegmentationExtractor,
    nwbfile: NWBFile,
    metadata: Optional[dict],
    plane_segmentation_name: Optional[str] = None,
    include_background_segmentation: bool = False,
    iterator_options: Optional[dict] = None,
    compression_options: Optional[dict] = None,  # TODO: remove completely after 10/1/2024
) -> NWBFile:
    """
    Adds the fluorescence traces specified by the metadata to the nwb file.
    The fluorescence traces that are added are the one located in metadata["Ophys"]["Fluorescence"].
    The df/F traces that are added are the one located in metadata["Ophys"]["DfOverF"].

    Parameters
    ----------
    segmentation_extractor : SegmentationExtractor
        The segmentation extractor to get the traces from.
    nwbfile : NWBFile
        The nwbfile to add the fluorescence traces to.
    metadata : dict
        The metadata for the fluorescence traces.
    plane_segmentation_name : str, optional
        The name of the plane segmentation that identifies which plane to add the fluorescence traces to.
    include_background_segmentation : bool, default: False
        Whether to include the background plane segmentation and fluorescence traces in the NWB file. If False,
        neuropil traces are included in the main plane segmentation rather than the background plane segmentation.
    iterator_options : dict, optional

    Returns
    -------
    NWBFile
        The nwbfile passed as an input with the fluorescence traces added.
    """
    # TODO: remove completely after 10/1/2024
    if compression_options is not None:
        warnings.warn(
            message=(
                "Specifying compression methods and their options at the level of tool functions has been deprecated. "
                "Please use the `configure_backend` tool function for this purpose."
            ),
            category=DeprecationWarning,
            stacklevel=2,
        )

    default_plane_segmentation_index = 0

    traces_to_add = segmentation_extractor.get_traces_dict()
    # Filter empty data and background traces
    traces_to_add = {
        trace_name: trace for trace_name, trace in traces_to_add.items() if trace is not None and trace.size != 0
    }
    if include_background_segmentation:
        traces_to_add.pop("neuropil")
    if not traces_to_add:
        return nwbfile

    roi_ids = segmentation_extractor.get_roi_ids()
    nwbfile = _add_fluorescence_traces_to_nwbfile(
        segmentation_extractor=segmentation_extractor,
        traces_to_add=traces_to_add,
        background_or_roi_ids=roi_ids,
        nwbfile=nwbfile,
        metadata=metadata,
        default_plane_segmentation_index=default_plane_segmentation_index,
        plane_segmentation_name=plane_segmentation_name,
        iterator_options=iterator_options,
    )
    return nwbfile


def _add_fluorescence_traces_to_nwbfile(
    segmentation_extractor: SegmentationExtractor,
    traces_to_add: dict,
    background_or_roi_ids: list,
    nwbfile: NWBFile,
    metadata: Optional[dict],
    default_plane_segmentation_index: int,
    plane_segmentation_name: Optional[str] = None,
    iterator_options: Optional[dict] = None,
):
    iterator_options = iterator_options or dict()

    # Set the defaults and required infrastructure
    metadata_copy = deepcopy(metadata)
    default_metadata = _get_default_segmentation_metadata()
    metadata_copy = dict_deep_update(default_metadata, metadata_copy, append_list=False)

    plane_segmentation_name = (
        plane_segmentation_name
        or default_metadata["Ophys"]["ImageSegmentation"]["plane_segmentations"][default_plane_segmentation_index][
            "name"
        ]
    )
    # df/F metadata
    df_over_f_metadata = metadata_copy["Ophys"]["DfOverF"]
    df_over_f_name = df_over_f_metadata["name"]

    # Fluorescence traces metadata
    fluorescence_metadata = metadata_copy["Ophys"]["Fluorescence"]
    fluorescence_name = fluorescence_metadata["name"]

    # Create a reference for ROIs from the plane segmentation
    roi_table_region = _create_roi_table_region(
        segmentation_extractor=segmentation_extractor,
        background_or_roi_ids=background_or_roi_ids,
        nwbfile=nwbfile,
        metadata=metadata_copy,
        plane_segmentation_name=plane_segmentation_name,
    )

    roi_response_series_kwargs = dict(rois=roi_table_region, unit="n.a.")

    # Add timestamps or rate
    if segmentation_extractor.has_time_vector():
        timestamps = segmentation_extractor.frame_to_time(np.arange(segmentation_extractor.get_num_frames()))
        estimated_rate = calculate_regular_series_rate(series=timestamps)
        if estimated_rate:
            roi_response_series_kwargs.update(starting_time=timestamps[0], rate=estimated_rate)
        else:
            roi_response_series_kwargs.update(timestamps=timestamps, rate=None)
    else:
        rate = float(segmentation_extractor.get_sampling_frequency())
        roi_response_series_kwargs.update(rate=rate)

    trace_to_data_interface = defaultdict()
    traces_to_add_to_fluorescence_data_interface = [
        trace_name for trace_name in traces_to_add.keys() if trace_name != "dff"
    ]
    if traces_to_add_to_fluorescence_data_interface:
        fluorescence_data_interface = _get_segmentation_data_interface(
            nwbfile=nwbfile, data_interface_name=fluorescence_name
        )
        trace_to_data_interface.default_factory = lambda: fluorescence_data_interface

    if "dff" in traces_to_add:
        df_over_f_data_interface = _get_segmentation_data_interface(nwbfile=nwbfile, data_interface_name=df_over_f_name)
        trace_to_data_interface.update(dff=df_over_f_data_interface)

    for trace_name, trace in traces_to_add.items():
        # Decide which data interface to use based on the trace name
        data_interface = trace_to_data_interface[trace_name]
        data_interface_metadata = df_over_f_metadata if isinstance(data_interface, DfOverF) else fluorescence_metadata
        # Extract the response series metadata
        # the name of the trace is retrieved from the metadata, no need to override it here
        # trace_name = "RoiResponseSeries" if trace_name in ["raw", "dff"] else trace_name.capitalize()
        assert plane_segmentation_name in data_interface_metadata, (
            f"Plane segmentation '{plane_segmentation_name}' not found in " f"{data_interface_metadata} metadata."
        )
        trace_metadata = data_interface_metadata[plane_segmentation_name][trace_name]
        if trace_metadata is None:
            raise ValueError(f"Metadata for '{trace_name}' trace not found in {data_interface_metadata}.")

        if trace_metadata["name"] in data_interface.roi_response_series:
            continue
        # Pop the rate from the metadata if irregular time series
        if "timestamps" in roi_response_series_kwargs and "rate" in trace_metadata:
            trace_metadata.pop("rate")

        # Build the roi response series
        roi_response_series_kwargs.update(
            data=SliceableDataChunkIterator(trace, **iterator_options),
            rois=roi_table_region,
            **trace_metadata,
        )
        roi_response_series = RoiResponseSeries(**roi_response_series_kwargs)

        # Add trace to the data interface
        data_interface.add_roi_response_series(roi_response_series)

    return nwbfile


def _create_roi_table_region(
    segmentation_extractor: SegmentationExtractor,
    background_or_roi_ids: list,
    nwbfile: NWBFile,
    metadata: dict,
    plane_segmentation_name: Optional[str] = None,
):
    """Private method to create ROI table region.

    Parameters
    ----------
    segmentation_extractor : SegmentationExtractor
        The segmentation extractor to get the results from.
    nwbfile : NWBFile
        The NWBFile to add the plane segmentation to.
    metadata : dict, optional
        The metadata for the plane segmentation.
    plane_segmentation_name : str, optional
        The name of the plane segmentation that identifies which plane to add the ROI table region to.
    """
    image_segmentation_metadata = metadata["Ophys"]["ImageSegmentation"]

    add_plane_segmentation_to_nwbfile(
        segmentation_extractor=segmentation_extractor,
        nwbfile=nwbfile,
        metadata=metadata,
        plane_segmentation_name=plane_segmentation_name,
    )

    image_segmentation_name = image_segmentation_metadata["name"]
    ophys = get_module(nwbfile, "ophys")
    image_segmentation = ophys.get_data_interface(image_segmentation_name)

    # Get plane segmentation from the image segmentation
    plane_segmentation = image_segmentation.plane_segmentations[plane_segmentation_name]

    # Create a reference for ROIs from the plane segmentation
    id_list = list(plane_segmentation.id)

    imaging_plane_name = plane_segmentation.imaging_plane.name
    roi_table_region = plane_segmentation.create_roi_table_region(
        region=[id_list.index(id) for id in background_or_roi_ids],
        description=f"The ROIs for {imaging_plane_name}.",
    )

    return roi_table_region


def _get_segmentation_data_interface(nwbfile: NWBFile, data_interface_name: str):
    """Private method to get the container for the segmentation data.
    If the container does not exist, it is created."""
    ophys = get_module(nwbfile, "ophys")

    if data_interface_name in ophys.data_interfaces:
        return ophys.get(data_interface_name)

    if data_interface_name == "DfOverF":
        data_interface = DfOverF(name=data_interface_name)
    else:
        data_interface = Fluorescence(name=data_interface_name)

    # Add the data interface to the ophys module
    ophys.add(data_interface)

    return data_interface


def add_background_fluorescence_traces_to_nwbfile(
    segmentation_extractor: SegmentationExtractor,
    nwbfile: NWBFile,
    metadata: Optional[dict],
    background_plane_segmentation_name: Optional[str] = None,
    iterator_options: Optional[dict] = None,
    compression_options: Optional[dict] = None,  # TODO: remove completely after 10/1/2024
) -> NWBFile:
    """
    Adds the fluorescence traces specified by the metadata to the nwb file.
    The fluorescence traces that are added are the one located in metadata["Ophys"]["Fluorescence"].
    The df/F traces that are added are the one located in metadata["Ophys"]["DfOverF"].

    Parameters
    ----------
    segmentation_extractor : SegmentationExtractor
        The segmentation extractor to get the traces from.
    nwbfile : NWBFile
        The nwbfile to add the fluorescence traces to.
    metadata : dict
        The metadata for the fluorescence traces.
    plane_segmentation_name : str, optional
        The name of the plane segmentation that identifies which plane to add the fluorescence traces to.
    iterator_options : dict, optional

    Returns
    -------
    NWBFile
        The nwbfile passed as an input with the fluorescence traces added.
    """
    # TODO: remove completely after 10/1/2024
    if compression_options is not None:
        warnings.warn(
            message=(
                "Specifying compression methods and their options at the level of tool functions has been deprecated. "
                "Please use the `configure_backend` tool function for this purpose."
            ),
            category=DeprecationWarning,
            stacklevel=2,
        )

    default_plane_segmentation_index = 1

    traces_to_add = segmentation_extractor.get_traces_dict()
    # Filter empty data and background traces
    traces_to_add = {
        trace_name: trace
        for trace_name, trace in traces_to_add.items()
        if trace is not None and trace.size != 0 and trace_name == "neuropil"
    }
    if not traces_to_add:
        return nwbfile

    background_ids = segmentation_extractor.get_background_ids()
    nwbfile = _add_fluorescence_traces_to_nwbfile(
        segmentation_extractor=segmentation_extractor,
        traces_to_add=traces_to_add,
        background_or_roi_ids=background_ids,
        nwbfile=nwbfile,
        metadata=metadata,
        default_plane_segmentation_index=default_plane_segmentation_index,
        plane_segmentation_name=background_plane_segmentation_name,
        iterator_options=iterator_options,
    )
    return nwbfile


def add_summary_images_to_nwbfile(
    nwbfile: NWBFile,
    segmentation_extractor: SegmentationExtractor,
    metadata: Optional[dict] = None,
    plane_segmentation_name: Optional[str] = None,
) -> NWBFile:
    """
    Adds summary images (i.e. mean and correlation) to the nwbfile using an image container object pynwb.Image

    Parameters
    ----------
    nwbfile : NWBFile
        An previously defined -in memory- NWBFile.
    segmentation_extractor : SegmentationExtractor
        A segmentation extractor object from roiextractors.
    metadata: dict, optional
        The metadata for the summary images is located in metadata["Ophys"]["SegmentationImages"].
    plane_segmentation_name: str, optional
        The name of the plane segmentation that identifies which images to add.

    Returns
    -------
    NWBFile
        The nwbfile passed as an input with the summary images added.
    """
    metadata = metadata or dict()

    # Set the defaults and required infrastructure
    metadata_copy = deepcopy(metadata)
    default_metadata = _get_default_segmentation_metadata()
    metadata_copy = dict_deep_update(default_metadata, metadata_copy, append_list=False)

    segmentation_images_metadata = metadata_copy["Ophys"]["SegmentationImages"]
    images_container_name = segmentation_images_metadata["name"]

    images_dict = segmentation_extractor.get_images_dict()
    images_to_add = {img_name: img for img_name, img in images_dict.items() if img is not None}
    if not images_to_add:
        return nwbfile

    ophys = get_module(nwbfile=nwbfile, name="ophys", description="contains optical physiology processed data")

    image_collection_does_not_exist = images_container_name not in ophys.data_interfaces
    if image_collection_does_not_exist:
        ophys.add(Images(name=images_container_name, description=segmentation_images_metadata["description"]))
    image_collection = ophys.data_interfaces[images_container_name]

    plane_segmentation_name = (
        plane_segmentation_name or default_metadata["Ophys"]["ImageSegmentation"]["plane_segmentations"][0]["name"]
    )
    assert (
        plane_segmentation_name in segmentation_images_metadata
    ), f"Plane segmentation '{plane_segmentation_name}' not found in metadata['Ophys']['SegmentationImages']"
    images_metadata = segmentation_images_metadata[plane_segmentation_name]

    for img_name, img in images_to_add.items():
        image_kwargs = dict(name=img_name, data=img.T)
        image_metadata = images_metadata.get(img_name, None)
        if image_metadata is not None:
            image_kwargs.update(image_metadata)

        # Note that nwb uses the conversion width x height (columns, rows) and roiextractors uses the transpose
        image_collection.add_image(GrayscaleImage(**image_kwargs))

    return nwbfile


def add_segmentation_to_nwbfile(
    segmentation_extractor: SegmentationExtractor,
    nwbfile: NWBFile,
    metadata: Optional[dict] = None,
    plane_segmentation_name: Optional[str] = None,
    background_plane_segmentation_name: Optional[str] = None,
    include_background_segmentation: bool = False,
    include_roi_centroids: bool = True,
    include_roi_acceptance: bool = True,
    mask_type: Optional[str] = "image",  # Literal["image", "pixel"]
    iterator_options: Optional[dict] = None,
) -> NWBFile:
    """
    Add segmentation data from a SegmentationExtractor object to an NWBFile.

    Parameters
    ----------
    segmentation_extractor : SegmentationExtractor
        The extractor object containing segmentation data.
    nwbfile : NWBFile
        The NWB file where the segmentation data will be added.
    metadata : dict, optional
        Metadata for the NWBFile, by default None.
    plane_segmentation_name : str, optional
        The name of the PlaneSegmentation object to be added, by default None.
    background_plane_segmentation_name : str, optional
        The name of the background PlaneSegmentation, if any, by default None.
    include_background_segmentation : bool, optional
        If True, includes background plane segmentation, by default False.
    include_roi_centroids : bool, optional
        If True, includes the centroids of the regions of interest (ROIs), by default True.
    include_roi_acceptance : bool, optional
        If True, includes the acceptance status of ROIs, by default True.
    mask_type : str, optional
        Type of mask to use for segmentation; can be either "image" or "pixel", by default "image".
    iterator_options : dict, optional
        Options for iterating over the data, by default None.


    Returns
    -------
    NWBFile
        The NWBFile with the added segmentation data.
    """

    # Add device:
    add_devices_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

    # Add PlaneSegmentation:
    add_plane_segmentation_to_nwbfile(
        segmentation_extractor=segmentation_extractor,
        nwbfile=nwbfile,
        metadata=metadata,
        plane_segmentation_name=plane_segmentation_name,
        include_roi_centroids=include_roi_centroids,
        include_roi_acceptance=include_roi_acceptance,
        mask_type=mask_type,
        iterator_options=iterator_options,
    )
    if include_background_segmentation:
        add_background_plane_segmentation_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
            background_plane_segmentation_name=background_plane_segmentation_name,
            mask_type=mask_type,
            iterator_options=iterator_options,
        )

    # Add fluorescence traces:
    add_fluorescence_traces_to_nwbfile(
        segmentation_extractor=segmentation_extractor,
        nwbfile=nwbfile,
        metadata=metadata,
        plane_segmentation_name=plane_segmentation_name,
        include_background_segmentation=include_background_segmentation,
        iterator_options=iterator_options,
    )

    if include_background_segmentation:
        add_background_fluorescence_traces_to_nwbfile(
            segmentation_extractor=segmentation_extractor,
            nwbfile=nwbfile,
            metadata=metadata,
            background_plane_segmentation_name=background_plane_segmentation_name,
            iterator_options=iterator_options,
        )

    # Adding summary images (mean and correlation)
    add_summary_images_to_nwbfile(
        nwbfile=nwbfile,
        segmentation_extractor=segmentation_extractor,
        metadata=metadata,
        plane_segmentation_name=plane_segmentation_name,
    )

    return nwbfile


def write_segmentation_to_nwbfile(
    segmentation_extractor: SegmentationExtractor,
    nwbfile_path: Optional[FilePath] = None,
    nwbfile: Optional[NWBFile] = None,
    metadata: Optional[dict] = None,
    overwrite: bool = False,
    verbose: bool = False,
    include_background_segmentation: bool = False,
    include_roi_centroids: bool = True,
    include_roi_acceptance: bool = True,
    mask_type: Optional[str] = "image",  # Literal["image", "pixel"]
    iterator_options: Optional[dict] = None,
) -> NWBFile:
    """
    Primary method for writing an SegmentationExtractor object to an NWBFile.

    Parameters
    ----------
    segmentation_extractor: SegmentationExtractor
        The segmentation extractor object to be written to nwb
    nwbfile_path: FilePath
        Path for where to write or load (if overwrite=False) the NWBFile.
        If specified, the context will always write to this location.
    nwbfile: NWBFile, optional
        If passed, this function will fill the relevant fields within the NWBFile object.
        E.g., calling::

            write_recording(recording=my_recording_extractor, nwbfile=my_nwbfile)

        will result in the appropriate changes to the my_nwbfile object.
        If neither 'nwbfile_path' nor 'nwbfile' are specified, an NWBFile object will be automatically generated
        and returned by the function.
    metadata: dict, optional
        Metadata dictionary with information used to create the NWBFile when one does not exist or overwrite=True.
    overwrite: bool, default: False
        Whether to overwrite the NWBFile if one exists at the nwbfile_path.
    verbose: bool, default: True
        If 'nwbfile_path' is specified, informs user after a successful write operation.
    include_background_segmentation : bool, default: False
        Whether to include the background plane segmentation and fluorescence traces in the NWB file. If False,
        neuropil traces are included in the main plane segmentation rather than the background plane segmentation.
    include_roi_centroids : bool, default: True
        Whether to include the ROI centroids on the PlaneSegmentation table.
        If there are a very large number of ROIs (such as in whole-brain recordings), you may wish to disable this for
        faster write speeds.
    include_roi_acceptance : bool, default: True
        Whether to include if the detected ROI was 'accepted' or 'rejected'.
        If there are a very large number of ROIs (such as in whole-brain recordings), you may wish to disable this for
        faster write speeds.
    mask_type : str, default: 'image'
        There are three types of ROI masks in NWB, 'image', 'pixel', and 'voxel'.

        * 'image' masks have the same shape as the reference images the segmentation was applied to, and weight each pixel
          by its contribution to the ROI (typically boolean, with 0 meaning 'not in the ROI').
        * 'pixel' masks are instead indexed by ROI, with the data at each index being the shape of the image by the number
          of pixels in each ROI.
        * 'voxel' masks are instead indexed by ROI, with the data at each index being the shape of the volume by the number
          of voxels in each ROI.

        Specify your choice between these two as mask_type='image', 'pixel', 'voxel', or None.
        If None, the mask information is not written to the NWB file.
    iterator_options: dict, optional
        A dictionary with options for the internal iterators that process the data.
    """
    assert (
        nwbfile_path is None or nwbfile is None
    ), "Either pass a nwbfile_path location, or nwbfile object, but not both!"

    iterator_options = iterator_options or dict()

    # parse metadata correctly considering the MultiSegmentationExtractor function:
    if isinstance(segmentation_extractor, MultiSegmentationExtractor):
        segmentation_extractors = segmentation_extractor.segmentations
        if metadata is not None:
            assert isinstance(metadata, list), (
                "For MultiSegmentationExtractor enter 'metadata' as a list of " "SegmentationExtractor metadata"
            )
            assert len(metadata) == len(segmentation_extractor), (
                "The 'metadata' argument should be a list with the same "
                "number of elements as the segmentations in the "
                "MultiSegmentationExtractor"
            )
    else:
        segmentation_extractors = [segmentation_extractor]
        if metadata is not None and not isinstance(metadata, list):
            metadata = [metadata]
    metadata_base_list = [
        get_nwb_segmentation_metadata(segmentation_extractor) for segmentation_extractor in segmentation_extractors
    ]

    # updating base metadata with new:
    for num, data in enumerate(metadata_base_list):
        metadata_input = metadata[num] if metadata else {}
        metadata_base_list[num] = dict_deep_update(metadata_base_list[num], metadata_input, append_list=False)
    metadata_base_common = metadata_base_list[0]

    with make_or_load_nwbfile(
        nwbfile_path=nwbfile_path, nwbfile=nwbfile, metadata=metadata_base_common, overwrite=overwrite, verbose=verbose
    ) as nwbfile_out:
        _ = get_module(nwbfile=nwbfile_out, name="ophys", description="contains optical physiology processed data")
        for plane_no_loop, (segmentation_extractor, metadata) in enumerate(
            zip(segmentation_extractors, metadata_base_list)
        ):
            add_segmentation_to_nwbfile(
                segmentation_extractor=segmentation_extractor,
                nwbfile=nwbfile_out,
                metadata=metadata,
                plane_num=plane_no_loop,
                include_background_segmentation=include_background_segmentation,
                include_roi_centroids=include_roi_centroids,
                include_roi_acceptance=include_roi_acceptance,
                mask_type=mask_type,
                iterator_options=iterator_options,
            )

    return nwbfile_out
