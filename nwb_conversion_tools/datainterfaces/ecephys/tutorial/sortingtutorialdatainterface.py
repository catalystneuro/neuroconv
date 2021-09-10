"""Authors: Cody Baker and Ben Dichter."""
import spikeextractors as se

from ..basesortingextractorinterface import BaseSortingExtractorInterface


class TutorialSortingExtractor(se.NumpySortingExtractor):
    """Tutorial extractor for the toy data."""

    def __init__(self, duration: float = 10.0, K: int = 4, sampling_frequency: float = 30000.0):
        """
        Create tutorial recording extractor.

        Parameters
        ----------
        duration: float, optional
            Duration in seconds. Default 10 s.
        K: int, optional
            Number of spiking units. Default is 10.
        sampling_frequency: float, optional
            Sampling frequency. Default is 30000 Hz.
        """
        sorting = se.example_datasets.toy_example(duration=duration, K=K, sampling_frequency=sampling_frequency)[1]
        super().__init__()
        self.load_from_extractor(sorting=sorting)


class SortingTutorialInterface(BaseSortingExtractorInterface):
    """Sorting data interface for demonstrating NWB Conversion Tools usage in tutorials."""

    SX = TutorialSortingExtractor

    def __init__(self, duration: float = 10.0, num_units: int = 10, sampling_frequency: float = 30000.0):
        """
        Initialize the internal properties of the recording interface.

        Parameters
        ----------
        duration: float, optional
            Duration in seconds. Default 10 s.
        num_units: int, optional
            Number of spiking units. Default is 10.
        sampling_frequency: float, optional
            Sampling frequency. Default is 30000 Hz.
        """
        super().__init__(
            duration=duration,
            K=num_units,  # You can handle spepcific argument renaming at this step of initializaiton
            sampling_frequency=sampling_frequency,
        )

        # Set data for custom columns of the Units table
        for unit_id in self.sorting_extractor.get_unit_ids():
            self.sorting_extractor.set_unit_property(
                unit_id=unit_id, property_name="custom_unit_column", value="A custom value"
            )

    def get_metadata(self):
        # Set all automatically constructed metadata for the interface at this step
        # The user can always manually override this prior to running the conversion
        metadata = dict(
            Ecephys=dict(
                UnitProperties=[
                    dict(
                        name="custom_unit_column",
                        description="Custom column in the spiking unit table for the NWB Conversion Tools tutorial.",
                    )
                ]
            )
        )
        return metadata
