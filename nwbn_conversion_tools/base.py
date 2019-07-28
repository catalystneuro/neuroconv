from datetime import datetime
from dateutil.tz import tzlocal

from pynwb import NWBFile, NWBHDF5IO


nwbfile = NWBFile('my first synthetic recording', 'EXAMPLE_ID', datetime.now(tzlocal()),
                  experimenter='Dr. Bilbo Baggins',
                  lab='Bag End Laboratory',
                  institution='University of Middle Earth at the Shire',
                  experiment_description=('I went on an adventure with thirteen '
                                          'dwarves to reclaim vast treasures.'),
                  session_id='LONELYMTN')


class Convert2NWB:

    def __init__(self, nwbfile):
        """

        Parameters
        ----------
        nwbfile: pynwb.NWBFile
        """
        self.nwbfile = nwbfile

    def save(self, to_path):
        """

        Parameters
        ----------
        to_path: str
        """

        with NWBHDF5IO(to_path, 'w') as io:
            io.write(self.nwbfile)
