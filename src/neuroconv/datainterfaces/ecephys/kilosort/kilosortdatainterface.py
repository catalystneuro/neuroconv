from pydantic import DirectoryPath

from ..basesortingextractorinterface import BaseSortingExtractorInterface


class KiloSortSortingInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting a KiloSortingExtractor from spikeinterface."""

    display_name = "KiloSort Sorting"
    associated_suffixes = (".npy",)
    info = "Interface for KiloSort sorting data."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["folder_path"][
            "description"
        ] = "Path to the output Phy folder (containing the params.py)"
        return source_schema

    def __init__(
        self,
        folder_path: DirectoryPath,
        keep_good_only: bool = False,
        verbose: bool = False,
    ):
        """
        Load and prepare sorting data for kilosort

        Parameters
        ----------
        folder_path: str or Path
            Path to the output Phy folder (containing the params.py)
        keep_good_only: bool, default: False
            If True, only Kilosort-labeled 'good' units are returned
        verbose: bool, default: True
        """
        super().__init__(folder_path=folder_path, keep_good_only=keep_good_only, verbose=verbose)

    def get_metadata(self):
        metadata = super().get_metadata()
        # See Kilosort save_to_phy() docstring for more info on these fields: https://github.com/MouseLand/Kilosort/blob/main/kilosort/io.py
        # Or see phy documentation: https://github.com/cortex-lab/phy/blob/master/phy/apps/base.py
        metadata["Ecephys"]["UnitProperties"] = [
            dict(name="n_spikes", description="Number of spikes recorded from each unit."),
            dict(name="fr", description="Average firing rate of each unit."),
            dict(name="depth", description="Estimated depth of each unit in micrometers."),
            dict(name="Amplitude", description="Per-template amplitudes, computed as the L2 norm of the template."),
            dict(
                name="ContamPct",
                description="Contamination rate for each template, computed as fraction of refractory period violations relative to expectation based on a Poisson process.",
            ),
            dict(
                name="KSLabel",
                description="Label indicating whether each template is 'mua' (multi-unit activity) or 'good' (refractory).",
            ),
            dict(name="original_cluster_id", description="Original cluster ID assigned by Kilosort."),
            dict(
                name="amp",
                description="For every template, the maximum amplitude of the template waveforms across all channels.",
            ),
            dict(name="ch", description="The channel label of the best channel, as defined by the user."),
            dict(name="sh", description="The shank label of the best channel."),
        ]
        return metadata
