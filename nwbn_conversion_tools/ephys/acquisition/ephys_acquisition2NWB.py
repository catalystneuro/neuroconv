from nwbn_conversion_tools.base import Convert2NWB
import numpy as np


class EphysAcquisition2NWB(Convert2NWB):

    def __init__(self, nwbfile):
        super(EphysAcquisition2NWB).__init__(nwbfile)
