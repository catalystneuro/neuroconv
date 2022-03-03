"""Authors: Saksham Sharda and Alessio Buccino."""
import os
import numpy as np
from pathlib import Path
from warnings import warn
from collections import abc

from roiextractors import ImagingExtractor, SegmentationExtractor, MultiSegmentationExtractor
from pynwb import NWBFile, NWBHDF5IO
from pynwb.base import Images
from pynwb.file import Subject
from pynwb.image import GrayscaleImage
from pynwb.ophys import (
    ImageSegmentation,
    Fluorescence,
    OpticalChannel,
    TwoPhotonSeries,
)

# from hdmf.commmon import VectorData
from hdmf.data_utils import DataChunkIterator
from hdmf.backends.hdf5.h5_utils import H5DataIO

from ..nwb_helpers import get_default_nwbfile_metadata, make_nwbfile_from_metadata
from ...utils import FilePathType, dict_deep_update


# TODO: This function should be refactored, but for now seems necessary to avoid errors in tests
def safe_update(d, u):
    for k, v in u.items():
        if isinstance(v, abc.Mapping):
            d[k] = safe_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d


def default_ophys_metadata():
    """Fill default metadata for optical physiology."""
    metadata = get_default_nwbfile_metadata()
    metadata.update(
        Ophys=dict(
            Device=[dict(name="Microscope")],
            Fluorescence=dict(
                roi_response_series=[
                    dict(
                        name="RoiResponseSeries",
                        description="array of raw fluorescence traces",
                    )
                ]
            ),
            ImageSegmentation=dict(plane_segmentations=[dict(description="Segmented ROIs", name="PlaneSegmentation")]),
            ImagingPlane=[
                dict(
                    name="ImagingPlane",
                    description="no description",
                    excitation_lambda=np.nan,
                    indicator="unknown",
                    location="unknown",
                    optical_channel=[
                        dict(
                            name="OpticalChannel",
                            emission_lambda=np.nan,
                            description="no description",
                        )
                    ],
                )
            ],
            TwoPhotonSeries=[
                dict(
                    name="TwoPhotonSeries",
                    description="no description",
                    comments="Generalized from RoiInterface",
                    unit="n.a.",
                )
            ],
        ),
    )
    return metadata


def add_devices(nwbfile: NWBFile, metadata: dict):
    """Add optical physiology devices from metadata."""
    metadata = dict_deep_update(default_ophys_metadata(), metadata)
    for device in metadata.get("Ophys", dict()).get("Device", dict()):
        if "name" in device and device["name"] not in nwbfile.devices:
            nwbfile.create_device(**device)
    return nwbfile


def add_two_photon_series(imaging, nwbfile, metadata, buffer_size=10, use_times=False):
    """
    Auxiliary static method for nwbextractor.

    Adds two photon series from imaging object as TwoPhotonSeries to nwbfile object.
    """
    metadata = dict_deep_update(default_ophys_metadata(), metadata)
    metadata = safe_update(metadata, get_nwb_imaging_metadata(imaging))
    # Tests if ElectricalSeries already exists in acquisition
    nwb_es_names = [ac for ac in nwbfile.acquisition]
    opts = metadata["Ophys"]["TwoPhotonSeries"][0]
    if opts["name"] not in nwb_es_names:
        # retrieve device
        device = nwbfile.devices[list(nwbfile.devices.keys())[0]]
        metadata["Ophys"]["ImagingPlane"][0]["optical_channel"] = [
            OpticalChannel(**i) for i in metadata["Ophys"]["ImagingPlane"][0]["optical_channel"]
        ]
        metadata["Ophys"]["ImagingPlane"][0] = safe_update(metadata["Ophys"]["ImagingPlane"][0], {"device": device})

        imaging_plane = nwbfile.create_imaging_plane(**metadata["Ophys"]["ImagingPlane"][0])

        def data_generator(imaging):
            for i in range(imaging.get_num_frames()):
                yield imaging.get_frames(frame_idxs=[i]).T

        data = H5DataIO(
            DataChunkIterator(data_generator(imaging), buffer_size=buffer_size),
            compression=True,
        )

        # using internal data. this data will be stored inside the NWB file
        two_p_series_kwargs = dict_deep_update(
            metadata["Ophys"]["TwoPhotonSeries"][0],
            dict(data=data, imaging_plane=imaging_plane),
        )

        if not use_times:
            two_p_series_kwargs.update(
                starting_time=imaging.frame_to_time(0),
                rate=float(imaging.get_sampling_frequency()),
            )
        else:
            two_p_series_kwargs.update(
                timestamps=H5DataIO(
                    imaging.frame_to_time(np.arange(imaging.get_num_frames())),
                    compression="gzip",
                )
            )
            if "rate" in two_p_series_kwargs:
                del two_p_series_kwargs["rate"]
        ophys_ts = TwoPhotonSeries(**two_p_series_kwargs)

        nwbfile.add_acquisition(ophys_ts)
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


