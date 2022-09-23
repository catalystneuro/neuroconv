"""Authors: Heberto Mayorquin, Saksham Sharda, Alessio Buccino and Szonja Weigl."""
from collections import defaultdict
from warnings import warn
from typing import Optional
from copy import deepcopy

import psutil
import numpy as np
from roiextractors import ImagingExtractor, SegmentationExtractor, MultiSegmentationExtractor
from pynwb import NWBFile
from pynwb.base import Images
from pynwb.image import GrayscaleImage
from pynwb.device import Device
from pynwb.ophys import (
    ImageSegmentation,
    ImagingPlane,
    PlaneSegmentation,
    Fluorescence,
    OpticalChannel,
    TwoPhotonSeries,
    RoiResponseSeries,
    DfOverF,
)

# from hdmf.commmon import VectorData
from hdmf.data_utils import DataChunkIterator
from hdmf.backends.hdf5.h5_utils import H5DataIO

from .imagingextractordatachunkiterator import ImagingExtractorDataChunkIterator
from ..hdmf import SliceableDataChunkIterator
from ..nwb_helpers import get_default_nwbfile_metadata, make_or_load_nwbfile, get_module
from ...utils import OptionalFilePathType, dict_deep_update, calculate_regular_series_rate


def get_default_ophys_metadata():
    """Fill default metadata for optical physiology."""
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

    default_fluorescence_roi_response_series = dict(
        name="RoiResponseSeries", description="Array of raw fluorescence traces.", unit="n.a."
    )

    default_fluorescence = dict(
        name="Fluorescence",
        roi_response_series=[default_fluorescence_roi_response_series],
    )

    default_dff_roi_response_series = dict(name="RoiResponseSeries", description="Array of df/F traces.", unit="n.a.")

    default_df_over_f = dict(
        name="DfOverF",
        roi_response_series=[default_dff_roi_response_series],
    )

    default_two_photon_series = dict(
        name="TwoPhotonSeries",
        description="Imaging data from two-photon excitation microscopy.",
        unit="n.a.",
    )

    default_image_segmentation = dict(
        name="ImageSegmentation",
        plane_segmentations=[
            dict(
                name="PlaneSegmentation",
                description="Segmented ROIs",
            )
        ],
    )

    metadata.update(
        Ophys=dict(
            Device=[default_device],
            Fluorescence=default_fluorescence,
            DfOverF=default_df_over_f,
            ImageSegmentation=default_image_segmentation,
            ImagingPlane=[default_imaging_plane],
            TwoPhotonSeries=[default_two_photon_series],
        ),
    )

    return metadata


def get_nwb_imaging_metadata(imgextractor: ImagingExtractor):
    """
    Convert metadata from the ImagingExtractor into nwb specific metadata.

    Parameters
    ----------
    imgextractor: ImagingExtractor
    """
    metadata = get_default_ophys_metadata()

    channel_name_list = imgextractor.get_channel_names() or (
        ["OpticalChannel"]
        if imgextractor.get_num_channels() == 1
        else [f"OpticalChannel{idx}" for idx in range(imgextractor.get_num_channels())]
    )
    for index, channel_name in enumerate(channel_name_list):
        if index == 0:
            metadata["Ophys"]["ImagingPlane"][0]["optical_channel"][index]["name"] = channel_name
        else:
            metadata["Ophys"]["ImagingPlane"][0]["optical_channel"].append(
                dict(
                    name=channel_name,
                    emission_lambda=np.nan,
                    description="An optical channel of the microscope.",
                )
            )
    # set imaging plane rate:
    rate = np.nan if imgextractor.get_sampling_frequency() is None else float(imgextractor.get_sampling_frequency())

    # adding imaging_rate:
    metadata["Ophys"]["ImagingPlane"][0].update(imaging_rate=rate)
    # TwoPhotonSeries update:
    metadata["Ophys"]["TwoPhotonSeries"][0].update(dimension=list(imgextractor.get_image_size()), rate=rate)

    plane_name = metadata["Ophys"]["ImagingPlane"][0]["name"]
    metadata["Ophys"]["TwoPhotonSeries"][0]["imaging_plane"] = plane_name

    # remove what Segmentation extractor will input:
    _ = metadata["Ophys"].pop("ImageSegmentation")
    _ = metadata["Ophys"].pop("Fluorescence")
    _ = metadata["Ophys"].pop("DfOverF")
    return metadata


