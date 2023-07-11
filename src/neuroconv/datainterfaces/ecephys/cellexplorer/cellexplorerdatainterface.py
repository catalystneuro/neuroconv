from pathlib import Path
from typing import List, Literal, Optional, Union
from warnings import warn

import numpy as np
import scipy
from pynwb import NWBFile

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....tools import get_package
from ....utils import FilePathType, FolderPathType


def add_channel_metadata_to_recoder(recording_extractor, folder_path: FolderPathType):
    """
    Main function to add channel metadata to a recording extractor from a CellExplorer session.
    The metadata is added as channel properties to the recording extractor.

    Parameters
    ----------
    recording_extractor : BaseRecording from spikeinterface
        The recording extractor to which the metadata will be added.
    folder_path : str or Path
        The path to the directory containing the CellExplorer session.

    Returns
    -------
    RecordingExtractor
        The same recording extractor passed in the `recording_extractor` argument, but with added metadata as
        channel properties.

    Notes
    -----
    The metadata for the channels is extracted from the `basename.session.mat`
    file. The logic of the extraction is described on the function:

    `add_channel_metadata_to_recorder_from_session_file`.

    Note that, while all the new data produced by CellExplorer should have a
    `session.mat` file,  it is not clear if all the channel metadata is always
    available.

    Besides, the current implementation also supports extracting channel metadata
    from the `chanMap.mat` file used by Kilosort. The logic of the extraction is
    described on the function:

    `add_channel_metadata_to_recorder_from_channel_map_file`.

    Bear in mind that this file is not always available for all datasets.

    From the documentation we also know that channel data can also be found in the following files:
    * `basename.ChannelName.channelinfo.mat`: general data container for channel-wise dat
    * `basename.chanCoords.channelinfo.mat`: contains the coordinates of the electrodes in the probe
    * `basename.ccf.channelinfo.mat`: Allen Institute's Common Coordinate Framework (CCF)

    Detailed information can be found in the following link
    https://cellexplorer.org/datastructure/data-structure-and-format/#channels

    Future versions of this function will support the extraction of this metadata from these files as well

    """

    recording_extractor = add_channel_metadata_to_recorder_from_session_file(
        recording_extractor=recording_extractor, folder_path=folder_path
    )

    recording_extractor = add_channel_metadata_to_recorder_from_channel_map_file(
        recording_extractor=recording_extractor, folder_path=folder_path
    )

    return recording_extractor


