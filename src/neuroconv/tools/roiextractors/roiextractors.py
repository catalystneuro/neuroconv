"""Authors: Heberto Mayorquin, Saksham Sharda, Alessio Buccino and Szonja Weigl"""
import os
from collections import defaultdict
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
    RoiResponseSeries,
    DfOverF,
)

# from hdmf.commmon import VectorData
from hdmf.data_utils import DataChunkIterator
from hdmf.backends.hdf5.h5_utils import H5DataIO

from ..nwb_helpers import get_default_nwbfile_metadata, make_or_load_nwbfile, get_module
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

    default_fluorescence_roi_response_series = dict(
        name="RoiResponseSeries", description="array of raw fluorescence traces", unit="n.a."
    )

    default_fluorescence = dict(
        name="Fluorescence",
        roi_response_series=[default_fluorescence_roi_response_series],
    )

    default_dff_roi_response_series = dict(name="DfOverF", description="array of df/F traces", unit="n.a.")

    default_df_over_f = dict(
        name="DfOverF",
        roi_response_series=[default_dff_roi_response_series],
    )

    default_two_photon_series = dict(
        name="TwoPhotonSeries",
        description="no description",
        comments="Generalized from RoiInterface",
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
        data=DataChunkIterator(data_generator(imaging), buffer_size=buffer_size),
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
        two_p_series_kwargs.update(timestamps=H5DataIO(data=timestamps, compression="gzip"))
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


def add_plane_segmentation(
    segmentation_extractor: SegmentationExtractor,
    nwbfile: NWBFile,
    metadata: Optional[dict],
    plane_segmentation_index: int = 0,
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
    iterator_options : dict, optional
        The options to use when iterating over the image masks of the segmentation extractor.
    compression_options : dict, optional
        The options to use when compressing the image masks of the segmentation extractor.

    Returns
    -------
    NWBFile
        The nwbfile passed as an input with the plane segmentation added.
    """
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

    add_imaging_plane(
        nwbfile=nwbfile,
        metadata=metadata_copy,
        imaging_plane_index=plane_segmentation_index,
    )

    add_image_segmentation(
        nwbfile=nwbfile,
        metadata=metadata_copy,
    )

    ophys = get_module(nwbfile, "ophys")
    image_segmentation_name = image_segmentation_metadata["name"]
    image_segmentation = ophys.get_data_interface(image_segmentation_name)

    # Check if the plane segmentation already exists in the image segmentation
    if plane_segmentation_name not in image_segmentation.plane_segmentations:
        roi_ids = segmentation_extractor.get_roi_ids()
        accepted_ids = [int(roi_id in segmentation_extractor.get_accepted_list()) for roi_id in roi_ids]
        rejected_ids = [int(roi_id in segmentation_extractor.get_rejected_list()) for roi_id in roi_ids]

        roi_locations = segmentation_extractor.get_roi_locations().T

        imaging_plane_metadata = metadata_copy["Ophys"]["ImagingPlane"][plane_segmentation_index]
        imaging_plane_name = imaging_plane_metadata["name"]
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


def add_fluorescence_traces(
    segmentation_extractor: SegmentationExtractor,
    nwbfile: NWBFile,
    metadata: Optional[dict],
    plane_index: int = 0,
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

    # Set the defaults and required infrastructure
    metadata_copy = deepcopy(metadata)
    default_metadata = get_default_ophys_metadata()
    metadata_copy = dict_deep_update(default_metadata, metadata_copy, append_list=False)

    # df/F metadata
    dff_metadata = metadata_copy["Ophys"]["DfOverF"]
    dff_name = dff_metadata["name"]

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

    rate = (
        np.nan
        if segmentation_extractor.get_sampling_frequency() is None
        else float(segmentation_extractor.get_sampling_frequency())
    )

    roi_response_series_kwargs = dict(
        rois=roi_table_region,
        # TODO: timestamps or rate (for timestamps we need frame_to_time method)
        # TODO: check for regularity, only use timestamps if irregular timing
        starting_time=0.0,
        rate=rate,
        unit="n.a.",
    )

    container = defaultdict(
        lambda: _get_segmentation_data_interface(
            nwbfile=nwbfile,
            data_interface_name=fluorescence_name,
        ),
        # we expect that the df/F trace name is "Dff"
        Dff=_get_segmentation_data_interface(
            nwbfile=nwbfile,
            data_interface_name=dff_name,
        ),
    )

    for trace_name, trace in traces_to_add.items():
        # Extract the response series metadata
        trace_name = "RoiResponseSeries" if trace_name == "raw" else trace_name.capitalize()
        trace_name = trace_name if plane_index == 0 else trace_name + f"_Plane{plane_index}"

        if trace_name in container[trace_name].roi_response_series:
            continue

        metadata = dff_metadata if trace_name == "Dff" else fluorescence_metadata
        response_series_metadata = metadata["roi_response_series"]
        trace_metadata = next(
            trace_metadata for trace_metadata in response_series_metadata if trace_name == trace_metadata["name"]
        )

        # Build the roi response series
        roi_response_series_kwargs.update(
            data=np.array(trace).T,
            rois=roi_table_region,
            **trace_metadata,
        )
        roi_response_series = RoiResponseSeries(**roi_response_series_kwargs)

        # Add it to the container
        container[trace_name].add_roi_response_series(roi_response_series)

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

    if data_interface_name.capitalize() == "Dff":
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

        ophys = get_module(nwbfile=nwbfile_out, name="ophys", description="contains optical physiology processed data")
        for plane_no_loop, (segext_obj, metadata) in enumerate(zip(segext_objs, metadata_base_list)):

            # Add device:
            add_devices(nwbfile=nwbfile_out, metadata=metadata)

            # ImageSegmentation:
            image_segmentation_name = (
                "ImageSegmentation" if plane_no_loop == 0 else f"ImageSegmentation_Plane{plane_no_loop}"
            )
            add_image_segmentation(nwbfile=nwbfile_out, metadata=metadata)
            image_segmentation = ophys.data_interfaces.get(image_segmentation_name)

            # Add imaging plane
            add_imaging_plane(nwbfile=nwbfile_out, metadata=metadata)

            # PlaneSegmentation:
            add_plane_segmentation(
                segmentation_extractor=segext_obj,
                nwbfile=nwbfile_out,
                metadata=metadata,
                iterator_options=dict(buffer_size=buffer_size),
                compression_options=dict(
                    compression=True,
                    compression_opts=9,
                ),
            )

            # Add fluorescence traces:
            add_fluorescence_traces(
                segmentation_extractor=segext_obj,
                nwbfile=nwbfile_out,
                metadata=metadata,
            )

            # Adding summary images (mean and correlation)
            images_set_name = "SegmentationImages" if plane_no_loop == 0 else f"SegmentationImages_Plane{plane_no_loop}"
            add_summary_images(nwbfile=nwbfile_out, segmentation_extractor=segext_obj, images_set_name=images_set_name)

    return nwbfile_out
