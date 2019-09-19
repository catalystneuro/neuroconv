from nwbn_conversion_tools.base import Convert2NWB
import numpy as np


class EphysProcessing2NWB(Convert2NWB):

    def __init__(self, nwbfile):
        super(EphysProcessing2NWB, self).__init__(nwbfile)
