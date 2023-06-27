import json
from typing import Any, Dict, List, Literal, Optional, Union

import numpy as np
from pynwb import NWBFile
from pynwb.device import Device
from pynwb.ecephys import ElectricalSeries, ElectrodeGroup

from ...baseextractorinterface import BaseExtractorInterface
from ...utils import NWBMetaDataEncoder, get_base_schema, get_schema_from_hdmf_class


class BaseRecordingExtractorInterface(BaseExtractorInterface):
    """Parent class for all RecordingExtractorInterfaces."""

    keywords = BaseExtractorInterface.keywords + ["extracellular electrophysiology", "voltage", "recording"]
    ExtractorModuleName = "spikeinterface.extractors"

    def __init__(self, verbose: bool = True, es_key: str = "ElectricalSeries", **source_data):
        """
        Parameters
        ----------
        verbose : bool, default: True
            If True, will print out additional information.
        es_key : str, default: "ElectricalSeries"
            The key of this ElectricalSeries in the metadata dictionary.
        source_data : dict
            The key-value pairs of extractor-specific arguments.

        """
        super().__init__(**source_data)
        self.recording_extractor = self.get_extractor()(**source_data)
        self.subset_channels = None
        self.verbose = verbose
        self.es_key = es_key
        self._number_of_segments = self.recording_extractor.get_num_segments()

    def get_metadata_schema(self) -> dict:
        """Compile metadata schema for the RecordingExtractor."""
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ecephys"] = get_base_schema(tag="Ecephys")
        metadata_schema["properties"]["Ecephys"]["required"] = ["Device", "ElectrodeGroup"]
        metadata_schema["properties"]["Ecephys"]["properties"] = dict(
            Device=dict(type="array", minItems=1, items={"$ref": "#/properties/Ecephys/properties/definitions/Device"}),
            ElectrodeGroup=dict(
                type="array", minItems=1, items={"$ref": "#/properties/Ecephys/properties/definitions/ElectrodeGroup"}
            ),
            Electrodes=dict(
                type="array",
                minItems=0,
                renderForm=False,
                items={"$ref": "#/properties/Ecephys/properties/definitions/Electrodes"},
            ),
        )
        # Schema definition for arrays
        metadata_schema["properties"]["Ecephys"]["properties"]["definitions"] = dict(
            Device=get_schema_from_hdmf_class(Device),
            ElectrodeGroup=get_schema_from_hdmf_class(ElectrodeGroup),
            Electrodes=dict(
                type="object",
                additionalProperties=False,
                required=["name"],
                properties=dict(
                    name=dict(type="string", description="name of this electrodes column"),
                    description=dict(type="string", description="description of this electrodes column"),
                ),
            ),
        )

        if self.es_key is not None:
            metadata_schema["properties"]["Ecephys"]["properties"].update(
                {self.es_key: get_schema_from_hdmf_class(ElectricalSeries)}
            )
        return metadata_schema

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()

        channel_groups_array = self.recording_extractor.get_channel_groups()
        unique_channel_groups = set(channel_groups_array) if channel_groups_array is not None else ["ElectrodeGroup"]
        electrode_metadata = [
            dict(name=str(group_id), description="no description", location="unknown", device="DeviceEcephys")
            for group_id in unique_channel_groups
        ]

        metadata["Ecephys"] = dict(
            Device=[dict(name="DeviceEcephys", description="no description")],
            ElectrodeGroup=electrode_metadata,
        )

        if self.es_key is not None:
            metadata["Ecephys"][self.es_key] = dict(
                name=self.es_key, description=f"Acquisition traces for the {self.es_key}."
            )

        return metadata

    def get_electrode_table_json(self) -> List[Dict[str, Any]]:
        """
        A convenience function for collecting and organizing the property values of the underlying recording extractor.

        Uses the structure of the Handsontable (list of dict entries) component of the NWB GUIDE.
        """
        property_names = set(self.recording_extractor.get_property_keys()) - {
            "contact_vector",  # TODO: add consideration for contact vector (probeinterface) info
            "location",  # testing
        }
        electrode_ids = self.recording_extractor.get_channel_ids()

        table = list()
        for electrode_id in electrode_ids:
            electrode_column = dict()
            for property_name in property_names:
                recording_property_value = self.recording_extractor.get_property(key=property_name, ids=[electrode_id])[
                    0  # First axis is always electodes in SI
                ]  # Since only fetching one electrode at a time, use trivial zero-index
                electrode_column.update({property_name: recording_property_value})
            table.append(electrode_column)
        table_as_json = json.loads(json.dumps(table, cls=NWBMetaDataEncoder))
        return table_as_json

    def get_original_timestamps(self) -> Union[np.ndarray, List[np.ndarray]]:
        """
        Retrieve the original unaltered timestamps for the data in this interface.

        This function should retrieve the data on-demand by re-initializing the IO.

        Returns
        -------
        timestamps: numpy.ndarray or list of numpy.ndarray
            The timestamps for the data stream; if the recording has multiple segments, then a list of timestamps is returned.
        """
        new_recording = self.get_extractor()(
            **{keyword: value for keyword, value in self.source_data.items() if keyword not in ["verbose", "es_key"]}
        )
        if self._number_of_segments == 1:
            return new_recording.get_times()
        else:
            return [
                new_recording.get_times(segment_index=segment_index)
                for segment_index in range(self._number_of_segments)
            ]

    def get_timestamps(self) -> Union[np.ndarray, List[np.ndarray]]:
        """
        Retrieve the timestamps for the data in this interface.

        Returns
        -------
        timestamps: numpy.ndarray or list of numpy.ndarray
            The timestamps for the data stream; if the recording has multiple segments, then a list of timestamps is returned.
        """
        if self._number_of_segments == 1:
            return self.recording_extractor.get_times()
        else:
            return [
                self.recording_extractor.get_times(segment_index=segment_index)
                for segment_index in range(self._number_of_segments)
            ]

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray):
        assert (
            self._number_of_segments == 1
        ), "This recording has multiple segments; please use 'align_segment_timestamps' instead."

        self.recording_extractor.set_times(times=aligned_timestamps)

    def set_aligned_segment_timestamps(self, aligned_segment_timestamps: List[np.ndarray]):
        """
        Replace all timestamps for all segments in this interface with those aligned to the common session start time.

        Must be in units seconds relative to the common 'session_start_time'.

        Parameters
        ----------
        aligned_segment_timestamps : list of numpy.ndarray
            The synchronized timestamps for segment of data in this interface.
        """
        assert isinstance(
            aligned_segment_timestamps, list
        ), "Recording has multiple segment! Please pass a list of timestamps to align each segment."
        assert (
            len(aligned_segment_timestamps) == self._number_of_segments
        ), f"The number of timestamp vectors ({len(aligned_segment_timestamps)}) does not match the number of segments ({self._number_of_segments})!"

        for segment_index in range(self._number_of_segments):
            self.recording_extractor.set_times(
                times=aligned_segment_timestamps[segment_index], segment_index=segment_index
            )

    def set_aligned_starting_time(self, aligned_starting_time: float):
        if self._number_of_segments == 1:
            self.set_aligned_timestamps(aligned_timestamps=self.get_timestamps() + aligned_starting_time)
        else:
            self.set_aligned_segment_timestamps(
                aligned_segment_timestamps=[
                    segment_timestamps + aligned_starting_time for segment_timestamps in self.get_timestamps()
                ]
            )

    def set_aligned_segment_starting_times(self, aligned_segment_starting_times: List[float]):
        """
        Align the starting time for each segment in this interface relative to the common session start time.

        Must be in units seconds relative to the common 'session_start_time'.

        Parameters
        ----------
        aligned_segment_starting_times : list of floats
            The starting time for each segment of data in this interface.
        """
        assert len(aligned_segment_starting_times) == self._number_of_segments, (
            f"The length of the starting_times ({len(aligned_segment_starting_times)}) does not match the "
            "number of segments ({self._number_of_segments})!"
        )

        if self._number_of_segments == 1:
            self.set_aligned_starting_time(aligned_starting_time=aligned_segment_starting_times[0])
        else:
            aligned_segment_timestamps = [
                segment_timestamps + aligned_segment_starting_time
                for segment_timestamps, aligned_segment_starting_time in zip(
                    self.get_timestamps(), aligned_segment_starting_times
                )
            ]
            self.set_aligned_segment_timestamps(aligned_segment_timestamps=aligned_segment_timestamps)

    def align_by_interpolation(
        self,
        unaligned_timestamps: np.ndarray,
        aligned_timestamps: np.ndarray,
    ):
        if self._number_of_segments == 1:
            self.set_aligned_timestamps(
                aligned_timestamps=np.interp(x=self.get_timestamps(), xp=unaligned_timestamps, fp=aligned_timestamps)
            )
        else:
            raise NotImplementedError("Multi-segment support for aligning by interpolation has not been added yet.")

    def subset_recording(self, stub_test: bool = False):
        """
        Subset a recording extractor according to stub and channel subset options.

        Parameters
        ----------
        stub_test : bool, default: False
        """
        from spikeinterface.core.segmentutils import ConcatenateSegmentRecording

        max_frames = 100

        recording_extractor = self.recording_extractor
        number_of_segments = recording_extractor.get_num_segments()
        recording_segments = [recording_extractor.select_segments([index]) for index in range(number_of_segments)]
        end_frame_list = [min(max_frames, segment.get_num_frames()) for segment in recording_segments]
        recording_segments_stubbed = [
            segment.frame_slice(start_frame=0, end_frame=end_frame)
            for segment, end_frame in zip(recording_segments, end_frame_list)
        ]
        recording_extractor = ConcatenateSegmentRecording(recording_segments_stubbed)

        return recording_extractor

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: Optional[dict] = None,
        stub_test: bool = False,
        starting_time: Optional[float] = None,
        write_as: Literal["raw", "lfp", "processed"] = "raw",
        write_electrical_series: bool = True,
        compression: Optional[str] = "gzip",
        compression_opts: Optional[int] = None,
        iterator_type: str = "v2",
        iterator_opts: Optional[dict] = None,
    ):
        """
        Primary function for converting raw (unprocessed) RecordingExtractor data to the NWB standard.

        Parameters
        ----------
        nwbfile : NWBFile
            NWBFile to which the recording information is to be added
        metadata : dict, optional
            metadata info for constructing the NWB file.
            Should be of the format::

                metadata['Ecephys']['ElectricalSeries'] = dict(name=my_name, description=my_description)
        The default is False (append mode).
        starting_time : float, optional
            Sets the starting time of the ElectricalSeries to a manually set value.
        stub_test : bool, default: False
            If True, will truncate the data to run the conversion faster and take up less memory.
        write_as : {'raw', 'lfp', 'processed'}
        write_electrical_series : bool, default: True
            Electrical series are written in acquisition. If False, only device, electrode_groups,
            and electrodes are written to NWB.
        compression : {'gzip', 'lzf', None}
            Type of compression to use.
            Set to None to disable all compression.
        compression_opts : int, default: 4
            Only applies to compression="gzip". Controls the level of the GZIP.
        iterator_type : {'v2', 'v1'}
            The type of DataChunkIterator to use.
            'v1' is the original DataChunkIterator of the hdmf data_utils.
            'v2' is the locally developed RecordingExtractorDataChunkIterator, which offers full control over chunking.
        iterator_opts : dict, optional
            Dictionary of options for the RecordingExtractorDataChunkIterator (iterator_type='v2').
            Valid options are
                buffer_gb : float, default: 1.0
                    In units of GB. Recommended to be as much free RAM as available. Automatically calculates suitable
                    buffer shape.
                buffer_shape : tuple, optional
                    Manual specification of buffer shape to return on each iteration.
                    Must be a multiple of chunk_shape along each axis.
                    Cannot be set if `buffer_gb` is specified.
                chunk_mb : float. default: 1.0
                    Should be below 1 MB. Automatically calculates suitable chunk shape.
                chunk_shape : tuple, optional
                    Manual specification of the internal chunk shape for the HDF5 dataset.
                    Cannot be set if `chunk_mb` is also specified.
                display_progress : bool, default: False
                    Display a progress bar with iteration rate and estimated completion time.
                progress_bar_options : dict, optional
                    Dictionary of keyword arguments to be passed directly to tqdm.
                    See https://github.com/tqdm/tqdm#parameters for options.
        """
        from ...tools.spikeinterface import add_recording

        if stub_test or self.subset_channels is not None:
            recording = self.subset_recording(stub_test=stub_test)
        else:
            recording = self.recording_extractor

        add_recording(
            recording=recording,
            nwbfile=nwbfile,
            metadata=metadata,
            starting_time=starting_time,
            write_as=write_as,
            write_electrical_series=write_electrical_series,
            es_key=self.es_key,
            compression=compression,
            compression_opts=compression_opts,
            iterator_type=iterator_type,
            iterator_opts=iterator_opts,
        )
