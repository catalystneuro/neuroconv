from ..ecephys import SpikeExtractor2NWBConverter
import spikeextractors as se

import pynwb

from pathlib import Path


class Spikeglx2NWB(SpikeExtractor2NWBConverter):
    def __init__(self, nwbfile, metadata, source_paths, x_pitch=None, y_pitch=None):
        """
        Reads data from SpikeGLX file, using SpikeGLXRecordingExtractor class
        from SpikeExtractors: https://github.com/SpikeInterface/spikeextractors

        Parameters
        ----------
        nwbfile: pynwb.NWBFile
        metadata: dict
        source_paths: {'npx_file': {'type': 'file', 'path': PATH_TO_FILE}}
            Dictionary with path to SpikeGLX file to be read.
        x_pitch : float
        y_pitch : float
        """
        super().__init__(nwbfile=nwbfile, metadata=metadata, source_paths=source_paths)
        # Read SpikeGLX data to a RecordingExtractor
        npx_file = Path(self.source_paths['npx_file']['path'])
        self.RX = se.SpikeGLXRecordingExtractor(npx_file, x_pitch=x_pitch, y_pitch=y_pitch)