def get_nwb_imaging_metadata(imgextractor: ImagingExtractor):
    """
    Convert metadata from the segmentation into nwb specific metadata.

    Parameters
    ----------
    imgextractor: ImagingExtractor
    """
    metadata = default_ophys_metadata()
    # Optical Channel name:
    for i in range(imgextractor.get_num_channels()):
        ch_name = imgextractor.get_channel_names()[i]
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
    # set imaging plane rate:
    rate = (
        np.float("NaN")
        if imgextractor.get_sampling_frequency() is None
        else float(imgextractor.get_sampling_frequency())
    )
    # adding imaging_rate:
    metadata["Ophys"]["ImagingPlane"][0].update(imaging_rate=rate)
    # TwoPhotonSeries update:
    metadata["Ophys"]["TwoPhotonSeries"][0].update(dimension=imgextractor.get_image_size(), rate=rate)
    # remove what Segmentation extractor will input:
    _ = metadata["Ophys"].pop("ImageSegmentation")
    _ = metadata["Ophys"].pop("Fluorescence")
    return metadata


def write_imaging(
    imaging: ImagingExtractor,
    save_path: FilePathType = None,
    nwbfile=None,
    metadata: dict = None,
    overwrite: bool = False,
    buffer_size: int = 10,
    use_times=False,
):
    """
    Parameters
    ----------
    imaging: ImagingExtractor
        The imaging extractor object to be written to nwb
    save_path: PathType
        Required if an nwbfile is not passed. Must be the path to the nwbfile
        being appended, otherwise one is created and written.
    nwbfile: NWBFile
        Required if a save_path is not specified. If passed, this function
        will fill the relevant fields within the nwbfile. E.g., calling
        write_imaging(my_imaging_extractor, my_nwbfile)
        will result in the appropriate changes to the my_nwbfile object.
    metadata: dict
        metadata info for constructing the nwb file (optional).
    overwrite: bool
        If True and save_path is existing, it is overwritten
    num_chunks: int
        Number of chunks for writing data to file
    use_times: bool (optional, defaults to False)
        If True, the times are saved to the nwb file using imaging.frame_to_time(). If False (defualt),
        the sampling rate is used.
    """
    assert save_path is None or nwbfile is None, "Either pass a save_path location, or nwbfile object, but not both!"

    if nwbfile is not None:
        assert isinstance(nwbfile, NWBFile), "'nwbfile' should be of type pynwb.NWBFile"
    # Update any previous metadata with user passed dictionary
    if metadata is None:
        metadata = dict()
    if hasattr(imaging, "nwb_metadata"):
        metadata = dict_deep_update(imaging.nwb_metadata, metadata)
    metadata = dict_deep_update(get_nwb_imaging_metadata(imaging), metadata)
    if nwbfile is None:
        save_path = Path(save_path)
        assert save_path.suffix == ".nwb", "'save_path' file is not an .nwb file"

        if save_path.is_file():
            if not overwrite:
                read_mode = "r+"
            else:
                # save_path.unlink()
                read_mode = "w"
        else:
            read_mode = "w"
        with NWBHDF5IO(str(save_path), mode=read_mode) as io:
            if read_mode == "r+":
                nwbfile = io.read()
            else:
                nwbfile = make_nwbfile_from_metadata(metadata=metadata)
                add_devices(nwbfile=nwbfile, metadata=metadata)
                add_two_photon_series(
                    imaging=imaging,
                    nwbfile=nwbfile,
                    metadata=metadata,
                    buffer_size=buffer_size,
                )
                add_epochs(imaging=imaging, nwbfile=nwbfile)
            io.write(nwbfile)
    else:
        add_devices(nwbfile=nwbfile, metadata=metadata)
        add_two_photon_series(imaging=imaging, nwbfile=nwbfile, metadata=metadata, use_times=use_times)
        add_epochs(imaging=imaging, nwbfile=nwbfile)


