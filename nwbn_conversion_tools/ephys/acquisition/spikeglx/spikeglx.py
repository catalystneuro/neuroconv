from nwbn_conversion_tools.ephys.acquisition.ephys_acquisition2NWB import EphysAcquisition2NWB
import spikeextractors as se


class Spikeglx2NWB(EphysAcquisition2NWB):
    def __init__(self, npx_file, x_pitch=None, y_pitch=None):
        #super().__init__(nwbfile=[])

        # Arguments for SpikeGLXRecordingExtractor
        npx_file = 'G4_190620_keicontrasttrack_10secBaseline1_g0_t0.imec0.ap.bin'
        x_pitch, y_pitch = None, None

        # Reads data from SpikeGLX file
        self.RX = se.SpikeGLXRecordingExtractor(npx_file, x_pitch=None, y_pitch=None)
