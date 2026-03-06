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

    def get_metadata(self):
        metadata = super().get_metadata()
        # See MdaSortingExtractor documentation:
        # https://github.com/SpikeInterface/spikeinterface/blob/2c6e800a820aa0618007018b94a047f71f82ace5/src/spikeinterface/extractors/mdaextractors.py#L180
        # https://mountainsort.readthedocs.io/en/latest/first_sort.html#format-of-the-firings-mda
        metadata["Ecephys"]["UnitProperties"] = [
            dict(
                name="max_channel",
                description=(
                    "1-indexed primary channel for the unit. The channel identification number "
                    "is relative and may not correspond to the ElectricalSeries also in the file. "
                    "In other words, if you only sort channels 61-64, the max_channel will be 1-4."
                ),
            ),
        ]
        return metadata