def get_nwb_segmentation_metadata(sgmextractor):
    """
    Convert metadata from the segmentation into nwb specific metadata.

    Parameters
    ----------
    sgmextractor: SegmentationExtractor
    """
    metadata = default_ophys_metadata()
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
    rate = np.float("NaN") if sgmextractor.get_sampling_frequency() is None else sgmextractor.get_sampling_frequency()
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
    save_path: FilePathType = None,
    plane_num=0,
    metadata: dict = None,
    overwrite: bool = True,
    buffer_size: int = 10,
    nwbfile=None,
):
    assert save_path is None or nwbfile is None, "Either pass a save_path location, or nwbfile object, but not both!"

    # parse metadata correctly:
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
        metadata_base_list[num] = dict_deep_update(metadata_base_list[num], metadata_input)
    metadata_base_common = metadata_base_list[0]

    # build/retrieve nwbfile:
    if nwbfile is not None:
        assert isinstance(nwbfile, NWBFile), "'nwbfile' should be of type pynwb.NWBFile"
        write = False
    else:
        write = True
        save_path = Path(save_path)
        assert save_path.suffix == ".nwb"
        if save_path.is_file() and not overwrite:
            nwbfile_exist = True
            file_mode = "r+"
        else:
            if save_path.is_file():
                os.remove(save_path)
            if not save_path.parent.is_dir():
                save_path.parent.mkdir(parents=True)
            nwbfile_exist = False
            file_mode = "w"
        io = NWBHDF5IO(str(save_path), file_mode)
        if nwbfile_exist:
            nwbfile = io.read()
        else:
            nwbfile = make_nwbfile_from_metadata(metadata=metadata_base_common)
    # Subject:
    if metadata_base_common.get("Subject") and nwbfile.subject is None:
        nwbfile.subject = Subject(**metadata_base_common["Subject"])
    # Processing Module:
    if "ophys" not in nwbfile.processing:
        ophys = nwbfile.create_processing_module("ophys", "contains optical physiology processed data")
    else:
        ophys = nwbfile.get_processing_module("ophys")
    for plane_no_loop, (segext_obj, metadata) in enumerate(zip(segext_objs, metadata_base_list)):
        # Device:
        if metadata["Ophys"]["Device"][0]["name"] not in nwbfile.devices:
            nwbfile.create_device(**metadata["Ophys"]["Device"][0])
        # ImageSegmentation:
        image_segmentation_name = (
            "ImageSegmentation" if plane_no_loop == 0 else f"ImageSegmentation_Plane{plane_no_loop}"
        )
        if image_segmentation_name not in ophys.data_interfaces:
            image_segmentation = ImageSegmentation(name=image_segmentation_name)
            ophys.add(image_segmentation)
        else:
            image_segmentation = ophys.data_interfaces.get(image_segmentation_name)
        # OpticalChannel:
        optical_channels = [OpticalChannel(**i) for i in metadata["Ophys"]["ImagingPlane"][0]["optical_channel"]]

        # ImagingPlane:
        image_plane_name = "ImagingPlane" if plane_no_loop == 0 else f"ImagePlane_{plane_no_loop}"
        if image_plane_name not in nwbfile.imaging_planes.keys():
            input_kwargs = dict(
                name=image_plane_name,
                device=nwbfile.get_device(metadata_base_common["Ophys"]["Device"][0]["name"]),
            )
            metadata["Ophys"]["ImagingPlane"][0]["optical_channel"] = optical_channels
            input_kwargs.update(**metadata["Ophys"]["ImagingPlane"][0])
            if "imaging_rate" in input_kwargs:
                input_kwargs["imaging_rate"] = float(input_kwargs["imaging_rate"])
            imaging_plane = nwbfile.create_imaging_plane(**input_kwargs)
        else:
            imaging_plane = nwbfile.imaging_planes[image_plane_name]
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
        # Fluorescence Traces:
        if "Flourescence" not in ophys.data_interfaces:
            fluorescence = Fluorescence()
            ophys.add(fluorescence)
        else:
            fluorescence = ophys.data_interfaces["Fluorescence"]
        roi_response_dict = segext_obj.get_traces_dict()
        roi_table_region = ps.create_roi_table_region(
            description=f"region for Imaging plane{plane_no_loop}",
            region=list(range(segext_obj.get_num_rois())),
        )
        rate = np.float("NaN") if segext_obj.get_sampling_frequency() is None else segext_obj.get_sampling_frequency()
        for i, j in roi_response_dict.items():
            data = getattr(segext_obj, f"_roi_response_{i}")
            if data is not None:
                data = np.asarray(data)
                trace_name = "RoiResponseSeries" if i == "raw" else i.capitalize()
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
        if "TwoPhotonSeries" not in nwbfile.acquisition:
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
        # saving NWB file:
        if write:
            io.write(nwbfile)
            io.close()
