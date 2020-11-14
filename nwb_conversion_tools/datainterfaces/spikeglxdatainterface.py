"""Authors: Cody Baker and Ben Dichter."""
from pathlib import Path
from spikeextractors import SpikeGLXRecordingExtractor

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface


class SpikeGLXRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting the high-pass (ap) SpikeGLX format."""

    RX = SpikeGLXRecordingExtractor

    def get_metadata(self):
        """Auto-populate as much metadata as possible from the high-pass (ap) SpikeGLX format."""
        file_path = Path(self.input_args['file_path'])
        session_id = file_path.parent.stem

        n_shanks = int(self.recording_extractor._meta['snsShankMap'][1])
        if n_shanks > 1:
            raise NotImplementedError("SpikeGLX metadata for more than a single shank is not yet supported.")

        channels = self.recording_extractor.get_channel_ids()
        shank_electrode_number = channels
        shank_group_name = ["Shank1" for x in channels]

        re_metadata = dict(
            Ecephys=dict(
                Device=[
                    dict(
                        description=f"More details for the high-pass (ap) data found in {session_id}.ap.meta!"
                    )
                ],
                ElectrodeGroup=[
                    dict(
                        name='Shank1',
                        description="Shank1 electrodes."
                    )
                    for n in range(n_shanks)
                ],
                Electrodes=[
                    dict(
                        name='shank_electrode_number',
                        description="0-indexed channel within a shank.",
                        data=shank_electrode_number
                    ),
                    dict(
                        name='group_name',
                        description="The name of the ElectrodeGroup this electrode is a part of.",
                        data=shank_group_name
                    )
                ],
                ElectricalSeries=dict(
                    name='ElectricalSeries',
                    description="Raw acquisition traces for the high-pass (ap) SpikeGLX data."
                )
            )
        )
        return re_metadata