def add_channel_metadata_to_recorder_from_session_file(
    recording_extractor,
    folder_path: FolderPathType,
):
    """
    Extracts channel metadata from the CellExplorer's `session.mat` file and adds
    it to the given recording extractor as properties.

    The metadata includes electrode groups, channel locations, and brain regions. The function will  skip addition
    if the `session.mat` file is not found in the given session path. This is done to support calling the
    when using files produced by the old cellexplorer format (Buzcode) which does not have a `session.mat` file.

    Parameters
    ----------
    recording_extractor : BaseRecording from spikeinterface
        The recording extractor to which the metadata will be added.
    folder_path : str or Path
        The path to the directory containing the CellExplorer session.

    Returns
    -------
    RecordingExtractor
        The same recording extractor passed in the `recording_extractor` argument, but with added metadata as
        channel properties.

    Notes
    -----
    1. The channel locations are retrieved from the `chanCoords` field in the `extracellular` section of the
    `session.mat` file. They are set in the recording extractor using the `set_channel_locations` method.

    2. The electrode group information is extracted from the `electrodeGroups` field in the `extracellular` section of the
    `session.mat` file. The groups are set in the recording extractor using the `set_property` method with the `group`
    key.

    3. The brain region data is fetched from the `brainRegions` section of the `session.mat` file. The brain regions are
    set in the recording extractor using the `set_property` method with the `brain_region` key.

    """

    session_path = Path(folder_path)
    session_id = session_path.stem
    session_path = session_path / f"{session_id}.session.mat"
    if not session_path.is_file():
        return recording_extractor

    from pymatreader import read_mat

    ignore_fields = ["animal", "behavioralTracking", "timeSeries", "spikeSorting", "epochs"]
    session_data = read_mat(session_path, ignore_fields=ignore_fields)["session"]
    channel_ids = recording_extractor.get_channel_ids()

    if "extracellular" in session_data:
        extracellular_data = session_data["extracellular"]

        if "chanCoords" in extracellular_data:
            channel_coordinates = extracellular_data["chanCoords"]
            x_coords = channel_coordinates["x"]
            y_coords = channel_coordinates["y"]
            locations = np.array((x_coords, y_coords)).T.astype("float32")
            recording_extractor.set_channel_locations(channel_ids=channel_ids, locations=locations)

        if "electrodeGroups" in extracellular_data:
            electrode_groups_data = extracellular_data["electrodeGroups"]
            channels = electrode_groups_data["channels"]

            # Channels is a list of arrays where each array corresponds to a group. We flatten it to a single array
            num_electrode_groups = len(channels)
            group_labels = [[f"Group {index + 1}"] * len(channels[index]) for index in range(num_electrode_groups)]
            channels = np.concatenate(channels).astype("int")
            values = np.concatenate(group_labels)
            corresponding_channel_ids = [str(channel) for channel in channels]
            recording_extractor.set_property(key="group", ids=corresponding_channel_ids, values=values)

    if "brainRegions" in session_data:
        brain_region_data = session_data["brainRegions"]
        # The data in the `brainRegions` field is a struct where the keys are the brain region ids and the values
        # are dictionaries with the brain region data.
        # Each of those inner diciontaries has a key called "channels" whose values is an array of channel ids

        channel_id_to_brain_region = dict()
        for brain_region_id, brain_region_dict in brain_region_data.items():
            # Also, each inner dictionary can have a key called "brainRegion" which is the name of the brain region.
            brain_region_name = brain_region_dict.get("brainRegion", brain_region_id)
            channels = brain_region_dict["channels"].astype("int")
            channels = [str(channel) for channel in channels]
            for channel_id in channels:
                # This is a fine grained brain region data.
                # Channels are assigned to more than one brain region (e.g. CA1sp and CA1so)
                if channel_id not in channel_id_to_brain_region:
                    channel_id_to_brain_region[channel_id] = brain_region_name
                else:
                    channel_id_to_brain_region[channel_id] += " - " + brain_region_name

        ids = list(channel_id_to_brain_region.keys())
        values = list(channel_id_to_brain_region.values())
        recording_extractor.set_property(
            key="brain_area",
            ids=ids,
            values=values,
        )

    return recording_extractor


def add_channel_metadata_to_recorder_from_channel_map_file(
    recording_extractor,
    folder_path: FolderPathType,
):
    """
    Extracts channel metadata from the `chanMap.mat` file used by Kilosort and adds
    the properties to the given recording extractor as channel properties.

    The metadata includes channel groups, channel locations, and channel names. The function will skip addition of
    properties if the `chanMap.mat` file is not found in the given session path.

    Parameters
    ----------
    recording_extractor : BaseRecording from spikeinterface
        The recording extractor to which the metadata will be added.
    folder_path : Path or str
        The path to the directory containing the session.

    Returns
    -------
    RecordingExtractor
        The same recording extractor passed in the `recording_extractor` argument, but with added metadata.

    Notes
    -----
    1. The channel locations are retrieved from the `xcoords` and `ycoords` fields in the `chanMap.mat` file. They are
    set in the recording extractor using the `set_channel_locations` method.

    2. The channel groups are extracted from the `connected` field in the `chanMap.mat` file. The groups are set in the
    recording extractor using the `set_property` method with the `group` key.

    3. The channel names are composed of the channel index and group, and are set in the recording extractor using the
    `set_property` method with the `channel_name` key.

    4. Channel group names are created based on the group index and are set in the recording extractor using the
    `set_property` method with the `group_name` key.
    """

    session_path = Path(folder_path)
    chan_map_file_path = session_path / f"chanMap.mat"
    if not chan_map_file_path.is_file():
        return recording_extractor

    recorder_properties = recording_extractor.get_property_keys()

    from pymatreader import read_mat

    channel_map_data = read_mat(chan_map_file_path)

    channel_ids = channel_map_data["chanMap"]
    channel_ids = [str(channel_id) for channel_id in channel_ids]

    add_group_to_recorder = "group" not in recorder_properties and "kcoords" in channel_map_data
    if add_group_to_recorder:
        channel_groups = channel_map_data["kcoords"]
        recording_extractor.set_property(key="group", ids=channel_ids, values=channel_groups)

    add_coordinates_to_recorder = "location" not in recorder_properties and "xcoords" in channel_map_data
    if add_coordinates_to_recorder:
        x_coords = channel_map_data["xcoords"]
        y_coords = channel_map_data["ycoords"]
        locations = np.array((x_coords, y_coords)).T.astype("float32")
        recording_extractor.set_channel_locations(channel_ids=channel_ids, locations=locations)

    return recording_extractor