def add_devices(nwbfile: NWBFile, metadata: dict) -> NWBFile:
    """
    Add optical physiology devices from metadata.
    The metadata concerning the optical physiology should be stored in metadata["Ophys]["Device"]
    This function handles both a text specification of the device to be built and an actual pynwb.Device object.

    """
    metadata_copy = deepcopy(metadata)
    default_metadata = get_default_ophys_metadata()
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


def add_imaging_plane(nwbfile: NWBFile, metadata: dict, imaging_plane_index: int = 0) -> NWBFile:
    """
    Adds the imaging plane specificied by the metadata to the nwb file.
    The imaging plane that is added is the one located in metadata["Ophys"]["ImagingPlane"][imaging_plane_index]

    Parameters
    ----------
    nwbfile : NWBFile
        An previously defined -in memory- NWBFile.
    metadata : dict
        The metadata in the nwb conversion tools format.
    imaging_plane_index : int, optional
        The metadata in the nwb conversion tools format is a list of the different imaging planes to add.
        Specificy which element of the list with this parameter, by default 0

    Returns
    -------
    NWBFile
        The nwbfile passed as an input with the imaging plane added.
    """

    # Set the defaults and required infrastructure
    metadata_copy = deepcopy(metadata)
    default_metadata = get_default_ophys_metadata()
    metadata_copy = dict_deep_update(default_metadata, metadata_copy, append_list=False)
    add_devices(nwbfile=nwbfile, metadata=metadata_copy)

    imaging_plane_metadata = metadata_copy["Ophys"]["ImagingPlane"][imaging_plane_index]
    imaging_plane_name = imaging_plane_metadata["name"]
    existing_imaging_planes = nwbfile.imaging_planes

    if imaging_plane_name not in existing_imaging_planes:
        imaging_plane = _create_imaging_plane_from_metadata(
            nwbfile=nwbfile, imaging_plane_metadata=imaging_plane_metadata
        )
        nwbfile.add_imaging_plane(imaging_plane)

    return nwbfile


