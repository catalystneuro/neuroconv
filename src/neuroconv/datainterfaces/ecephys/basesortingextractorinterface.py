import warnings
from copy import deepcopy
from functools import partial
from typing import Literal

import numpy as np
from pynwb import NWBFile
from pynwb.device import Device
from pynwb.ecephys import ElectrodeGroup

from .baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..._temporal_alignment import _TemporalAlignment, _TimeBearingObject
from ...baseextractorinterface import BaseExtractorInterface
from ...utils import DeepDict, get_base_schema, get_schema_from_hdmf_class

_NO_SORTING_START_MESSAGE = (
    "A sorting has no start to place: its first spike is not when its recording began. Use `shift_times` to move " "it."
)


class _SortingTimeBearingObject(_TimeBearingObject):
    """One segment of a sorting: every unit's spikes in that segment, flattened in unit order.

    A shift or a remap acts on each spike, so both work. What would need the flat vector to mean more is
    refused: replacement times cannot say which spike belongs to which unit, and the first spike is not where
    the segment starts.
    """

    def set_times(self, times) -> None:
        raise NotImplementedError(
            "A sorting's times are its units' spikes flattened in unit order, so `set_times` cannot say which "
            "spike is which. Use `shift_times` or `remap_times`."
        )

    def move_start_to(self, starting_time: float) -> None:
        raise NotImplementedError(_NO_SORTING_START_MESSAGE)

    def _get_start_time(self) -> float:
        raise NotImplementedError(_NO_SORTING_START_MESSAGE)