class CellExplorerRecordingInterface(BaseRecordingExtractorInterface):
    """
    Adds raw and lfp data from binary files with the new CellExplorer format:

    https://cellexplorer.org/

    Parameters
    ----------
    folder_path : Path or str
        The folder where the session data is located. It should contain a
        `{folder.name}.session.mat` file and the binary files `{folder.name}.dat`
        or `{folder.name}.lfp` for the LFP interface.
    verbose : bool, default: True
            Whether to output verbose text.
    es_key : str, default: "ElectricalSeries" and "ElectricalSeriesLFP" for the LFP interface

    Notes
    -----
    CellExplorer's new format contains a `basename.session.mat` file containing
    rich metadata about the session. basename is the name of the session
    folder / directory and works as a session identifier.

    Link to the documentation detailing the `basename.session.mat` structure:
    https://cellexplorer.org/datastructure/data-structure-and-format/#session-metadata

    Specifically, we can use the following fields from `basename.session.mat`
    to create a recording extractor using `BinaryRecordingExtractor` from
    spikeinterface:

    * Sampling frequency
    * Gains
    * Dtype

    Where the binary file is named `basename.dat` for the raw data and
    `basename.lfp` for lfp data.

    The extraction of channel metadata is described in the function: `add_channel_metadata_to_recoder`
    """

    sampling_frequency_key = "sr"
    binary_file_extension = "dat"

    def __init__(self, folder_path: FolderPathType, verbose: bool = True, es_key: str = "ElectricalSeries"):
        self.session_path = Path(folder_path)

        # No super here, we need to do everything by hand
        self.verbose = verbose
        self.es_key = es_key
        self.subset_channels = None
        self.source_data = dict(folder_path=folder_path)
        self._number_of_segments = 1  # CellExplorer is mono segment

        self.session_id = self.session_path.stem
        session_data_file_path = self.session_path / f"{self.session_id}.session.mat"
        assert session_data_file_path.is_file(), f"File {session_data_file_path} does not exist"

        from pymatreader import read_mat

        ignore_fields = ["animal", "behavioralTracking", "timeSeries", "spikeSorting", "epochs"]
        session_data = read_mat(filename=session_data_file_path, ignore_fields=ignore_fields)["session"]
        extracellular_data = session_data["extracellular"]
        num_channels = int(extracellular_data["nChannels"])
        gain = float(extracellular_data["leastSignificantBit"])  # Usually a value of 0.195 when intan is used
        gains_to_uv = np.ones(num_channels) * gain
        dtype = np.dtype(extracellular_data["precision"])
        sampling_frequency = float(extracellular_data[self.sampling_frequency_key])

        # Channels in CellExplorer are 1-indexed
        channel_ids = [str(1 + i) for i in range(num_channels)]
        binary_file_path = self.session_path / f"{self.session_id}.{self.binary_file_extension}"
        assert binary_file_path.is_file(), f"Binary file {binary_file_path.name} does not exist in `folder_path`"

        from spikeinterface.core.binaryrecordingextractor import (
            BinaryRecordingExtractor,
        )

        self.recording_extractor = BinaryRecordingExtractor(
            file_paths=[binary_file_path],
            sampling_frequency=sampling_frequency,
            num_chan=num_channels,
            dtype=dtype,
            t_starts=None,
            file_offset=0,
            gain_to_uV=gains_to_uv,
            offset_to_uV=None,
            channel_ids=channel_ids,
        )

        self.recording_extractor = add_channel_metadata_to_recoder(
            recording_extractor=self.recording_extractor, folder_path=folder_path
        )

    def get_original_timestamps(self):
        num_frames = self.recording_extractor.get_num_frames()
        sampling_frequency = self.recording_extractor.get_sampling_frequency()
        timestamps = np.arange(num_frames) / sampling_frequency
        return timestamps


