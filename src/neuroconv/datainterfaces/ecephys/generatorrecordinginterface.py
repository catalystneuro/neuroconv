from datetime import datetime

from .baserecordingextractorinterface import BaseRecordingExtractorInterface

from ...utils.dict import dict_deep_update


class GeneratorRecordingInterface(BaseRecordingExtractorInterface):
    """An interface for testing purposes."""

    def __init__(
        self,
        num_channels=4,
        sampling_frequency=30_000.0,
        durations=[1.0],
        seed=0,
        verbose=True,
        es_key: str = "ElectricalSeries",
    ):
        from spikeinterface.core.generate import generate_recording

        # TODO: Use the true generator recording once spikeinterface is updated to 0.98
        self.recording_extractor = generate_recording(
            num_channels=num_channels, sampling_frequency=sampling_frequency, durations=durations, seed=seed
        )
        self.subset_channels = None
        self.verbose = verbose
        self.es_key = es_key

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
        session_start_time = datetime.now().astimezone()
        metadata = dict_deep_update(metadata, dict(NWBFile=dict(session_start_time=session_start_time)))
        return metadata
