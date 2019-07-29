from nwbn_conversion_tools.base import Convert2NWB


class Acquisition2NWB(Convert2NWB):

    def __init__(self, nwbfile):
        super(Acquisition2NWB).__init__(nwbfile)
