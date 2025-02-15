from pydantic import FilePath

from ..basesortingextractorinterface import BaseSortingExtractorInterface


class MdaSortingInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting a firings.mda file from MountainSort v4 or earlier.

    https://mountainsort.readthedocs.io/en/latest/first_sort.html#format-of-the-firings-mda
    """

    display_name = "MountainSort Sorting"
    associated_suffixes = (".mda",)
    info = "Interface for MountainSort sorting data from firings.mda."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to the firings.mda file"
        return source_schema

    def __init__(
        self,
        file_path: FilePath,
        sampling_frequency: int,
        verbose: bool = True,
    ):
        """
        Load and prepare sorting data for MountainSort

        Parameters
        ----------
        file_path: str or Path
            Path to the firings.mda file
        sampling_frequency : int
            The sampling frequency in Hz.
        verbose: bool, default: True
        """
        super().__init__(file_path=file_path, sampling_frequency=sampling_frequency, verbose=verbose)

        # TODO: append channel indices (1-index) from the firings.mda file if available
        # This is a draft implementation

        # NOTE: These indices are based on the order of channels in the input data to the sorter
        # If the user sorts a different timeseries array than what is stored as raw data in the NWB file,
        # then there will be a mismatch in the electrode IDs / it is not possible to know which channel
        # in the raw data do the channel indices from the firings.mda correspond to...

        # TODO: Collect the max channel values for each spike event for each unit across segments
        # Should this be done in spikeinterface or neuroconv?
        from collections import defaultdict

        label_to_channel = defaultdict(list)
        for segment in self.sorting_extractor._sorting_segments:
            for spike_event_index in range(len(segments._labels)):
                label = segments._labels[spike_event_index]
                max_channel = segments._max_channels[spike_event_index]
                label_to_channel[label].append(max_channel)

        # Check that all units have the same max channel value
        for label in label_to_channel.keys():
            channels = label_to_channel[label]
            assert all(channels == channels[0]), f"Unit {label} has spike events where the max channel values differ"

        # TODO: ensure NWB file has electrodes in the electrodes table to map to
        self.set_property(key="electrodes", values=self.sorting_extractor.get_segment)