class BaseSortingExtractorInterface(BaseExtractorInterface):
    """Primary class for all SortingExtractor interfaces."""

    keywords = ("extracellular electrophysiology", "spike sorting")

    def __init__(self, verbose: bool = False, **source_data):

        super().__init__(**source_data)
        self.sorting_extractor = self._extractor_instance
        self.verbose = verbose
        self._number_of_segments = self.sorting_extractor.get_num_segments()
        self._register_segments()

    def _register_segments(self) -> None:
        """Name every segment as a time-bearing object, keyed ``{metadata_key}_{segment_index}`` as for recordings.

        The keys are for alignment only. The segments are joined in one units table, so there is no segment-level
        metadata for them to address. Registering reads nothing.
        """
        self._alignment = _TemporalAlignment()
        for segment_index in range(self._number_of_segments):
            self._alignment._register(
                key=f"{self.metadata_key}_{segment_index}",
                get_native_times=partial(self._get_segment_native_spike_times, segment_index=segment_index),
                time_bearing_object_class=_SortingTimeBearingObject,
            )

    @property
    def temporal_alignment(self) -> _TemporalAlignment:
        return self._alignment

    # The sorting is read on every call because an interface replaces it when it renames its units
    def _get_segment_native_spike_times(self, segment_index: int) -> np.ndarray:
        spike_trains = [
            self.sorting_extractor.get_unit_spike_train(unit_id=unit_id, segment_index=segment_index, return_times=True)
            for unit_id in self.sorting_extractor.unit_ids
        ]
        return np.concatenate(spike_trains) if spike_trains else np.empty(0)

    def _get_aligned_unit_spike_times(self) -> dict:
        """Each unit's spike times as they will be written, keyed by unit id, with the segments joined in order."""
        unit_ids = self.sorting_extractor.unit_ids
        segments_by_unit = {unit_id: [] for unit_id in unit_ids}
        for segment_index in range(self._number_of_segments):
            aligned_spike_times = self._alignment[f"{self.metadata_key}_{segment_index}"].get_times()
            spike_counts = [
                self.sorting_extractor.get_unit_spike_train(unit_id=unit_id, segment_index=segment_index).size
                for unit_id in unit_ids
            ]
            unit_segments = np.split(aligned_spike_times, np.cumsum(spike_counts)[:-1])
            for unit_id, segment_spike_times in zip(unit_ids, unit_segments):
                segments_by_unit[unit_id].append(segment_spike_times)
        return {unit_id: np.concatenate(segments) for unit_id, segments in segments_by_unit.items()}

    def get_metadata_schema(self) -> dict:
        """
        Compile the metadata schema.

        A sorting interface registers no series of its own: what it reads from ``metadata["Ecephys"]`` is
        the description of the columns it writes, on the units table and, when a recording is attached, on
        the electrode table. Both are lists. It also declares ``ElectrodeGroups``, because a sorting
        interface that was given a recording carries the groups that recording describes
        (``NeuroScopeSortingInterface`` reads them from the session's XML), and they reach validation in
        the dict format like any other.

        Metadata in the old list-based format is validated against
        ``_get_metadata_schema_for_old_list_format``, and both go when that format does.
        """
        from ...basedatainterface import BaseDataInterface

        metadata_schema = BaseDataInterface.get_metadata_schema(self)
        metadata_schema["properties"]["Ecephys"] = get_base_schema(tag="Ecephys")
        metadata_schema["properties"]["Ecephys"]["required"] = []
        metadata_schema["properties"]["Ecephys"]["properties"] = dict(
            ElectrodeGroups=dict(
                type="object",
                additionalProperties={"$ref": "#/properties/Ecephys/definitions/ElectrodeGroupEntry"},
            ),
            Electrodes=dict(
                type="array",
                minItems=0,
                renderForm=False,
                items={"$ref": "#/properties/Ecephys/definitions/ColumnDescription"},
            ),
            UnitProperties=dict(
                type="array",
                minItems=0,
                renderForm=False,
                items={"$ref": "#/properties/Ecephys/definitions/ColumnDescription"},
            ),
            UnitsTables=dict(
                type="object",
                additionalProperties={"$ref": "#/properties/Ecephys/definitions/UnitsTableEntry"},
            ),
            Sortings=dict(
                type="object",
                additionalProperties={"$ref": "#/properties/Ecephys/definitions/SortingEntry"},
            ),
        )
        metadata_schema["properties"]["Ecephys"]["definitions"] = dict(
            UnitsTableEntry=dict(
                type="object",
                additionalProperties=False,
                properties=dict(
                    name=dict(type="string", pattern="^[^/]*$"),
                    description=dict(type="string"),
                ),
            ),
            SortingEntry=dict(
                type="object",
                additionalProperties=False,
                properties=dict(
                    sorting_name=dict(
                        type="string",
                        description=(
                            "Name identifying one sorting output: the set of units produced by a particular "
                            "spike-sorting run or curation step. All units from that output share this value. "
                            "Assign distinct names to different outputs written to the same units table."
                        ),
                    ),
                    name=dict(
                        type="string",
                        pattern="^[^/]*$",
                        description="Name of a units table of this sorting's own, written in processing.",
                    ),
                    description=dict(
                        type="string",
                        description="Description of the units table of this sorting's own, which needs a 'name'.",
                    ),
                    units_table_metadata_key=dict(
                        type="string",
                        description="Key of the units table this sorting writes into in metadata['Ecephys']['UnitsTables'].",
                    ),
                ),
            ),
            ElectrodeGroupEntry=dict(
                type="object",
                additionalProperties=True,
                properties=dict(
                    name=dict(type="string", pattern="^[^/]*$"),
                    description=dict(type="string"),
                    location=dict(type="string"),
                    device_metadata_key=dict(
                        type="string",
                        description="Key of this group's device in metadata['Devices'].",
                    ),
                ),
            ),
            ColumnDescription=dict(
                type="object",
                additionalProperties=False,
                required=["name"],
                properties=dict(
                    name=dict(type="string", description="name of this column"),
                    description=dict(type="string", description="description of this column"),
                ),
            ),
        )
        return metadata_schema

    def _get_metadata_schema_for_old_list_format(self) -> dict:
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
        warnings.warn(
            "`register_recording` is deprecated and will be removed in v0.13.0. "
            "Align the sorting with `interface.temporal_alignment` instead.",
            FutureWarning,
            stacklevel=2,
        )
        self.sorting_extractor.register_recording(recording=recording_interface.recording_extractor)

    def get_original_timestamps(self) -> np.ndarray:
        raise NotImplementedError(
            "Unable to fetch original timestamps for a SortingInterface since it relies upon an attached recording."
        )

    def get_timestamps(self) -> np.ndarray | list[np.ndarray]:
        warnings.warn(
            "`get_timestamps` is deprecated and will be removed in v0.13.0. "
            "Use `interface.temporal_alignment[key].get_times()` for a segment's spike times instead.",
            FutureWarning,
            stacklevel=2,
        )
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
        warnings.warn(
            "`set_aligned_timestamps` is deprecated and will be removed in v0.13.0. "
            "Use `interface.temporal_alignment.remap_times(local_sync_times=..., reference_sync_times=...)` "
            "instead, from the recording's timestamps to the aligned ones.",
            FutureWarning,
            stacklevel=2,
        )
        if not self.sorting_extractor.has_recording():
            raise NotImplementedError(
                "In order to align timestamps for a SortingInterface, it must have a recording "
                "object attached to it! Please attach one by calling `.register_recording(recording_interface=...)`."
            )
        assert (
            self._number_of_segments == 1
        ), "This recording has multiple segments; please use 'set_aligned_segment_timestamps' instead."

        if self._number_of_segments == 1:
            self.sorting_extractor._recording.set_times(times=aligned_timestamps)
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
        warnings.warn(
            "`set_aligned_segment_timestamps` is deprecated and will be removed in v0.13.0. "
            "Use `interface.temporal_alignment[key].remap_times(local_sync_times=..., reference_sync_times=...)` "
            "on each segment instead, from the recording's timestamps to the aligned ones.",
            FutureWarning,
            stacklevel=2,
        )
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
            )

    def set_aligned_starting_time(self, aligned_starting_time: float):
        warnings.warn(
            "`set_aligned_starting_time` is deprecated and will be removed in v0.13.0. "
            "Use `interface.temporal_alignment.shift_times(delta)` instead.",
            FutureWarning,
            stacklevel=2,
        )
        if self.sorting_extractor.has_recording():
            # The recording is read and set directly, so a call warns once and not for every deprecated method it used
            recording = self.sorting_extractor._recording
            for segment_index in range(self._number_of_segments):
                segment_timestamps = recording.get_times(segment_index=segment_index)
                recording.set_times(times=segment_timestamps + aligned_starting_time, segment_index=segment_index)
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
        warnings.warn(
            "`set_aligned_segment_starting_times` is deprecated and will be removed in v0.13.0. "
            "Use `interface.temporal_alignment[key].shift_times(delta)` on each segment instead.",
            FutureWarning,
            stacklevel=2,
        )
        assert len(aligned_segment_starting_times) == self._number_of_segments, (
            f"The length of the starting_times ({len(aligned_segment_starting_times)}) does not match the number "
            f"of segments ({self._number_of_segments})!"
        )

        if self.sorting_extractor.has_recording():
            # The recording is read and set directly, so a call warns once and not for every deprecated method it used
            recording = self.sorting_extractor._recording
            for segment_index, aligned_segment_starting_time in enumerate(aligned_segment_starting_times):
                segment_timestamps = recording.get_times(segment_index=segment_index)
                recording.set_times(
                    times=segment_timestamps + aligned_segment_starting_time, segment_index=segment_index
                )
        else:
            for sorting_segment, aligned_segment_starting_time in zip(
                self.sorting_extractor._sorting_segments, aligned_segment_starting_times
            ):
                sorting_segment._t_start = aligned_segment_starting_time

    def align_by_interpolation(self, unaligned_timestamps: np.ndarray, aligned_timestamps: np.ndarray) -> None:
        warnings.warn(
            "`align_by_interpolation` is deprecated and will be removed in v0.13.0. "
            "Use `interface.temporal_alignment.remap_times(local_sync_times=..., reference_sync_times=...)` instead.",
            FutureWarning,
            stacklevel=2,
        )
        if not self.sorting_extractor.has_recording():
            raise NotImplementedError(
                "In order to align timestamps for a SortingInterface, it must have a recording "
                "object attached to it! Please attach one by calling `.register_recording(recording_interface=...)`."
            )
        assert (
            self._number_of_segments == 1
        ), "This recording has multiple segments; please use 'set_aligned_segment_timestamps' instead."

        # The recording is read and set directly, so a call warns once and not for every deprecated method it used
        recording = self.sorting_extractor._recording
        recording.set_times(times=np.interp(x=recording.get_times(), xp=unaligned_timestamps, fp=aligned_timestamps))

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

    def add_channel_metadata_to_nwb(self, nwbfile: NWBFile, metadata: DeepDict | None = None):
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
        metadata : DeepDict | None
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
        from ...tools.spikeinterface import add_recording_metadata_to_nwbfile

        if hasattr(self, "generate_recording_with_channel_metadata"):
            recording = self.generate_recording_with_channel_metadata()
            add_recording_metadata_to_nwbfile(recording=recording, nwbfile=nwbfile, metadata=metadata)

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: DeepDict | None = None,
        stub_test: bool = False,
        write_ecephys_metadata: bool = False,
        write_as: Literal["units", "processing"] | None = None,
        units_name: str | None = None,
        units_description: str | None = None,
        unit_electrode_indices: list[list[int]] | None = None,
        *,
        parent_container: Literal["units", "processing"] | None = None,
        waveform_data_dict: dict | None = None,
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
        parent_container : {'units', 'processing'}, optional
            Deprecated. A sorting whose entry in ``metadata["Ecephys"]["Sortings"]`` gives a ``name`` writes a table of
            its own in processing. Otherwise it writes ``nwbfile.units``, or the shared table its
            ``units_table_metadata_key`` names in ``metadata["Ecephys"]["UnitsTables"]``. Will be removed in v0.13.0.
        units_name : str, optional
            Deprecated. Set ``name`` in the sorting's entry in ``metadata["Ecephys"]["Sortings"]`` instead, which writes
            the sorting into a table of its own in processing. Will be removed in v0.13.0.
        units_description : str, optional
            Deprecated. Set ``description`` in the sorting's entry in ``metadata["Ecephys"]["Sortings"]`` for a table of
            its own, or in ``metadata["Ecephys"]["UnitsTables"]`` for ``nwbfile.units`` and for a shared table. Will be
            removed in v0.13.0.
        unit_electrode_indices : list of lists of int, optional
            A list of lists of integers indicating the indices of the electrodes that each unit is associated with.
            The length of the list must match the number of units in the sorting extractor.
        waveform_data_dict : dict, optional
            Dictionary containing waveform data and metadata. Keys:
                - "means": np.ndarray of shape (num_units, num_samples, num_channels)
                - "sds": np.ndarray of shape (num_units, num_samples, num_channels), optional
                - "sampling_rate": float, the sampling rate of the waveforms in Hz
                - "unit": str, the unit of measurement (default: "volts")
                - "time_before_peak_in_ms": float, the time from the start of each waveform to the spike peak, optional
        write_as : {'units', 'processing'}, optional
            Deprecated. A sorting whose entry in ``metadata["Ecephys"]["Sortings"]`` gives a ``name`` writes a table of
            its own in processing. Otherwise it writes ``nwbfile.units``, or the shared table its
            ``units_table_metadata_key`` names in ``metadata["Ecephys"]["UnitsTables"]``. Will be removed in v0.12.0.
        """
        from ...tools.spikeinterface.spikeinterface import _add_sorting_to_nwbfile

        if write_as is not None:
            warnings.warn(
                "The 'write_as' parameter of BaseSortingExtractorInterface.add_to_nwbfile() is deprecated and will "
                "be removed in v0.12.0. A sorting whose entry in metadata['Ecephys']['Sortings'] gives a 'name' "
                "writes a table of its own in processing. Otherwise it writes nwbfile.units, or the shared table its "
                "'units_table_metadata_key' names in metadata['Ecephys']['UnitsTables'].",
                FutureWarning,
                stacklevel=2,
            )
            parent_container = write_as

        if metadata is None:
            metadata = self.get_metadata()

        metadata_copy = deepcopy(metadata)
        if write_ecephys_metadata:
            self.add_channel_metadata_to_nwb(nwbfile=nwbfile, metadata=metadata_copy)

        unit_spike_times = self._get_aligned_unit_spike_times()
        if stub_test:
            sorting_extractor = self.subset_sorting()
            # The stub keeps each unit's first spikes, and aligned spike `i` is native spike `i` aligned
            unit_spike_times = {
                unit_id: spike_times[: sorting_extractor.get_unit_spike_train(unit_id=unit_id).size]
                for unit_id, spike_times in unit_spike_times.items()
            }
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

        _add_sorting_to_nwbfile(
            sorting=sorting_extractor,
            nwbfile=nwbfile,
            unit_ids=None,
            unit_spike_times=unit_spike_times,
            property_descriptions=property_descriptions,
            skip_properties=None,
            units_name=units_name,
            units_description=units_description,
            parent_container=parent_container,
            unit_electrode_indices=unit_electrode_indices,
            null_values_for_properties=None,
            waveform_data_dict=waveform_data_dict,
            metadata=metadata_copy,
            metadata_key=self.metadata_key,
        )

    def rename_unit_ids(self, unit_ids_map: dict):
        """
        Rename unit IDs using a mapping dictionary.

        Parameters
        ----------
        unit_ids_map : dict
            A dictionary mapping current unit IDs to new unit IDs.
            Format: {old_unit_id: new_unit_id, ...}

        Raises
        ------
        ValueError
            If any of the old unit IDs in the mapping do not exist in the sorting extractor.
        TypeError
            If unit_ids_map is not a dictionary.

        Examples
        --------
        >>> sorting_interface = MockSortingInterface()
        >>> print(sorting_interface.units_ids)  # ['0', '1', '2', '3']
        >>> sorting_interface.rename_unit_ids({'0': 'unit_a', '1': 'unit_b'})
        >>> print(sorting_interface.units_ids)  # ['unit_a', 'unit_b', '2', '3']
        """
        if not isinstance(unit_ids_map, dict):
            raise TypeError("unit_ids_map must be a dictionary")

        if not unit_ids_map:
            return

        current_unit_ids = list(self.sorting_extractor.get_unit_ids())

        # Validate that all old unit IDs exist
        missing_ids = [old_id for old_id in unit_ids_map.keys() if old_id not in current_unit_ids]
        if missing_ids:
            raise ValueError(
                f"Unit IDs {missing_ids} not found in sorting extractor. " f"Available unit IDs: {current_unit_ids}"
            )

        # Create the new unit IDs list, keeping non-mapped IDs unchanged
        new_unit_ids = [unit_ids_map.get(unit_id, unit_id) for unit_id in current_unit_ids]

        # Rename the units in the sorting extractor
        self.sorting_extractor = self.sorting_extractor.rename_units(new_unit_ids=new_unit_ids)
