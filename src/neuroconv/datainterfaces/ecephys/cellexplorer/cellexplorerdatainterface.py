from pathlib import Path
from typing import List, Literal, Optional, Union

import numpy as np
import scipy
from pynwb import NWBFile

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..basesortingextractorinterface import BaseSortingExtractorInterface
from ....tools import get_package
from ....utils import FilePathType, FolderPathType


def add_channel_metadata_to_recorder_from_session_file(
    recording_extractor,
    session_path: FolderPathType,
):
    """
    Extracts channel metadata from the CellExplorer's `session.mat` file and adds it to the given recording extractor.

    The metadata includes electrode groups, channel locations, and brain regions. The function will  skip addition
    if the `session.mat` file is not found in the given session path. This is done to support calling the
    when using files produced by the old cellexplorer format (Buzcode) which does not have a `session.mat` file.

    Parameters
    ----------
    recording_extractor : BaseRecording from spikeinterface
        The recording extractor to which the metadata will be added.
    session_path : str or Path
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

    session_path = Path(session_path)
    session_path = session_path / f"{session_path.stem}.session.mat"
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
            corresponding_channels_ids = [str(channel) for channel in channels]
            recording_extractor.set_property(key="group", ids=corresponding_channels_ids, values=values)

    if "brainRegions" in session_data:
        brain_region_data = session_data["brainRegions"]
        for brain_region_id, brain_region_dict in brain_region_data.items():
            brain_region_name = brain_region_dict["brainRegion"]
            channels = brain_region_dict["channels"].astype("int")
            corresponding_channel_ids = [str(id) for id in channels]
            values = [brain_region_name] * len(channel_ids)
            recording_extractor.set_property(
                key="location",
                ids=corresponding_channel_ids,
                values=values,
            )

    return recording_extractor


def add_channel_metadata_to_recorder_from_channel_map_file(
    recording_extractor,
    session_path: FolderPathType,
):
    """
    Extracts channel metadata from the `chanMap.mat` file used by Kilosort and adds it to the given recording extractor.

    The metadata includes channel groups, channel locations, and channel names. The function will skip addition of
    properties if the `chanMap.mat` file is not found in the given session path.

    Parameters
    ----------
    recording_extractor : BaseRecording from spikeinterface
        The recording extractor to which the metadata will be added.
    session_path : Path or str
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

    session_path = Path(session_path)
    chan_map_file_path = session_path / f"chanMap.mat"
    if chan_map_file_path.is_file():
        from pymatreader import read_mat

        channel_map_data = read_mat(chan_map_file_path)
        channel_groups = channel_map_data["connected"]

        channel_indices = channel_map_data["chanMap0ind"]
        channel_ids = [str(channel_indices[i]) for i in channel_indices]

        channel_name = [
            f"ch{channel_index}grp{channel_group}"
            for channel_index, channel_group in zip(channel_indices, channel_groups)
        ]
        base_ids = recording_extractor.get_channel_ids()
        recording_extractor = recording_extractor.channel_slice(channel_ids=base_ids, renamed_channel_ids=channel_ids)
        x_coords = channel_map_data["xcoords"]
        y_coords = channel_map_data["ycoords"]
        locations = np.array((x_coords, y_coords)).T.astype("float32")
        recording_extractor.set_channel_locations(channel_ids=channel_ids, locations=locations)

        recording_extractor.set_property(key="channel_name", values=channel_name)
        recording_extractor.set_property(key="group", ids=channel_ids, values=channel_groups)

    return recording_extractor


