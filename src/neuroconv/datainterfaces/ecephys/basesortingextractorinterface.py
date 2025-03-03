from copy import deepcopy
from typing import Literal, Optional, Union

import numpy as np
from pynwb import NWBFile
from pynwb.device import Device
from pynwb.ecephys import ElectrodeGroup

from .baserecordingextractorinterface import BaseRecordingExtractorInterface
from ...baseextractorinterface import BaseExtractorInterface
from ...utils import DeepDict, get_base_schema, get_schema_from_hdmf_class


class BaseSortingExtractorInterface(BaseExtractorInterface):
    """Primary class for all SortingExtractor interfaces."""

    keywords = ("extracellular electrophysiology", "spike sorting")

    ExtractorModuleName = "spikeinterface.extractors"

    def __init__(self, verbose: bool = False, **source_data):

        super().__init__(**source_data)
        self.sorting_extractor = self.get_extractor()(**source_data)
        self.verbose = verbose
        self._number_of_segments = self.sorting_extractor.get_num_segments()

    def get_metadata_schema(self) -> dict:
        """
        Compile metadata schema for the RecordingExtractor.

        Returns
        -------
        dict
            The metadata schema dictionary containing definitions for Device, ElectrodeGroup,
            Electrodes, and UnitProperties.
        """

        # Initiate Ecephys metadata
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ecephys"] = get_base_schema(tag="Ecephys")
        metadata_schema["properties"]["Ecephys"]["required"] = []
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
            UnitProperties=dict(
                type="array",
                minItems=0,
                renderForm=False,
                items={"$ref": "#/properties/Ecephys/definitions/UnitProperties"},
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
            UnitProperties=dict(
                type="object",
                additionalProperties=False,
                required=["name"],
                properties=dict(
                    name=dict(type="string", description="name of this units column"),
                    description=dict(type="string", description="description of this units column"),
                ),
            ),
        )
        return metadata_schema

    @property
    def units_ids(self):
        "Gets the units ids of the data."
        return self.sorting_extractor.get_unit_ids()

    def register_recording(self, recording_interface: BaseRecordingExtractorInterface):
        self.sorting_extractor.register_recording(recording=recording_interface.recording_extractor)

    def get_original_timestamps(self) -> np.ndarray:
        raise NotImplementedError(
            "Unable to fetch original timestamps for a SortingInterface since it relies upon an attached recording."
        )

    def get_timestamps(self) -> Union[np.ndarray, list[np.ndarray]]:
        if not self.sorting_extractor.has_recording():
            raise NotImplementedError(
                "In order to align timestamps for a SortingInterface, it must have a recording "
                "object attached to it! Please attach one by calling `.register_recording(recording_interface=...)`."
            )
        if self._number_of_segments == 1:
            return self.sorting_extractor._recording.get_times()
        else:
            return [
                self.sorting_extractor._recording.get_times(segment_index=segment_index)
                for segment_index in range(self._number_of_segments)
            ]

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray):
        """
        Replace all timestamps for the attached interface with those aligned to the common session start time.

        Must be in units seconds relative to the common 'session_start_time'.
        Must have a single-segment RecordingInterface attached; call `.register_recording(recording_interface=...)` to accomplish this.

        When a SortingInterface has a recording attached, it infers the timing via the frame indices of the
        timestamps from the corresponding recording segment. This method aligns the timestamps of that recording
        so that the SortingExtractor can automatically infer the timing from the frames.

        Parameters
        ----------
        aligned_timestamps : numpy.ndarray or list of numpy.ndarray
            The synchronized timestamps for data in this interface.
            If there is more than one segment in the sorting/recording pair, then
        """
        if not self.sorting_extractor.has_recording():
            raise NotImplementedError(
                "In order to align timestamps for a SortingInterface, it must have a recording "
                "object attached to it! Please attach one by calling `.register_recording(recording_interface=...)`."
            )
        assert (
            self._number_of_segments == 1
        ), "This recording has multiple segments; please use 'set_aligned_segment_timestamps' instead."

        if self._number_of_segments == 1:
            self.sorting_extractor._recording.set_times(times=aligned_timestamps, with_warning=False)
        else:
            assert isinstance(
                aligned_timestamps, list
            ), "Recording has multiple segment! Please pass a list of timestamps to align each segment."
            assert (
                len(aligned_timestamps) == self._number_of_segments
            ), f"The number of timestamp vectors ({len(aligned_timestamps)}) does not match the number of segments ({self._number_of_segments})!"

            for segment_index in range(self._number_of_segments):
                self.sorting_extractor._recording.set_times(
                    times=aligned_timestamps[segment_index],
                    segment_index=segment_index,
                    with_warning=False,
                )

    def set_aligned_segment_timestamps(self, aligned_segment_timestamps: list[np.ndarray]):
        """
        Replace all timestamps for all segments in this interface with those aligned to the common session start time.

        Must be in units seconds relative to the common 'session_start_time'.
        Must have a multi-segment RecordingInterface attached by calling `.register_recording(recording_interface=...)`.

        Parameters
        ----------
        aligned_segment_timestamps : list of numpy.ndarray
            The synchronized timestamps for segment of data in this interface.
        """
        if not self.sorting_extractor.has_recording():
            raise NotImplementedError(
                "In order to align timestamps for a SortingInterface, it must have a recording "
                "object attached to it! Please attach one by calling `.register_recording(recording_interface=...)`."
            )
        assert isinstance(
            aligned_segment_timestamps, list
        ), "Recording has multiple segment! Please pass a list of timestamps to align each segment."
        assert (
            len(aligned_segment_timestamps) == self._number_of_segments
        ), f"The number of timestamp vectors ({len(aligned_segment_timestamps)}) does not match the number of segments ({self._number_of_segments})!"

        for segment_index in range(self._number_of_segments):
            self.sorting_extractor._recording.set_times(
                times=aligned_segment_timestamps[segment_index],
                segment_index=segment_index,
                with_warning=False,
            )

    def set_aligned_starting_time(self, aligned_starting_time: float):
        if self.sorting_extractor.has_recording():
            if self._number_of_segments == 1:
                self.set_aligned_timestamps(aligned_timestamps=self.get_timestamps() + aligned_starting_time)
            else:
                self.set_aligned_segment_timestamps(
                    [segment_timestamps + aligned_starting_time for segment_timestamps in self.get_timestamps()]
                )
        else:
            for sorting_segment in self.sorting_extractor._sorting_segments:
                if sorting_segment._t_start is None:
                    sorting_segment._t_start = aligned_starting_time
                else:
                    sorting_segment._t_start += aligned_starting_time

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
            f"The length of the starting_times ({len(aligned_segment_starting_times)}) does not match the number "
            f"of segments ({self._number_of_segments})!"
        )

        if self.sorting_extractor.has_recording():
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
        else:
            for sorting_segment, aligned_segment_starting_time in zip(
                self.sorting_extractor._sorting_segments, aligned_segment_starting_times
            ):
                sorting_segment._t_start = aligned_segment_starting_time

    def subset_sorting(self):
        """
        Generate a subset of the sorting extractor based on spike timing data.

        This method identifies the earliest spike time across all units in the sorting extractor and creates a
        subset of the sorting data up to 110% of the earliest spike time. If the sorting extractor is associated
        with a recording, the subset is further limited by the total number of samples in the recording.

        Returns
        -------
        SortingExtractor
            A new `SortingExtractor` object representing the subset of the original sorting data,
            sliced from the start frame to the calculated end frame.
        """
        max_min_spike_time = max(
            [
                min(x)
                for y in self.sorting_extractor.get_unit_ids()
                for x in [self.sorting_extractor.get_unit_spike_train(y)]
                if any(x)
            ]
        )
        end_frame = int(1.1 * max_min_spike_time)
        if self.sorting_extractor.has_recording():
            end_frame = min(end_frame, self.sorting_extractor._recording.get_total_samples())
        stub_sorting_extractor = self.sorting_extractor.frame_slice(start_frame=0, end_frame=end_frame)
        return stub_sorting_extractor

    def add_channel_metadata_to_nwb(self, nwbfile: NWBFile, metadata: Optional[DeepDict] = None):
        """
        Add channel metadata to an NWBFile object using information extracted from a SortingExtractor and
        optional metadata.

        This function attempts to add devices, electrode groups, and electrodes to the NWBFile. If a recording is
        associated with the SortingExtractor, it is used for metadata addition. Otherwise, it attempts to create a dummy
        NumpyRecording based on the provided metadata. If neither is available, the function warns the user and skips the
        metadata addition.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWBFile object to which the metadata is added.
        metadata : Optional[DeepDict]
            Optional metadata to use for the addition of electrode-related data. If it's provided, it should contain an
            "Ecephys" field with a nested "Electrodes" field.

        Returns
        -------
        None

        Raises
        ------
        Warning
            If there's no recording in the sorting extractor and no electrodes metadata in the provided metadata, a warning
            is raised and the function returns None.

        Notes
        -----
        This function adds metadata to the `nwbfile` in-place, meaning the `nwbfile` object is modified directly.
        """
        from ...tools.spikeinterface import (
            add_devices_to_nwbfile,
            add_electrode_groups_to_nwbfile,
            add_electrodes_to_nwbfile,
        )

        if hasattr(self, "generate_recording_with_channel_metadata"):
            recording = self.generate_recording_with_channel_metadata()

            add_devices_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
            add_electrode_groups_to_nwbfile(recording=recording, nwbfile=nwbfile, metadata=metadata)
            add_electrodes_to_nwbfile(recording=recording, nwbfile=nwbfile, metadata=metadata)

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: Optional[DeepDict] = None,
        stub_test: bool = False,
        write_ecephys_metadata: bool = False,
        write_as: Literal["units", "processing"] = "units",
        units_name: str = "units",
        units_description: str = "Autogenerated by neuroconv.",
        unit_electrode_indices: Optional[list[list[int]]] = None,
    ):
        """
        Primary function for converting the data in a SortingExtractor to NWB format.

        Parameters
        ----------
        nwbfile : NWBFile
            Fill the relevant fields within the NWBFile object.
        metadata : DeepDict
            Information for constructing the NWB file (optional) and units table descriptions.
            Should be of the format::

                metadata["Ecephys"]["UnitProperties"] = dict(name=my_name, description=my_description)
        stub_test : bool, default: False
            If True, will truncate the data to run the conversion faster and take up less memory.
        write_ecephys_metadata : bool, default: False
            Write electrode information contained in the metadata.
        write_as : {'units', 'processing'}
            How to save the units table in the nwb file. Options:
            - 'units' will save it to the official NWBFile.Units position; recommended only for the final form of the data.
            - 'processing' will save it to the processing module to serve as a historical provenance for the official table.
        units_name : str, default: 'units'
            The name of the units table. If write_as=='units', then units_name must also be 'units'.
        units_description : str, default: 'Autogenerated by neuroconv.'
        unit_electrode_indices : list of lists of int, optional
            A list of lists of integers indicating the indices of the electrodes that each unit is associated with.
            The length of the list must match the number of units in the sorting extractor.
        """
        from ...tools.spikeinterface import add_sorting_to_nwbfile

        if metadata is None:
            metadata = self.get_metadata()

        metadata_copy = deepcopy(metadata)
        if write_ecephys_metadata:
            self.add_channel_metadata_to_nwb(nwbfile=nwbfile, metadata=metadata_copy)

        if stub_test:
            sorting_extractor = self.subset_sorting()
        else:
            sorting_extractor = self.sorting_extractor

        property_descriptions = dict()
        for metadata_column in metadata_copy["Ecephys"].get("UnitProperties", []):
            property_descriptions.update({metadata_column["name"]: metadata_column["description"]})
            for unit_id in sorting_extractor.get_unit_ids():
                # Special condition for wrapping electrode group pointers to actual object ids rather than string names
                if metadata_column["name"] == "electrode_group" and nwbfile.electrode_groups:
                    value = nwbfile.electrode_groups[
                        self.sorting_extractor.get_unit_property(unit_id=unit_id, property_name="electrode_group")
                    ]
                    sorting_extractor.set_unit_property(
                        unit_id=unit_id,
                        property_name=metadata_column["name"],
                        value=value,
                    )

        add_sorting_to_nwbfile(
            sorting_extractor,
            nwbfile=nwbfile,
            property_descriptions=property_descriptions,
            write_as=write_as,
            units_name=units_name,
            units_description=units_description,
            unit_electrode_indices=unit_electrode_indices,
        )