class CellExplorerLFPInterface(CellExplorerRecordingInterface):
    keywords = BaseRecordingExtractorInterface.keywords + [
        "extracellular electrophysiology",
        "LFP",
        "local field potential",
        "LF",
    ]

    sampling_frequency_key = "srLfp"
    binary_file_extension = "lfp"

    def __init__(self, folder_path: FolderPathType, verbose: bool = True, es_key: str = "ElectricalSeriesLFP"):
        super().__init__(folder_path, verbose, es_key)

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: Optional[dict] = None,
        stub_test: bool = False,
        starting_time: Optional[float] = None,
        write_as: Literal["raw", "lfp", "processed"] = "lfp",
        write_electrical_series: bool = True,
        compression: Optional[str] = "gzip",
        compression_opts: Optional[int] = None,
        iterator_type: str = "v2",
        iterator_opts: Optional[dict] = None,
    ):
        super().add_to_nwbfile(
            nwbfile,
            metadata,
            stub_test,
            starting_time,
            write_as,
            write_electrical_series,
            compression,
            compression_opts,
            iterator_type,
            iterator_opts,
        )


class CellExplorerSortingInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting Cell Explorer spiking data."""

    def __init__(self, file_path: FilePathType, verbose: bool = True):
        """
        Initialize read of Cell Explorer file.

        Parameters
        ----------
        file_path: FilePathType
            Path to .spikes.cellinfo.mat file.
        verbose: bool, default: True
        """

        hdf5storage = get_package(package_name="hdf5storage")

        file_path = Path(file_path)
        self.session_path = Path(file_path).parent
        self.session_id = self.session_path.stem

        # Temporary hack to get sampling frequency from the spikes cellinfo file until next SI release
        from pymatreader import read_mat

        matlab_file = read_mat(file_path)

        if "spikes" not in matlab_file.keys():
            raise KeyError(f"CellExplorer file '{file_path}' does not contain 'spikes' field.")
        spikes_mat = matlab_file["spikes"]
        sampling_frequency = spikes_mat.get("sr", None)

        # If sampling rate is not available in the spikes cellinfo file, try to get it from the session file
        session_path = self.session_path / f"{self.session_id}.session.mat"
        if sampling_frequency is None and session_path.is_file():
            matlab_file = read_mat(session_path)
            session_data = matlab_file["session"]
            if "extracellular" in session_data.keys():
                sampling_frequency = session_data["extracellular"].get("sr", None)

        super().__init__(spikes_matfile_path=file_path, sampling_frequency=sampling_frequency, verbose=verbose)
        self.source_data = dict(file_path=file_path)
        spikes_matfile_path = Path(file_path)

        assert (
            spikes_matfile_path.is_file()
        ), f"The file_path should point to an existing .spikes.cellinfo.mat file ({spikes_matfile_path})"

        try:
            spikes_mat = scipy.io.loadmat(file_name=str(spikes_matfile_path))
            self.read_spikes_info_with_scipy = True
        except NotImplementedError:
            spikes_mat = hdf5storage.loadmat(file_name=str(spikes_matfile_path))
            self.read_spikes_info_with_scipy = False
        cell_info = spikes_mat.get("spikes", np.empty(0))
        self.cell_info_fields = cell_info.dtype.names

        unit_ids = self.sorting_extractor.get_unit_ids()
        if self.read_spikes_info_with_scipy:
            if "cluID" in self.cell_info_fields:
                self.sorting_extractor.set_property(
                    ids=unit_ids, key="clu_id", values=[int(x) for x in cell_info["cluID"][0][0][0]]
                )
            if "shankID" in self.cell_info_fields:
                self.sorting_extractor.set_property(
                    ids=unit_ids, key="group_id", values=[f"Group{x}" for x in cell_info["shankID"][0][0][0]]
                )
            if "region" in self.cell_info_fields:
                self.sorting_extractor.set_property(
                    ids=unit_ids, key="location", values=[str(x[0]) for x in cell_info["region"][0][0][0]]
                )
        else:  # Logic for hdf5storage
            if "cluID" in self.cell_info_fields:
                self.sorting_extractor.set_property(
                    ids=unit_ids, key="clu_id", values=[int(x) for x in cell_info["cluID"][0][0]]
                )
            if "shankID" in self.cell_info_fields:
                self.sorting_extractor.set_property(
                    ids=unit_ids, key="group_id", values=[f"Group{x}" for x in cell_info["shankID"][0][0]]
                )
            if "region" in self.cell_info_fields:
                self.sorting_extractor.set_property(
                    ids=unit_ids, key="location", values=[str(x[0]) for x in cell_info["region"][0][0]]
                )

        celltype_mapping = {"pE": "excitatory", "pI": "inhibitory", "[]": "unclassified"}
        celltype_file_path = self.session_path / f"{self.session_id}.CellClass.cellinfo.mat"
        if celltype_file_path.is_file():
            celltype_info = scipy.io.loadmat(celltype_file_path).get("CellClass", np.empty(0))
            if "label" in celltype_info.dtype.names:
                self.sorting_extractor.set_property(
                    ids=unit_ids,
                    key="cell_type",
                    values=[str(celltype_mapping[str(x[0])]) for x in celltype_info["label"][0][0][0]],
                )

    def generate_recording_with_channel_metadata(self):
        session_data_file_path = self.session_path / f"{self.session_id}.session.mat"
        if session_data_file_path.is_file():
            from pymatreader import read_mat

            ignore_fields = ["animal", "behavioralTracking", "timeSeries", "spikeSorting", "epochs"]
            session_data = read_mat(filename=session_data_file_path, ignore_fields=ignore_fields)["session"]
            extracellular_data = session_data["extracellular"]
            num_channels = int(extracellular_data["nChannels"])
            num_samples = int(extracellular_data["nSamples"])
            sampling_frequency = int(extracellular_data["sr"])

            # Create a dummy recording extractor
            from spikeinterface.core.numpyextractors import NumpyRecording

            traces_list = [np.empty(shape=(1, num_channels))]
            channel_ids = [str(1 + i) for i in range(num_channels)]
            dummy_recording_extractor = NumpyRecording(
                traces_list=traces_list,
                sampling_frequency=sampling_frequency,
                channel_ids=channel_ids,
            )

            # Add the channel metadata
            dummy_recording_extractor = add_channel_metadata_to_recoder(
                recording_extractor=dummy_recording_extractor, folder_path=self.session_path
            )

        return dummy_recording_extractor

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
        session_path = Path(self.source_data["file_path"]).parent
        session_id = session_path.stem
        # TODO: add condition for retrieving ecephys metadata if no recording or lfp are included in conversion
        metadata["NWBFile"].update(session_id=session_id)

        unit_properties = []
        cellinfo_file_path = session_path / f"{session_id}.spikes.cellinfo.mat"
        if cellinfo_file_path.is_file():
            cell_info_fields = self.cell_info_fields
            if "cluID" in cell_info_fields:
                unit_properties.append(
                    dict(
                        name="clu_id",
                        description="0-indexed id of cluster identified from the shank.",
                    )
                )
            if "shankID" in cell_info_fields:
                unit_properties.append(
                    dict(
                        name="group_id",
                        description="The electrode group ID that each unit was identified by.",
                    )
                )
            if "region" in cell_info_fields:
                unit_properties.append(
                    dict(
                        name="location",
                        description="Brain region where each unit was detected.",
                    )
                )
        celltype_filepath = session_path / f"{session_id}.CellClass.cellinfo.mat"
        if celltype_filepath.is_file():
            celltype_info = scipy.io.loadmat(celltype_filepath).get("CellClass", np.empty(0))
            if "label" in celltype_info.dtype.names:
                unit_properties.append(
                    dict(
                        name="cell_type",
                        description="Type of cell this has been classified as.",
                    )
                )
        metadata.update(Ecephys=dict(UnitProperties=unit_properties))

        return metadata
