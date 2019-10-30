from nwbn_conversion_tools.ephys.acquisition.ephys_acquisition2NWB import EphysAcquisition2NWB
import spikeextractors as se


class Spikeglx2NWB(EphysAcquisition2NWB):
    def __init__(self, nwbfile, metadata, npx_file, x_pitch=None, y_pitch=None):
        """
        Reads data from SpikeGLX file, using SpikeGLXRecordingExtractor class
        from SpikeExtractors: https://github.com/SpikeInterface/spikeextractors

        Parameters
        ----------
        nwbfile: pynwb.NWBFile
        metadata: dict
        npx_file: str
            Full path to SpikeGLX file to be read.
        x_pitch : float
        y_pitch : float
        """
        super(Spikeglx2NWB, self).__init__(nwbfile=nwbfile, metadata=metadata)

        self.RX = se.SpikeGLXRecordingExtractor(npx_file, x_pitch=None, y_pitch=None)
