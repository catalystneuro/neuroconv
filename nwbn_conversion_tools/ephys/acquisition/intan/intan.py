from nwbn_conversion_tools.ephys.acquisition.ephys_acquisition2NWB import EphysAcquisition2NWB
from nwbn_conversion_tools.ephys.acquisition.intan.load_intan import load_intan, read_header


class Intan2NWB(EphysAcquisition2NWB):
    def __init__(self, nwbfile, metadata):
        """
        Reads data from Intantech .rhd files, using an adapted version of the
        rhd reader scripts: http://intantech.com/downloads.html?tabSelect=Software

        Parameters
        ----------
        nwbfile: pynwb.NWBFile
        metadata: dict
        """
        super(Intan2NWB, self).__init__(nwbfile=nwbfile, metadata=metadata)

        