def add_image_segmentation(nwbfile: NWBFile, metadata: dict) -> NWBFile:
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
        The nwbfile passed as an input with the image segmentation added.
    """
    # Set the defaults and required infrastructure
    metadata_copy = deepcopy(metadata)
    default_metadata = get_default_ophys_metadata()
    metadata_copy = dict_deep_update(default_metadata, metadata_copy, append_list=False)

    image_segmentation_metadata = metadata_copy["Ophys"]["ImageSegmentation"]
    image_segmentation_name = image_segmentation_metadata["name"]

    ophys = get_module(nwbfile, "ophys")

    # Check if the image segmentation already exists in the NWB file
    if image_segmentation_name not in ophys.data_interfaces:
        ophys.add(ImageSegmentation(name=image_segmentation_name))

    return nwbfile


def add_two_photon_series(
    imaging: ImagingExtractor,
    nwbfile: NWBFile,
    metadata: dict,
    two_photon_series_index: int = 0,
    iterator_type: Optional[str] = "v2",
    iterator_options: Optional[dict] = None,
    use_times=False,  # TODO: to be removed
    buffer_size: Optional[int] = None,  # TODO: to be removed
):
    """
    Auxiliary static method for nwbextractor.

    Adds two photon series from imaging object as TwoPhotonSeries to nwbfile object.
    """
    if use_times:
        warn("Keyword argument 'use_times' is deprecated and will be removed on or after August 1st, 2022.")
    if buffer_size:
        warn(
            "Keyword argument 'buffer_size' is deprecated and will be removed on or after September 1st, 2022."
            "Specify as a key in the new 'iterator_options' dictionary instead."
        )

    iterator_options = iterator_options or dict()

    metadata_copy = deepcopy(metadata)
    metadata_copy = dict_deep_update(get_nwb_imaging_metadata(imaging), metadata_copy, append_list=False)

    # Tests if TwoPhotonSeries already exists in acquisition
    two_photon_series_metadata = metadata_copy["Ophys"]["TwoPhotonSeries"][two_photon_series_index]
    two_photon_series_name = two_photon_series_metadata["name"]

    if two_photon_series_name in nwbfile.acquisition:
        warn(f"{two_photon_series_name} already on nwbfile")
        return nwbfile

    # Add the image plane to nwb
    nwbfile = add_imaging_plane(nwbfile=nwbfile, metadata=metadata_copy)
    imaging_plane_name = two_photon_series_metadata["imaging_plane"]
    imaging_plane = nwbfile.get_imaging_plane(name=imaging_plane_name)
    two_photon_series_metadata.update(imaging_plane=imaging_plane)

    # Add the data
    two_p_series_kwargs = two_photon_series_metadata
    frames_to_iterator = _imaging_frames_to_hdmf_iterator(
        imaging=imaging,
        iterator_type=iterator_type,
        iterator_options=iterator_options,
    )
    data = H5DataIO(data=frames_to_iterator, compression=True)
    two_p_series_kwargs.update(data=data)

    # Add dimension
    two_p_series_kwargs.update(dimension=imaging.get_image_size())

    # Add timestamps or rate
    timestamps = imaging.frame_to_time(np.arange(imaging.get_num_frames()))
    rate = calculate_regular_series_rate(series=timestamps)
    if rate:
        two_p_series_kwargs.update(starting_time=timestamps[0], rate=rate)
    else:
        two_p_series_kwargs.update(timestamps=H5DataIO(data=timestamps, compression="gzip"))
        two_p_series_kwargs["rate"] = None

    # Add the TwoPhotonSeries to the nwbfile
    two_photon_series = TwoPhotonSeries(**two_p_series_kwargs)
    nwbfile.add_acquisition(two_photon_series)

    return nwbfile


def check_if_imaging_fits_into_memory(imaging: ImagingExtractor) -> None:
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

    traces_size_in_bytes = num_frames * np.prod(image_size) * element_size_in_bytes
    available_memory_in_bytes = psutil.virtual_memory().available

    if traces_size_in_bytes > available_memory_in_bytes:
        message = (
            f"Memory error, full TwoPhotonSeries data is {round(traces_size_in_bytes/1e9, 2)} GB) but only"
            f"({round(available_memory_in_bytes/1e9, 2)} GB are available! Please use iterator_type='v2'."
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
    iterator_type : str (optional, defaults to 'v2')
        The type of iterator to use.
        'v1' is the original DataChunkIterator of the hdmf data_utils.
        https://hdmf.readthedocs.io/en/stable/hdmf.data_utils.html#hdmf.data_utils.DataChunkIterator
        'v2' is the locally developed ImagingExtractorDataChunkIterator, which offers full control over chunking.
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
        check_if_imaging_fits_into_memory(imaging=imaging)
        return imaging.get_video().transpose((0, 2, 1))

    if iterator_type == "v1":
        if "buffer_size" not in iterator_options:
            iterator_options.update(buffer_size=10)
        return DataChunkIterator(data=data_generator(imaging), **iterator_options)

    return ImagingExtractorDataChunkIterator(imaging_extractor=imaging, **iterator_options)


def write_imaging(
    imaging: ImagingExtractor,
    nwbfile_path: OptionalFilePathType = None,
    nwbfile: Optional[NWBFile] = None,
    metadata: Optional[dict] = None,
    overwrite: bool = False,
    verbose: bool = True,
    iterator_type: Optional[str] = "v2",
    iterator_options: Optional[dict] = None,
    use_times=False,  # TODO: to be removed
    buffer_size: Optional[int] = None,  # TODO: to be removed
):
    """
    Primary method for writing an ImagingExtractor object to an NWBFile.

    Parameters
    ----------
    imaging: ImagingExtractor
        The imaging extractor object to be written to nwb
    nwbfile_path: FilePathType
        Path for where to write or load (if overwrite=False) the NWBFile.
        If specified, the context will always write to this location.
    nwbfile: NWBFile, optional
        If passed, this function will fill the relevant fields within the NWBFile object.
        E.g., calling
            write_recording(recording=my_recording_extractor, nwbfile=my_nwbfile)
        will result in the appropriate changes to the my_nwbfile object.
        If neither 'nwbfile_path' nor 'nwbfile' are specified, an NWBFile object will be automatically generated
        and returned by the function.
    metadata: dict, optional
        Metadata dictionary with information used to create the NWBFile when one does not exist or overwrite=True.
    overwrite: bool, optional
        Whether or not to overwrite the NWBFile if one exists at the nwbfile_path.
        The default is False (append mode).
    verbose: bool, optional
        If 'nwbfile_path' is specified, informs user after a successful write operation.
        The default is True.
    num_chunks: int
        Number of chunks for writing data to file
    iterator_type : str (optional, defaults to 'v2')
        The type of iterator to use.
        'v1' is the original DataChunkIterator of the hdmf data_utils.
        https://hdmf.readthedocs.io/en/stable/hdmf.data_utils.html#hdmf.data_utils.DataChunkIterator
        'v2' is the locally developed ImagingExtractorDataChunkIterator, which offers full control over chunking.
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
    if use_times:
        warn("Keyword argument 'use_times' is deprecated and will be removed on or after August 1st, 2022.")
    if buffer_size:
        warn(
            "Keyword argument 'buffer_size' is deprecated and will be removed on or after September 1st, 2022."
            "Specify as a key in the new 'iterator_options' dictionary instead."
        )

    if metadata is None:
        metadata = dict()
    if hasattr(imaging, "nwb_metadata"):
        metadata = dict_deep_update(imaging.nwb_metadata, metadata, append_list=False)

    with make_or_load_nwbfile(
        nwbfile_path=nwbfile_path, nwbfile=nwbfile, metadata=metadata, overwrite=overwrite, verbose=verbose
    ) as nwbfile_out:
        add_devices(nwbfile=nwbfile_out, metadata=metadata)
        add_two_photon_series(
            imaging=imaging,
            nwbfile=nwbfile_out,
            metadata=metadata,
            iterator_type=iterator_type,
            iterator_options=iterator_options,
        )
    return nwbfile_out


