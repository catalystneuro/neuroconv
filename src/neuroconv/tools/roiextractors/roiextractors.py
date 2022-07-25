"""Authors: Heberto Mayorquin, Saksham Sharda and Alessio Buccino, Szonja Weigl"""
import os
from pathlib import Path
from warnings import warn
from typing import Optional
from copy import deepcopy

import numpy as np
from hdmf.common import VectorData

from roiextractors import ImagingExtractor, SegmentationExtractor, MultiSegmentationExtractor
from pynwb import NWBFile, NWBHDF5IO
from pynwb.base import Images
from pynwb.file import Subject
from pynwb.image import GrayscaleImage
from pynwb.device import Device
from pynwb.ophys import (
    ImageSegmentation,
    ImagingPlane,
    Fluorescence,
    OpticalChannel,
    TwoPhotonSeries,
)

# from hdmf.commmon import VectorData
from hdmf.data_utils import DataChunkIterator
from hdmf.backends.hdf5.h5_utils import H5DataIO

from ..nwb_helpers import get_default_nwbfile_metadata, make_nwbfile_from_metadata, make_or_load_nwbfile
from ...utils import (
    FilePathType,
    OptionalFilePathType,
    dict_deep_update,
    calculate_regular_series_rate,
)


def get_default_ophys_metadata():
    """Fill default metadata for optical physiology."""
    metadata = get_default_nwbfile_metadata()

    default_device = dict(name="Microscope")

    default_optical_channel = dict(
        name="OpticalChannel",
        emission_lambda=np.nan,
        description="no description",
    )

    default_imaging_plane = dict(
        name="ImagingPlane",
        description="no description",
        excitation_lambda=np.nan,
        indicator="unknown",
        location="unknown",
        device=default_device["name"],
        optical_channel=[default_optical_channel],
    )

    default_roi_response_series = dict(
        name="RoiResponseSeries",
        description="array of raw fluorescence traces",
    )

    default_fluoresence = dict(roi_response_series=[default_roi_response_series])

    default_two_photon_series = dict(
        name="TwoPhotonSeries",
        description="no description",
        comments="Generalized from RoiInterface",
        unit="n.a.",
    )

    metadata.update(
        Ophys=dict(
            Device=[default_device],
            Fluorescence=default_fluoresence,
            ImageSegmentation=dict(plane_segmentations=[dict(description="Segmented ROIs", name="PlaneSegmentation")]),
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
    # Optical Channel name:
    channel_name_list = imgextractor.get_channel_names()
    if channel_name_list is None:
        channel_name_list = ["generic_name"] * imgextractor.get_num_channels()

    for index, channel_name in enumerate(channel_name_list):
        if index == 0:
            metadata["Ophys"]["ImagingPlane"][0]["optical_channel"][index]["name"] = channel_name
        else:
            metadata["Ophys"]["ImagingPlane"][0]["optical_channel"].append(
                dict(
                    name=channel_name,
                    emission_lambda=np.nan,
                    description=f"{channel_name} description",
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
    Private auxiliar function to create an ImagingPlane object from pynwb using the imaging_plane_metadata
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


def add_plane_segmentation(
    segmentation_extractor: SegmentationExtractor,
    nwbfile: NWBFile,
    metadata: Optional[dict],
    plane_segmentation_index: int = 0,
    image_segmentation_name: str = None,
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
    image_segmentation_name : str, optional
        The name of the image segmentation to add the plane segmentation to.
    iterator_options : dict, optional
        The options to use when iterating over the image masks of the segmentation extractor.
    compression_options : dict, optional
        The options to use when compressing the image masks of the segmentation extractor.

    Returns
    -------
    NWBFile
        The nwbfile passed as an input with the plane segmentation added.
    """
    if image_segmentation_name is None:
        image_segmentation_name = "ImageSegmentation"
    if iterator_options is None:
        iterator_options = dict()
    if compression_options is None:
        compression_options = dict()

    def image_mask_iterator():
        for roi_id in segmentation_extractor.get_roi_ids():
            image_masks = segmentation_extractor.get_roi_image_masks(roi_ids=[roi_id]).T.squeeze()
            yield image_masks

    # Set the defaults and required infrastructure
    metadata_copy = deepcopy(metadata)
    default_metadata = get_default_ophys_metadata()
    metadata_copy = dict_deep_update(default_metadata, metadata_copy, append_list=False)

    image_segmentation_metadata = metadata_copy["Ophys"]["ImageSegmentation"]
    plane_segmentation_metadata = image_segmentation_metadata["plane_segmentations"][plane_segmentation_index]
    plane_segmentation_name = plane_segmentation_metadata["name"]

    # Check if "ophys" processing module already exists in the NWB file
    if "ophys" not in nwbfile.processing:
        ophys = nwbfile.create_processing_module("ophys", "contains optical physiology processed data")
    else:
        ophys = nwbfile.get_processing_module("ophys")

    # Check if the image segmentation already exists in the NWB file
    if image_segmentation_name not in ophys.data_interfaces:
        ophys.add(ImageSegmentation(image_segmentation_name, "contains image segmentation data"))

    image_segmentation = ophys.get_data_interface(image_segmentation_name)

    # Check if the plane segmentation already exists in the image segmentation
    if plane_segmentation_name not in image_segmentation.plane_segmentations:
        roi_ids = segmentation_extractor.get_roi_ids()
        accepted_ids = [int(roi_id in segmentation_extractor.get_accepted_list()) for roi_id in roi_ids]
        rejected_ids = [int(roi_id in segmentation_extractor.get_rejected_list()) for roi_id in roi_ids]

        roi_locations = np.array(segmentation_extractor.get_roi_locations()).T

        imaging_plane_metadata = metadata_copy["Ophys"]["ImagingPlane"][plane_segmentation_index]
        imaging_plane_name = imaging_plane_metadata["name"]
        if imaging_plane_name not in nwbfile.imaging_planes:
            imaging_plane = _create_imaging_plane_from_metadata(
                nwbfile=nwbfile, imaging_plane_metadata=imaging_plane_metadata
            )
            nwbfile.add_imaging_plane(imaging_plane)

        imaging_plane = nwbfile.imaging_planes[imaging_plane_name]

        plane_segmentation_kwargs = dict(
            **plane_segmentation_metadata,
            imaging_plane=imaging_plane,
            columns=[
                VectorData(
                    data=H5DataIO(
                        DataChunkIterator(image_mask_iterator(), **iterator_options),
                        **compression_options,
                    ),
                    name="image_mask",
                    description="image masks",
                ),
                VectorData(
                    data=roi_locations,
                    name="RoiCentroid",
                    description="x,y location of centroid of the roi in image_mask",
                ),
                VectorData(
                    data=accepted_ids,
                    name="Accepted",
                    description="1 if ROI was accepted or 0 if rejected as a cell during segmentation operation",
                ),
                VectorData(
                    data=rejected_ids,
                    name="Rejected",
                    description="1 if ROI was rejected or 0 if accepted as a cell during segmentation operation",
                ),
            ],
            id=roi_ids,
        )

        image_segmentation.create_plane_segmentation(**plane_segmentation_kwargs)

    return nwbfile


def add_two_photon_series(
    imaging, nwbfile, metadata, buffer_size=10, use_times=False, two_photon_series_index: int = 0
):
    """
    Auxiliary static method for nwbextractor.

    Adds two photon series from imaging object as TwoPhotonSeries to nwbfile object.
    """

    if use_times:
        warn("Keyword argument 'use_times' is deprecated and will be removed on or after August 1st, 2022.")

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
    def data_generator(imaging):
        for i in range(imaging.get_num_frames()):
            yield imaging.get_frames(frame_idxs=[i]).squeeze().T

    data = H5DataIO(
        DataChunkIterator(data_generator(imaging), buffer_size=buffer_size),
        compression=True,
    )
    two_p_series_kwargs = two_photon_series_metadata
    two_p_series_kwargs.update(data=data)

    # Add dimension
    two_p_series_kwargs.update(dimension=imaging.get_image_size())

    # Add timestamps or rate
    timestamps = imaging.frame_to_time(np.arange(imaging.get_num_frames()))
    rate = calculate_regular_series_rate(series=timestamps)
    if rate:
        two_p_series_kwargs.update(starting_time=timestamps[0], rate=rate)
    else:
        two_p_series_kwargs.update(timestamps=H5DataIO(timestamps, compression="gzip"))
        two_p_series_kwargs["rate"] = None

    # Add the TwoPhotonSeries to the nwbfile
    two_photon_series = TwoPhotonSeries(**two_p_series_kwargs)
    nwbfile.add_acquisition(two_photon_series)

    return nwbfile


def add_epochs(imaging, nwbfile):
    """
    Auxiliary static method for nwbextractor.

    Adds epochs from recording object to nwbfile object.
    """
    # add/update epochs
    for (name, ep) in imaging._epochs.items():
        if nwbfile.epochs is None:
            nwbfile.add_epoch(
                start_time=imaging.frame_to_time(ep["start_frame"]),
                stop_time=imaging.frame_to_time(ep["end_frame"]),
                tags=name,
            )
        else:
            if [name] in nwbfile.epochs["tags"][:]:
                ind = nwbfile.epochs["tags"][:].index([name])
                nwbfile.epochs["start_time"].data[ind] = imaging.frame_to_time(ep["start_frame"])
                nwbfile.epochs["stop_time"].data[ind] = imaging.frame_to_time(ep["end_frame"])
            else:
                nwbfile.add_epoch(
                    start_time=imaging.frame_to_time(ep["start_frame"]),
                    stop_time=imaging.frame_to_time(ep["end_frame"]),
                    tags=name,
                )
    return nwbfile


def write_imaging(
    imaging: ImagingExtractor,
    nwbfile_path: OptionalFilePathType = None,
    nwbfile: Optional[NWBFile] = None,
    metadata: Optional[dict] = None,
    overwrite: bool = False,
    verbose: bool = True,
    buffer_size: int = 10,
    use_times=False,
    save_path: OptionalFilePathType = None,  # TODO: to be removed
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
        If neither 'save_path' nor 'nwbfile' are specified, an NWBFile object will be automatically generated
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
    """
    assert save_path is None or nwbfile is None, "Either pass a save_path location, or nwbfile object, but not both!"
    if nwbfile is not None:
        assert isinstance(nwbfile, NWBFile), "'nwbfile' should be of type pynwb.NWBFile"

    if use_times:
        warn("Keyword argument 'use_times' is deprecated and will be removed on or after August 1st, 2022.")

    # TODO on or after August 1st, 2022, remove argument and deprecation warnings
    if save_path is not None:
        will_be_removed_str = "will be removed on or after August 1st, 2022. Please use 'nwbfile_path' instead."
        if nwbfile_path is not None:
            if save_path == nwbfile_path:
                warn(
                    "Passed both 'save_path' and 'nwbfile_path', but both are equivalent! "
                    f"'save_path' {will_be_removed_str}",
                    DeprecationWarning,
                )
            else:
                warn(
                    "Passed both 'save_path' and 'nwbfile_path' - using only the 'nwbfile_path'! "
                    f"'save_path' {will_be_removed_str}",
                    DeprecationWarning,
                )
        else:
            warn(
                f"The keyword argument 'save_path' to 'spikeinterface.write_recording' {will_be_removed_str}",
                DeprecationWarning,
            )
            nwbfile_path = save_path

    if metadata is None:
        metadata = dict()
    if hasattr(imaging, "nwb_metadata"):
        metadata = dict_deep_update(imaging.nwb_metadata, metadata, append_list=False)

    with make_or_load_nwbfile(
        nwbfile_path=nwbfile_path, nwbfile=nwbfile, metadata=metadata, overwrite=overwrite, verbose=verbose
    ) as nwbfile_out:
        add_devices(nwbfile=nwbfile_out, metadata=metadata)
        add_two_photon_series(imaging=imaging, nwbfile=nwbfile_out, metadata=metadata, buffer_size=buffer_size)
        add_epochs(imaging=imaging, nwbfile=nwbfile_out)
    return nwbfile_out


def get_nwb_segmentation_metadata(sgmextractor):
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


def write_segmentation(
    segext_obj: SegmentationExtractor,
    nwbfile_path: OptionalFilePathType = None,
    nwbfile: Optional[NWBFile] = None,
    metadata: Optional[dict] = None,
    overwrite: bool = False,
    verbose: bool = True,
    buffer_size: int = 10,
    plane_num: int = 0,
    save_path: OptionalFilePathType = None,  # TODO: to be removed
):
    """Primary method for writing an SegmentationExtractor object to an NWBFile.

    Parameters
    ----------
    segext_obj: SegmentationExtractor
        The segentation extractor object to be written to nwb
    nwbfile_path: FilePathType
        Path for where to write or load (if overwrite=False) the NWBFile.
        If specified, the context will always write to this location.
    nwbfile: NWBFile, optional
        If passed, this function will fill the relevant fields within the NWBFile object.
        E.g., calling
            write_recording(recording=my_recording_extractor, nwbfile=my_nwbfile)
        will result in the appropriate changes to the my_nwbfile object.
        If neither 'save_path' nor 'nwbfile' are specified, an NWBFile object will be automatically generated
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
    """
    assert save_path is None or nwbfile is None, "Either pass a save_path location, or nwbfile object, but not both!"

    # parse metadata correctly considering the MultiSegmentationExtractor function:
    if isinstance(segext_obj, MultiSegmentationExtractor):
        segext_objs = segext_obj.segmentations
        if metadata is not None:
            assert isinstance(metadata, list), (
                "For MultiSegmentationExtractor enter 'metadata' as a list of " "SegmentationExtractor metadata"
            )
            assert len(metadata) == len(segext_objs), (
                "The 'metadata' argument should be a list with the same "
                "number of elements as the segmentations in the "
                "MultiSegmentationExtractor"
            )
    else:
        segext_objs = [segext_obj]
        if metadata is not None and not isinstance(metadata, list):
            metadata = [metadata]
    metadata_base_list = [get_nwb_segmentation_metadata(sgobj) for sgobj in segext_objs]

    # updating base metadata with new:
    for num, data in enumerate(metadata_base_list):
        metadata_input = metadata[num] if metadata else {}
        metadata_base_list[num] = dict_deep_update(metadata_base_list[num], metadata_input, append_list=False)
    metadata_base_common = metadata_base_list[0]

    # TODO on or after August 1st, 2022, remove argument and deprecation warnings
    if save_path is not None:
        will_be_removed_str = "will be removed on or after August 1st, 2022. Please use 'nwbfile_path' instead."
        if nwbfile_path is not None:
            if save_path == nwbfile_path:
                warn(
                    "Passed both 'save_path' and 'nwbfile_path', but both are equivalent! "
                    f"'save_path' {will_be_removed_str}",
                    DeprecationWarning,
                )
            else:
                warn(
                    "Passed both 'save_path' and 'nwbfile_path' - using only the 'nwbfile_path'! "
                    f"'save_path' {will_be_removed_str}",
                    DeprecationWarning,
                )
        else:
            warn(
                f"The keyword argument 'save_path' to 'spikeinterface.write_recording' {will_be_removed_str}",
                DeprecationWarning,
            )
            nwbfile_path = save_path

    with make_or_load_nwbfile(
        nwbfile_path=nwbfile_path, nwbfile=nwbfile, metadata=metadata_base_common, overwrite=overwrite, verbose=verbose
    ) as nwbfile_out:
        # Processing Module:
        if "ophys" not in nwbfile_out.processing:
            ophys = nwbfile_out.create_processing_module("ophys", "contains optical physiology processed data")
        else:
            ophys = nwbfile_out.get_processing_module("ophys")

        for plane_no_loop, (segext_obj, metadata) in enumerate(zip(segext_objs, metadata_base_list)):

            # Add device:
            add_devices(nwbfile=nwbfile_out, metadata=metadata)

            # ImageSegmentation:
            image_segmentation_name = (
                "ImageSegmentation" if plane_no_loop == 0 else f"ImageSegmentation_Plane{plane_no_loop}"
            )
            if image_segmentation_name not in ophys.data_interfaces:
                image_segmentation = ImageSegmentation(name=image_segmentation_name)
                ophys.add(image_segmentation)
            else:
                image_segmentation = ophys.data_interfaces.get(image_segmentation_name)

            # Add imaging plane
            imaging_plane_name = "ImagingPlane" if plane_no_loop == 0 else f"ImagePlane_{plane_no_loop}"
            add_imaging_plane(nwbfile=nwbfile_out, metadata=metadata)
            imaging_plane = nwbfile_out.imaging_planes[imaging_plane_name]

            # PlaneSegmentation:
            input_kwargs = dict(
                description="output from segmenting imaging plane",
                imaging_plane=imaging_plane,
            )
            ps_metadata = metadata["Ophys"]["ImageSegmentation"]["plane_segmentations"][0]
            if ps_metadata["name"] not in image_segmentation.plane_segmentations:
                ps_exist = False
            else:
                ps = image_segmentation.get_plane_segmentation(ps_metadata["name"])
                ps_exist = True
            roi_ids = segext_obj.get_roi_ids()
            accepted_list = segext_obj.get_accepted_list()
            accepted_list = [] if accepted_list is None else accepted_list
            rejected_list = segext_obj.get_rejected_list()
            rejected_list = [] if rejected_list is None else rejected_list
            accepted_ids = [1 if k in accepted_list else 0 for k in roi_ids]
            rejected_ids = [1 if k in rejected_list else 0 for k in roi_ids]
            roi_locations = np.array(segext_obj.get_roi_locations()).T

            def image_mask_iterator():
                for id in segext_obj.get_roi_ids():
                    img_msks = segext_obj.get_roi_image_masks(roi_ids=[id]).T.squeeze()
                    yield img_msks

            if not ps_exist:
                from hdmf.common import VectorData

                input_kwargs.update(
                    **ps_metadata,
                    columns=[
                        VectorData(
                            data=H5DataIO(
                                DataChunkIterator(image_mask_iterator(), buffer_size=buffer_size),
                                compression=True,
                                compression_opts=9,
                            ),
                            name="image_mask",
                            description="image masks",
                        ),
                        VectorData(
                            data=roi_locations,
                            name="RoiCentroid",
                            description="x,y location of centroid of the roi in image_mask",
                        ),
                        VectorData(
                            data=accepted_ids,
                            name="Accepted",
                            description="1 if ROi was accepted or 0 if rejected as a cell during segmentation operation",
                        ),
                        VectorData(
                            data=rejected_ids,
                            name="Rejected",
                            description="1 if ROi was rejected or 0 if accepted as a cell during segmentation operation",
                        ),
                    ],
                    id=roi_ids,
                )

                ps = image_segmentation.create_plane_segmentation(**input_kwargs)

            # Fluorescence Traces - This should be a function on its own.
            if "Flourescence" not in ophys.data_interfaces:
                fluorescence = Fluorescence()
                ophys.add(fluorescence)
            else:
                fluorescence = ophys.data_interfaces["Fluorescence"]

            roi_table_region = ps.create_roi_table_region(
                description=f"region for Imaging plane{plane_no_loop}",
                region=list(range(segext_obj.get_num_rois())),
            )

            roi_response_dict = segext_obj.get_traces_dict()

            rate = np.nan if segext_obj.get_sampling_frequency() is None else segext_obj.get_sampling_frequency()

            # Filter empty data
            roi_response_dict = {key: value for key, value in roi_response_dict.items() if value is not None}
            for signal, response_series in roi_response_dict.items():

                not_all_data_is_zero = any(x != 0 for x in np.ravel(response_series))
                if not_all_data_is_zero:
                    data = np.asarray(response_series)
                    trace_name = "RoiResponseSeries" if signal == "raw" else signal.capitalize()
                    trace_name = trace_name if plane_no_loop == 0 else trace_name + f"_Plane{plane_no_loop}"
                    input_kwargs = dict(
                        name=trace_name,
                        data=data.T,
                        rois=roi_table_region,
                        rate=rate,
                        unit="n.a.",
                    )
                    if trace_name not in fluorescence.roi_response_series:
                        fluorescence.create_roi_response_series(**input_kwargs)

            # create Two Photon Series:
            if "TwoPhotonSeries" not in nwbfile_out.acquisition:
                warn("could not find TwoPhotonSeries, using ImagingExtractor to create an nwbfile")
            # adding images:
            images_dict = segext_obj.get_images_dict()
            if any([image is not None for image in images_dict.values()]):
                images_name = "SegmentationImages" if plane_no_loop == 0 else f"SegmentationImages_Plane{plane_no_loop}"
                if images_name not in ophys.data_interfaces:
                    images = Images(images_name)
                    for img_name, img_no in images_dict.items():
                        if img_no is not None:
                            images.add_image(GrayscaleImage(name=img_name, data=img_no.T))
                    ophys.add(images)

    return nwbfile_out