class CellExplorerRecordingInterface(BaseRecordingExtractorInterface):
    """
    This interface serves as an temporary solution for integrating CellExplorer metadata during a conversion process.

    CellExplorer's new format (https://cellexplorer.org/) contains a `session.mat` file, which has the following field:

    * Sampling frequency
    * Gains for both raw data (held in a file named session.dat) and lfp (located in session.lfp)
    * Dtype for both raw data and lfp.

    Link to the documentation detailing the file's structure:
    https://cellexplorer.org/datastructure/data-structure-and-format/#session-metadata

    If the binary file is available (session.dat or session.lfp), the interface will use the
    `BinaryRecordingExtractor` from spikeinterface to load the data. Otherwise, it will use the
    `NumpyRecording` extractor, which is a dummy extractor that only contains metadata.  This can be used to add
    the electrode using `write_electrical_series=False` as a conversion option.

    The metadata for this electrode is also extracted from the `session.mat` file. The logic of the extraction is
    described on the function:

    `add_channel_metadata_to_recorder_from_session_file`.

    Note that, while all the new
    data produced by CellExplorer should have this file it is not clear if the channel metadata is always available.

    Besides, the current implementation also supports extracting channel metadata from the `chanMap.mat` file used by
    Kilosort. The logic of the extraction is described on the function:

    `add_channel_metadata_to_recorder_from_channel_map_file`.

    Bear in mind that this file is not always available for all datasets.

    From the documentation we also know that channel data can also be found in the following files:
    * `basename.ChannelName.channelinfo.mat`: general data container for channel-wise dat
    * `basename.chanCoords.channelinfo.mat`: contains the coordinates of the electrodes in the probe
    * `basename.ccf.channelinfo.mat`: Allen Institute’s Common Coordinate Framework (CCF)

    Detailed information can be found in the following link
    https://cellexplorer.org/datastructure/data-structure-and-format/#channels

    Future versions of this interface will support the extraction of this metadata from these files.
    """

    sampling_frequency_key = "sr"
    binary_file_extension = "dat"

    def __init__(self, folder_path: FolderPathType, verbose: bool = True, es_key: str = "ElectricalSeries"):
        self.folder_path = Path(folder_path)

        # No super here, we need to do everything by hand
        self.verbose = verbose
        self.es_key = es_key
        self.subset_channels = None
        self.source_data = dict(folder_path=folder_path)
        self._number_of_segments = 1  # CellExplorer is mono segment

        self.session = self.folder_path.name
        session_data_file_path = self.folder_path / f"{self.session}.session.mat"
        assert session_data_file_path.is_file(), f"File {session_data_file_path} does not exist"

        ignore_fields = ["animal", "behavioralTracking", "timeSeries", "spikeSorting", "epochs"]
        from pymatreader import read_mat

        session_data = read_mat(filename=session_data_file_path, ignore_fields=ignore_fields)["session"]
        extracellular_data = session_data["extracellular"]
        num_channels = int(extracellular_data["nChannels"])
        gain = float(extracellular_data["leastSignificantBit"])  # 0.195
        gains_to_uv = np.ones(num_channels) * gain
        dtype = np.dtype(extracellular_data["precision"])
        sampling_frequency = float(extracellular_data[self.sampling_frequency_key])

        # Channels in CellExplorer are 1-indexed
        channel_ids = [str(1 + i) for i in range(num_channels)]
        binary_file_path = self.folder_path / f"{self.session}.{self.binary_file_extension}"
        if binary_file_path.is_file():
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
        else:
            from spikeinterface.core.numpyextractors import NumpyRecording

            traces_list = [np.empty(shape=(1, num_channels))]
            dummy_recording = NumpyRecording(
                traces_list=traces_list,
                sampling_frequency=sampling_frequency,
                channel_ids=channel_ids,
            )

            self.recording_extractor = dummy_recording
            self.recording_extractor.set_channel_gains(channel_ids=channel_ids, gains=np.ones(num_channels) * gain)

        self.recording_extractor = add_channel_metadata_to_recorder_from_session_file(
            recording_extractor=self.recording_extractor, session_path=self.folder_path
        )

        self.recording_extractor = add_channel_metadata_to_recorder_from_channel_map_file(
            recording_extractor=self.recording_extractor, session_path=self.folder_path
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
        compression: Optional[str] = None,
        compression_opts: Optional[int] = None,
        iterator_type: str = "v2",
        iterator_opts: Optional[dict] = None,
    ):
        return super().add_to_nwbfile(
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

        # Temporary hack to get sampling frequency from the spikes cellinfo file until next SI release.
        import h5py

        try:
            matlab_file = scipy.io.loadmat(file_name=str(file_path), simplify_cells=True)
            if "spikes" not in matlab_file.keys():
                raise KeyError(f"CellExplorer file '{file_path}' does not contain 'spikes' field.")
            spikes_mat = matlab_file["spikes"]
            assert isinstance(spikes_mat, dict), f"field `spikes` must be a dict, not {type(spikes_mat)}!"

        except NotImplementedError:
            matlab_file = h5py.File(name=file_path, mode="r")
            if "spikes" not in matlab_file.keys():
                raise KeyError(f"CellExplorer file '{file_path}' does not contain 'spikes' field.")
            spikes_mat = matlab_file["spikes"]
            assert isinstance(spikes_mat, h5py.Group), f"field `spikes` must be a Group, not {type(spikes_mat)}!"

        sampling_frequency = spikes_mat.get("sr", None)
        sampling_frequency = (
            sampling_frequency[()] if isinstance(sampling_frequency, h5py.Dataset) else sampling_frequency
        )

        super().__init__(spikes_matfile_path=file_path, sampling_frequency=sampling_frequency, verbose=verbose)
        self.source_data = dict(file_path=file_path)
        spikes_matfile_path = Path(file_path)

        session_path = Path(file_path).parent
        session_id = session_path.stem

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
        celltype_file_path = session_path / f"{session_id}.CellClass.cellinfo.mat"
        if celltype_file_path.is_file():
            celltype_info = scipy.io.loadmat(celltype_file_path).get("CellClass", np.empty(0))
            if "label" in celltype_info.dtype.names:
                self.sorting_extractor.set_property(
                    ids=unit_ids,
                    key="cell_type",
                    values=[str(celltype_mapping[str(x[0])]) for x in celltype_info["label"][0][0][0]],
                )

        # Register a dummy recorder to write the recording device metadata if desired

        session_data_file_path = session_path / f"{session_id}.session.mat"
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
            dummy_recording_extractor = add_channel_metadata_to_recorder_from_session_file(
                recording_extractor=dummy_recording_extractor,
                session_path=session_path,
            )

            dummy_recording_extractor = add_channel_metadata_to_recorder_from_channel_map_file(
                recording_extractor=dummy_recording_extractor,
                session_path=session_path,
            )

            # Need a time vector for the recording extractor
            last_spikes_frame = self.sorting_extractor.get_all_spike_trains()[0][0][-1]
            time_vector = np.arange(last_spikes_frame + 1) / sampling_frequency
            dummy_recording_extractor._recording_segments[0].time_vector = time_vector
            self.sorting_extractor.register_recording(recording=dummy_recording_extractor)

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