def get_nwb_segmentation_metadata(sgmextractor: SegmentationExtractor):
    """
    Convert metadata from the segmentation into nwb specific metadata.

    Parameters
    ----------
    sgmextractor: SegmentationExtractor
    """
    metadata = get_default_ophys_metadata()
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
    # set roi_response_series rate:
    rate = np.nan if sgmextractor.get_sampling_frequency() is None else sgmextractor.get_sampling_frequency()
    for trace_name, trace_data in sgmextractor.get_traces_dict().items():
        if trace_name == "raw":
            if trace_data is not None:
                metadata["Ophys"]["Fluorescence"]["roi_response_series"][0].update(rate=rate)
            continue
        if trace_data is not None and len(trace_data.shape) != 0:
            metadata["Ophys"]["Fluorescence"]["roi_response_series"].append(
                dict(
                    name=trace_name.capitalize(),
                    description=f"description of {trace_name} traces",
                    rate=rate,
                )
            )
    # adding imaging_rate:
    metadata["Ophys"]["ImagingPlane"][0].update(imaging_rate=rate)
    # remove what imaging extractor will input:
    _ = metadata["Ophys"].pop("TwoPhotonSeries")
    return metadata


def add_plane_segmentation(
    segmentation_extractor: SegmentationExtractor,
    nwbfile: NWBFile,
    metadata: Optional[dict],
    plane_segmentation_index: int = 0,
    include_roi_centroids: bool = True,
    mask_type: Optional[str] = "image",  # Optional[Literal["image", "pixel"]]
    iterator_options: Optional[dict] = None,
    compression_options: Optional[dict] = None,
) -> NWBFile:
    """
    Adds the plane segmentation specified by the metadata to the image segmentation.

    If the plane segmentation already exists in the image segmentation, it is not added again.

    Parameters
    ----------
    segmentation_extractor : SegmentationExtractor
        The segmentation extractor to get the results from.
    nwbfile : NWBFile
        The nwbfile to add the plane segmentation to.
    metadata : dict, optional
        The metadata for the plane segmentation.
    plane_segmentation_index: int, optional
        The index of the plane segmentation to add.
    include_roi_centroids : bool, optional
        Whether or not to include the ROI centroids on the PlaneSegmentation table.
        If there are a very large number of ROIs (such as in whole-brain recordings), you may wish to disable this for
            faster write speeds.
        Defaults to True.
    mask_type : str, optional
        There are two types of ROI masks in NWB: ImageMasks and PixelMasks.
        Image masks have the same shape as the reference images the segmentation was applied to, and weight each pixel
            by its contribution to the ROI (typically boolean, with 0 meaning 'not in the ROI').
        Pixel masks are instead indexed by ROI, with the data at each index being the shape of the image by the number
            of pixels in each ROI.
        Voxel masks are instead indexed by ROI, with the data at each index being the shape of the volume by the number
            of voxels in each ROI.
        Specify your choice between these two as mask_type='image', 'pixel', 'voxel', or None.
        If None, the mask information is not written to the NWB file.
        Defaults to 'image'.
    iterator_options : dict, optional
        The options to use when iterating over the image masks of the segmentation extractor.
    compression_options : dict, optional
        The options to use when compressing the image masks of the segmentation extractor.

    Returns
    -------
    NWBFile
        The nwbfile passed as an input with the plane segmentation added.
    """
    assert mask_type in ["image", "pixel", "voxel", None], (
        "Keyword argument 'mask_type' must be one of either 'image', 'pixel', 'voxel', "
        f"or None (to not write any masks)! Received '{mask_type}'."
    )

    iterator_options = iterator_options or dict()
    compression_options = compression_options or dict(compression="gzip")

    # Set the defaults and required infrastructure
    metadata_copy = deepcopy(metadata)
    default_metadata = get_default_ophys_metadata()
    metadata_copy = dict_deep_update(default_metadata, metadata_copy, append_list=False)

    image_segmentation_metadata = metadata_copy["Ophys"]["ImageSegmentation"]
    plane_segmentation_metadata = image_segmentation_metadata["plane_segmentations"][plane_segmentation_index]
    plane_segmentation_name = plane_segmentation_metadata["name"]

    add_imaging_plane(nwbfile=nwbfile, metadata=metadata_copy, imaging_plane_index=plane_segmentation_index)
    add_image_segmentation(nwbfile=nwbfile, metadata=metadata_copy)

    ophys = get_module(nwbfile, "ophys")
    image_segmentation_name = image_segmentation_metadata["name"]
    image_segmentation = ophys.get_data_interface(image_segmentation_name)

    # Check if the plane segmentation already exists in the image segmentation
    if plane_segmentation_name not in image_segmentation.plane_segmentations:
        roi_ids = segmentation_extractor.get_roi_ids()
        accepted_ids = [int(roi_id in segmentation_extractor.get_accepted_list()) for roi_id in roi_ids]
        rejected_ids = [int(roi_id in segmentation_extractor.get_rejected_list()) for roi_id in roi_ids]

        imaging_plane_metadata = metadata_copy["Ophys"]["ImagingPlane"][plane_segmentation_index]
        imaging_plane_name = imaging_plane_metadata["name"]
        imaging_plane = nwbfile.imaging_planes[imaging_plane_name]

        plane_segmentation_kwargs = dict(**plane_segmentation_metadata, imaging_plane=imaging_plane)
        if mask_type is None:
            plane_segmentation = PlaneSegmentation(id=roi_ids, **plane_segmentation_kwargs)
        elif mask_type == "image":
            plane_segmentation = PlaneSegmentation(id=roi_ids, **plane_segmentation_kwargs)
            plane_segmentation.add_column(
                name="image_mask",
                description="Image masks for each ROI.",
                data=H5DataIO(segmentation_extractor.get_roi_image_masks().T, **compression_options),
            )
        elif mask_type == "pixel" or mask_type == "voxel":
            pixel_masks = segmentation_extractor.get_roi_pixel_masks()
            num_pixel_dims = pixel_masks[0].shape[1]

            assert num_pixel_dims in [3, 4], (
                "The segmentation extractor returned a pixel mask that is not 3- or 4- dimensional! "
                "Please open a ticket with https://github.com/catalystneuro/roiextractors/issues"
            )
            if mask_type == "pixel" and num_pixel_dims == 4:
                warn(
                    "Specified mask_type='pixel', but ROIExtractors returned 4-dimensional masks. "
                    "Using mask_type='voxel' instead."
                )
                mask_type = "voxel"
            if mask_type == "voxel" and num_pixel_dims == 3:
                warn(
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
            tranpose_image_convention = (1, 0) if len(segmentation_extractor.get_image_size()) == 2 else (1, 0, 2)
            roi_locations = segmentation_extractor.get_roi_locations()[tranpose_image_convention, :].T
            plane_segmentation.add_column(
                name="ROICentroids",
                description="The x, y, (z) centroids of each ROI.",
                data=H5DataIO(roi_locations, **compression_options),
            )

        plane_segmentation.add_column(
            name="Accepted",
            description="1 if ROI was accepted or 0 if rejected as a cell during segmentation operation.",
            data=H5DataIO(accepted_ids, **compression_options),
        )
        plane_segmentation.add_column(
            name="Rejected",
            description="1 if ROI was rejected or 0 if accepted as a cell during segmentation operation.",
            data=H5DataIO(rejected_ids, **compression_options),
        )

        image_segmentation.add_plane_segmentation(plane_segmentations=[plane_segmentation])
    return nwbfile


def add_fluorescence_traces(
    segmentation_extractor: SegmentationExtractor,
    nwbfile: NWBFile,
    metadata: Optional[dict],
    plane_index: int = 0,
    iterator_options: Optional[dict] = None,
    compression_options: Optional[dict] = None,
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
    plane_index : int, optional
        The index of the plane to add the fluorescence traces to.

    Returns
    -------
    NWBFile
        The nwbfile passed as an input with the fluorescence traces added.
    """
    iterator_options = iterator_options or dict()
    compression_options = compression_options or dict(compression="gzip")

    # Set the defaults and required infrastructure
    metadata_copy = deepcopy(metadata)
    default_metadata = get_default_ophys_metadata()
    metadata_copy = dict_deep_update(default_metadata, metadata_copy, append_list=False)

    # df/F metadata
    df_over_f_metadata = metadata_copy["Ophys"]["DfOverF"]
    df_over_f_name = df_over_f_metadata["name"]

    # Fluorescence traces metadata
    fluorescence_metadata = metadata_copy["Ophys"]["Fluorescence"]
    fluorescence_name = fluorescence_metadata["name"]

    # Get traces from the segmentation extractor
    traces_to_add = segmentation_extractor.get_traces_dict()

    # Filter empty data
    traces_to_add = {trace_name: trace for trace_name, trace in traces_to_add.items() if trace is not None}
    # Filter all zero data
    traces_to_add = {
        trace_name: trace for trace_name, trace in traces_to_add.items() if any(x != 0 for x in np.ravel(trace))
    }

    # Early return if there is nothing to add
    if not traces_to_add:
        return nwbfile

    # Create a reference for ROIs from the plane segmentation
    roi_table_region = _create_roi_table_region(
        segmentation_extractor=segmentation_extractor,
        nwbfile=nwbfile,
        metadata=metadata_copy,
        plane_index=plane_index,
    )

    roi_response_series_kwargs = dict(rois=roi_table_region, unit="n.a.")

    # Add timestamps or rate
    timestamps = segmentation_extractor.frame_to_time(np.arange(segmentation_extractor.get_num_frames()))
    rate = calculate_regular_series_rate(series=timestamps)
    if rate:
        roi_response_series_kwargs.update(starting_time=timestamps[0], rate=rate)
    else:
        roi_response_series_kwargs.update(timestamps=H5DataIO(data=timestamps, **compression_options))

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
        # Extract the response series metadata
        # The name of the roi_response_series is "RoiResponseSeries" for raw and df/F traces,
        # otherwise it is capitalized trace_name.
        trace_name = "RoiResponseSeries" if trace_name in ["raw", "dff"] else trace_name.capitalize()
        trace_name = trace_name if plane_index == 0 else trace_name + f"_Plane{plane_index}"

        if trace_name in data_interface.roi_response_series:
            continue

        data_interface_metadata = df_over_f_metadata if isinstance(data_interface, DfOverF) else fluorescence_metadata
        response_series_metadata = data_interface_metadata["roi_response_series"]
        trace_metadata = next(
            trace_metadata for trace_metadata in response_series_metadata if trace_name == trace_metadata["name"]
        )
        # Build the roi response series
        roi_response_series_kwargs.update(
            data=H5DataIO(SliceableDataChunkIterator(trace, **iterator_options), **compression_options),
            rois=roi_table_region,
            **trace_metadata,
        )
        roi_response_series = RoiResponseSeries(**roi_response_series_kwargs)

        # Add trace to the data interface
        data_interface.add_roi_response_series(roi_response_series)

    return nwbfile


def _create_roi_table_region(
    segmentation_extractor: SegmentationExtractor,
    nwbfile: NWBFile,
    metadata: dict,
    plane_index: int,
):
    """Private method to create ROI table region."""
    add_plane_segmentation(segmentation_extractor=segmentation_extractor, nwbfile=nwbfile, metadata=metadata)

    # Get plane segmentation from the image segmentation
    image_segmentation_metadata = metadata["Ophys"]["ImageSegmentation"]
    image_segmentation_name = image_segmentation_metadata["name"]
    ophys = get_module(nwbfile, "ophys")
    image_segmentation = ophys.get_data_interface(image_segmentation_name)

    plane_segmentation_name = image_segmentation_metadata["plane_segmentations"][0]["name"]
    plane_segmentation = image_segmentation.plane_segmentations[plane_segmentation_name]

    # Create a reference for ROIs from the plane segmentation
    roi_table_region = plane_segmentation.create_roi_table_region(
        region=segmentation_extractor.get_roi_ids(),
        description=f"region for Imaging plane{plane_index}",
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


def add_summary_images(
    nwbfile: NWBFile, segmentation_extractor: SegmentationExtractor, images_set_name: str = "summary_images"
) -> NWBFile:
    """
    Adds summary images (i.e. mean and correlation) to the nwbfile using an image container object pynwb.Image

    Parameters
    ----------
    nwbfile : NWBFile
        An previously defined -in memory- NWBFile.
    segmentation_extractor : SegmentationExtractor
        A segmentation extractor object from roiextractors.
    images_set_name : str
        The name of the image container, "summary_images" by default.

    Returns
    -------
    NWBFile
        The nwbfile passed as an input with the summary images added.
    """

    images_dict = segmentation_extractor.get_images_dict()
    images_to_add = {img_name: img for img_name, img in images_dict.items() if img is not None}
    if not images_to_add:
        return nwbfile

    ophys = get_module(nwbfile=nwbfile, name="ophys", description="contains optical physiology processed data")

    image_collection_does_not_exist = images_set_name not in ophys.data_interfaces
    if image_collection_does_not_exist:
        ophys.add(Images(images_set_name))
    image_collection = ophys.data_interfaces[images_set_name]

    for img_name, img in images_to_add.items():
        # Note that nwb uses the conversion width x heigth (columns, rows) and roiextractors uses the transpose
        image_collection.add_image(GrayscaleImage(name=img_name, data=img.T))

    return nwbfile


def write_segmentation(
    segmentation_extractor: SegmentationExtractor,
    nwbfile_path: OptionalFilePathType = None,
    nwbfile: Optional[NWBFile] = None,
    metadata: Optional[dict] = None,
    overwrite: bool = False,
    verbose: bool = True,
    buffer_size: int = 10,
    plane_num: int = 0,
    include_roi_centroids: bool = True,
    mask_type: Optional[str] = "image",  # Optional[Literal["image", "pixel"]]
    iterator_options: Optional[dict] = None,
    compression_options: Optional[dict] = None,
):
    """
    Primary method for writing an SegmentationExtractor object to an NWBFile.

    Parameters
    ----------
    segmentation_extractor: SegmentationExtractor
        The segentation extractor object to be written to nwb
    nwbfile_path: FilePathType
        Path for where to write or load (if overwrite=False) the NWBFile.
        If specified, the context will always write to this location.
    nwbfile: NWBFile, optional
        If passed, this function will fill the relevant fields within the NWBFile object.
        E.g., calling
            write_recording(recording=my_recording_extractor, nwbfile=my_nwbfile)
        will result in the appropriate changes to the my_nwbfile object.
        If neither 'nwbfile_path' nor 'nwbfile' are specified, an NWBFile object will be automatically generated
        and returned by the function.
    metadata: dict, optional
        Metadata dictionary with information used to create the NWBFile when one does not exist or overwrite=True.
    overwrite: bool, optional
        Whether or not to overwrite the NWBFile if one exists at the nwbfile_path.
        The default is False (append mode).
    verbose: bool, optional
        If 'nwbfile_path' is specified, informs user after a successful write operation.
        The default is True.
    buffer_size : int, optional
        The buffer size in GB, by default 10
    plane_num : int, optional
        The plane number to be extracted, by default 0
    include_roi_centroids : bool, optional
        Whether or not to include the ROI centroids on the PlaneSegmentation table.
        If there are a very large number of ROIs (such as in whole-brain recordings), you may wish to disable this for
            faster write speeds.
        Defaults to True.
    mask_type : str, optional
        There are two types of ROI masks in NWB: ImageMasks and PixelMasks.
        Image masks have the same shape as the reference images the segmentation was applied to, and weight each pixel
            by its contribution to the ROI (typically boolean, with 0 meaning 'not in the ROI').
        Pixel masks are instead indexed by ROI, with the data at each index being the shape of the image by the number
            of pixels in each ROI.
        Voxel masks are instead indexed by ROI, with the data at each index being the shape of the volume by the number
            of voxels in each ROI.
        Specify your choice between these two as mask_type='image', 'pixel', 'voxel', or None.
        If None, the mask information is not written to the NWB file.
        Defaults to 'image'.
    """
    assert (
        nwbfile_path is None or nwbfile is None
    ), "Either pass a nwbfile_path location, or nwbfile object, but not both!"

    iterator_options = iterator_options or dict()
    compression_options = compression_options or dict(compression="gzip")

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

            # Add device:
            add_devices(nwbfile=nwbfile_out, metadata=metadata)

            # ImageSegmentation:
            # image_segmentation_name = (
            #     "ImageSegmentation" if plane_no_loop == 0 else f"ImageSegmentation_Plane{plane_no_loop}"
            # )
            # add_image_segmentation(nwbfile=nwbfile_out, metadata=metadata)
            # image_segmentation = ophys.data_interfaces.get(image_segmentation_name)

            # Add imaging plane
            add_imaging_plane(nwbfile=nwbfile_out, metadata=metadata)

            # PlaneSegmentation:
            add_plane_segmentation(
                segmentation_extractor=segmentation_extractor,
                nwbfile=nwbfile_out,
                metadata=metadata,
                include_roi_centroids=include_roi_centroids,
                mask_type=mask_type,
                iterator_options=iterator_options,
                compression_options=compression_options,
            )

            # Add fluorescence traces:
            add_fluorescence_traces(
                segmentation_extractor=segmentation_extractor,
                nwbfile=nwbfile_out,
                metadata=metadata,
                iterator_options=iterator_options,
                compression_options=compression_options,
            )

            # Adding summary images (mean and correlation)
            images_set_name = "SegmentationImages" if plane_no_loop == 0 else f"SegmentationImages_Plane{plane_no_loop}"
            add_summary_images(
                nwbfile=nwbfile_out, segmentation_extractor=segmentation_extractor, images_set_name=images_set_name
            )

    return nwbfile_out
