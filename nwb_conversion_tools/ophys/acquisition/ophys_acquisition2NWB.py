from nwb_conversion_tools.base import Convert2NWB


class OphysAcquisition2NWB(Convert2NWB):

    def __init__(self, nwbfile):
        super(OphysAcquisition2NWB).__init__(nwbfile)
