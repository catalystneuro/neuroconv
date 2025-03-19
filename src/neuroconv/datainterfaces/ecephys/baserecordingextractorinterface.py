from typing import Literal, Optional, Union

import numpy as np
from pynwb import NWBFile
from pynwb.device import Device
from pynwb.ecephys import ElectricalSeries, ElectrodeGroup

from ...baseextractorinterface import BaseExtractorInterface
from ...utils import (
    DeepDict,
    get_base_schema,
    get_schema_from_hdmf_class,
)


class BaseRecordingExtractorInterface(BaseExtractorInterface):
    """Parent class for all RecordingExtractorInterfaces."""

    keywords = ("extracellular electrophysiology", "voltage", "recording")

    ExtractorModuleName = "spikeinterface.extractors"

    def __init__(self, verbose: bool = False, es_key: str = "ElectricalSeries", **source_data):
        """
        Parameters
        ----------
        verbose : bool, default: False
            If True, will print out additional information.
        es_key : str, default: "ElectricalSeries"
            The key of this ElectricalSeries in the metadata dictionary.
        source_data : dict
            The key-value pairs of extractor-specific arguments.

        """

        super().__init__(**source_data)
        self.recording_extractor = self._extractor_instance
        property_names = self.recording_extractor.get_property_keys()
        # TODO remove this and go and change all the uses of channel_name once spikeinterface > 0.101.0 is released
        if "channel_name" not in property_names and "channel_names" in property_names:
            channel_names = self.recording_extractor.get_property("channel_names")
            self.recording_extractor.set_property("channel_name", channel_names)
            self.recording_extractor.delete_property("channel_names")

        self.subset_channels = None
        self.verbose = verbose
        self.es_key = es_key
        self._number_of_segments = self.recording_extractor.get_num_segments()

    def get_metadata_schema(self) -> dict:
        """
        Compile metadata schema for the RecordingExtractor.

        Returns
        -------
        dict
            The metadata schema dictionary containing definitions for Device, ElectrodeGroup,
            Electrodes, and optionally ElectricalSeries.
        """
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ecephys"] = get_base_schema(tag="Ecephys")
        metadata_schema["properties"]["Ecephys"]["required"] = ["Device", "ElectrodeGroup"]
        metadata_schema["properties"]["Ecephys"]["properties"] = dict(
            Device=dict(type="array", minItems=1, items={"$ref": "#/properties/Ecephys/definitions/Device"}),
            ElectrodeGroup=dict(
                type="array", minItems=1, items={"$ref": "#/properties/Ecephys/definitions/ElectrodeGroup"}
            ),
            Electrodes=dict(
                type="array",
                minItems=0,
                renderForm=False,
                items={"$ref": "#/properties/Ecephys/definitions/Electrodes"},
            ),
        )
        # Schema definition for arrays
        metadata_schema["properties"]["Ecephys"]["definitions"] = dict(
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

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()

        from ...tools.spikeinterface.spikeinterface import _get_group_name

        channel_groups_array = _get_group_name(recording=self.recording_extractor)
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

    @property
    def channel_ids(self):
        "Gets the channel ids of the data."
        return self.recording_extractor.get_channel_ids()

    def get_original_timestamps(self) -> Union[np.ndarray, list[np.ndarray]]:
        """
        Retrieve the original unaltered timestamps for the data in this interface.

        This function should retrieve the data on-demand by re-initializing the IO.

        Returns
        -------
        timestamps: numpy.ndarray or list of numpy.ndarray
            The timestamps for the data stream; if the recording has multiple segments, then a list of timestamps is returned.
        """
        new_recording = self.get_extractor()(
            **{
                keyword: value
                for keyword, value in self.extractor_kwargs.items()
                if keyword not in ["verbose", "es_key"]
            }
        )
        if self._number_of_segments == 1:
            return new_recording.get_times()
        else:
            return [
                new_recording.get_times(segment_index=segment_index)
                for segment_index in range(self._number_of_segments)
            ]

    def get_timestamps(self) -> Union[np.ndarray, list[np.ndarray]]:
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

        self.recording_extractor.set_times(times=aligned_timestamps, with_warning=False)

    def set_aligned_segment_timestamps(self, aligned_segment_timestamps: list[np.ndarray]):
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
                times=aligned_segment_timestamps[segment_index],
                segment_index=segment_index,
                with_warning=False,
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

    def set_aligned_segment_starting_times(self, aligned_segment_starting_times: list[float]):
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

    def set_probe(self, probe, group_mode: Literal["by_shank", "by_probe"]):
        """
        Set the probe information via a ProbeInterface object.

        Parameters
        ----------
        probe : probeinterface.Probe
            The probe object.
        group_mode : {'by_shank', 'by_probe'}
            How to group the channels. If 'by_shank', channels are grouped by the shank_id column.
            If 'by_probe', channels are grouped by the probe_id column.
            This is a required parameter to avoid the pitfall of using the wrong mode.
        """
        # Set the probe to the recording extractor
        self.recording_extractor.set_probe(
            probe,
            in_place=True,
            group_mode=group_mode,
        )
        # Spike interface sets the "group" property
        # But neuroconv allows "group_name" property to override spike interface "group" value
        self.recording_extractor.set_property("group_name", self.recording_extractor.get_property("group").astype(str))

    def has_probe(self) -> bool:
        """
        Check if the recording extractor has probe information.

        Returns
        -------
        bool
            True if the recording extractor has probe information, False otherwise.
        """
        return self.recording_extractor.has_probe()

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
            If True, only a subset of frames will be included.

        Returns
        -------
        spikeinterface.core.BaseRecording
            The subsetted recording extractor.
        """
        from spikeinterface.core.segmentutils import AppendSegmentRecording

        max_frames = 100

        recording_extractor = self.recording_extractor
        number_of_segments = recording_extractor.get_num_segments()
        recording_segments = [recording_extractor.select_segments([index]) for index in range(number_of_segments)]
        end_frame_list = [min(max_frames, segment.get_num_frames()) for segment in recording_segments]
        recording_segments_stubbed = [
            segment.frame_slice(start_frame=0, end_frame=end_frame)
            for segment, end_frame in zip(recording_segments, end_frame_list)
        ]
        recording_extractor_stubbed = AppendSegmentRecording(recording_list=recording_segments_stubbed)

        times_stubbed = [
            recording_extractor.get_times(segment_index=segment_index)[:end_frame]
            for segment_index, end_frame in zip(range(number_of_segments), end_frame_list)
        ]
        for segment_index in range(number_of_segments):
            recording_extractor_stubbed.set_times(
                times=times_stubbed[segment_index],
                segment_index=segment_index,
                with_warning=False,
            )

        return recording_extractor_stubbed

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: Optional[dict] = None,
        stub_test: bool = False,
        starting_time: Optional[float] = None,
        write_as: Literal["raw", "lfp", "processed"] = "raw",
        write_electrical_series: bool = True,
        iterator_type: Optional[str] = "v2",
        iterator_opts: Optional[dict] = None,
        always_write_timestamps: bool = False,
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

        starting_time : float, optional
            Sets the starting time of the ElectricalSeries to a manually set value.
        stub_test : bool, default: False
            If True, will truncate the data to run the conversion faster and take up less memory.
        write_as : {'raw', 'processed', 'lfp'}, default='raw'
            Specifies how to save the trace data in the NWB file. Options are:
            - 'raw': Save the data in the acquisition group.
            - 'processed': Save the data as FilteredEphys in a processing module.
            - 'lfp': Save the data as LFP in a processing module.

        write_electrical_series : bool, default: True
            Electrical series are written in acquisition. If False, only device, electrode_groups,
            and electrodes are written to NWB.
        iterator_type : {'v2'}
            The type of DataChunkIterator to use.
            'v2' is the locally developed RecordingExtractorDataChunkIterator, which offers full control over chunking
        iterator_opts : dict, optional
            Dictionary of options for the RecordingExtractorDataChunkIterator (iterator_type='v2').
            Valid options are:

            * buffer_gb : float, default: 1.0
                In units of GB. Recommended to be as much free RAM as available. Automatically calculates suitable
                buffer shape.
            * buffer_shape : tuple, optional
                Manual specification of buffer shape to return on each iteration.
                Must be a multiple of chunk_shape along each axis.
                Cannot be set if `buffer_gb` is specified.
            * chunk_mb : float. default: 1.0
                Should be below 1 MB. Automatically calculates suitable chunk shape.
            * chunk_shape : tuple, optional
                Manual specification of the internal chunk shape for the HDF5 dataset.
                Cannot be set if `chunk_mb` is also specified.
            * display_progress : bool, default: False
                Display a progress bar with iteration rate and estimated completion time.
            * progress_bar_options : dict, optional
                Dictionary of keyword arguments to be passed directly to tqdm.
                See https://github.com/tqdm/tqdm#parameters for options.
        always_write_timestamps : bool, default: False
            Set to True to always write timestamps.
            By default (False), the function checks if the timestamps are uniformly sampled, and if so, stores the data
            using a regular sampling rate instead of explicit timestamps. If set to True, timestamps will be written
            explicitly, regardless of whether the sampling rate is uniform.
        """
        from ...tools.spikeinterface import add_recording_to_nwbfile

        if stub_test or self.subset_channels is not None:
            recording = self.subset_recording(stub_test=stub_test)
        else:
            recording = self.recording_extractor

        metadata = metadata or self.get_metadata()

        add_recording_to_nwbfile(
            recording=recording,
            nwbfile=nwbfile,
            metadata=metadata,
            starting_time=starting_time,
            write_as=write_as,
            write_electrical_series=write_electrical_series,
            es_key=self.es_key,
            iterator_type=iterator_type,
            iterator_opts=iterator_opts,
            always_write_timestamps=always_write_timestamps,
        )
