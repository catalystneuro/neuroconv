from neuroconv import ConverterPipe
from neuroconv.datainterfaces.ecephys.baserecordingextractorinterface import (
    BaseRecordingExtractorInterface,
)
from neuroconv.datainterfaces.ecephys.basesortingextractorinterface import (
    BaseSortingExtractorInterface,
)


class SortedRecordingConverter(ConverterPipe):
    """
    A converter for linking spike sorting results with their corresponding recording electrodes.

    This converter ensures proper linkage between sorted units and recording channels by requiring
    an explicit mapping between unit IDs and channel IDs. This is essential for maintaining the
    spatial and technical context of sorted units in the resulting NWB file, enabling downstream
    analyses that rely on electrode information such as spatial clustering, quality control, and
    current source density analysis.

    The converter validates that:
    - All unit IDs from the sorting interface have corresponding channel mappings
    - All referenced channel IDs exist in the recording interface
    - Proper electrode references are maintained in the NWB Units table
    """

    keywords = (
        "electrophysiology",
        "spike sorting",
    )
    display_name = "SortedRecordingConverter"
    associated_suffixes = ("electrophysiology", "spike sorting")
    info = "A converter for handling simultaneous recording and sorting data linking metadata properly."

    def __init__(
        self,
        recording_interface: BaseRecordingExtractorInterface,
        sorting_interface: BaseSortingExtractorInterface,
        unit_ids_to_channel_ids: dict[str | int, list[str | int]],
    ):
        """
        Parameters
        ----------
        recording_interface : BaseRecordingExtractorInterface
            The interface handling the raw recording data. This typically represents data
            from a single recording stream (e.g., SpikeGLXRecordingInterface, IntanRecordingInterface).
        sorting_interface : BaseSortingExtractorInterface
            The interface handling the sorted units data. This typically represents the
            output of a spike sorting algorithm (e.g., KiloSortSortingInterface, MountainSortSortingInterface).
        unit_ids_to_channel_ids : dict[str | int, list[str | int]]
            A mapping from unit IDs to their associated channel IDs. Each unit ID (key)
            maps to a list of channel IDs (values) that were used to detect that unit.
            This mapping ensures proper linkage between sorted units and recording electrodes.
        """

        self.recording_interface = recording_interface
        self.sorting_interface = sorting_interface
        self.unit_ids_to_channel_ids = unit_ids_to_channel_ids

        self.channel_ids = self.recording_interface.channel_ids
        self.unit_ids = self.sorting_interface.units_ids

        # Convert channel_ids to set for comparison (use list to avoid numpy scalar representation issues)
        available_channels = set(self.channel_ids.tolist())

        # Check that all referenced channels exist in recording
        for unit_id, channel_ids in unit_ids_to_channel_ids.items():
            unknown_channels = set(channel_ids) - available_channels
            if unknown_channels:
                raise ValueError(
                    f"Inexistent channel IDs {unknown_channels} referenced in mapping for unit {unit_id} "
                    f"not found in recording. Available channels are {available_channels}"
                )

        # Check that all units have a channel mapping
        available_units = set(self.unit_ids.tolist())  # Use tolist() to avoid numpy scalar representation issues
        mapped_units = set(unit_ids_to_channel_ids.keys())
        unmapped_units = available_units - mapped_units
        if unmapped_units:
            raise ValueError(f"Units {unmapped_units} from sorting interface have no channel mapping")

        data_interfaces = [recording_interface, sorting_interface]
        super().__init__(data_interfaces=data_interfaces)

    def add_to_nwbfile(self, nwbfile, metadata, conversion_options: dict | None = None):

        conversion_options = conversion_options or dict()
        conversion_options_recording = conversion_options.get("recording", dict())

        self.recording_interface.add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata,
            **conversion_options_recording,
        )

        from ...tools.spikeinterface.spikeinterface import (
            _get_electrode_table_indices_for_recording,
        )

        # This returns the indices in the electrode table that corresponds to the channel ids of the recording
        electrode_table_indices = _get_electrode_table_indices_for_recording(
            recording=self.recording_interface.recording_extractor,
            nwbfile=nwbfile,
        )

        # Map ids in the recording to the indices in the electrode table
        channel_id_to_electrode_table_index = {
            channel_id: electrode_table_indices[channel_index]
            for channel_index, channel_id in enumerate(self.channel_ids)
        }

        # Create a list of lists with the indices of the electrodes in the electrode table for each unit
        unit_electrode_indices = []
        for unit_id in self.unit_ids:
            unit_channel_ids = self.unit_ids_to_channel_ids[unit_id]
            unit_indices = [channel_id_to_electrode_table_index[channel_id] for channel_id in unit_channel_ids]
            unit_electrode_indices.append(unit_indices)

        conversion_options_sorting = conversion_options.get("sorting", dict())
        self.sorting_interface.add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata,
            unit_electrode_indices=unit_electrode_indices,
            **conversion_options_sorting,
        )
