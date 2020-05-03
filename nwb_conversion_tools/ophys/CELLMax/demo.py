from nwb_conversion_tools.ophys.CELLMax import CellMax2NWB
from pynwb import NWBFile
from datetime import datetime
from dateutil.tz import tzlocal


nwbfile = NWBFile('my first synthetic recording', 'EXAMPLE_ID',
                  session_start_time=datetime.now(tzlocal()),
                  experimenter='Dr. Bilbo Baggins',
                  lab='Bag End Laboratory',
                  institution='University of Middle Earth at the Shire',
                  experiment_description=('I went on an adventure with thirteen '
                                          'dwarves to reclaim vast treasures.'),
                  session_id='LONELYMTN')

from_path = '/Users/bendichter/dev/calciumImagingAnalysis/data/2014_04_01_p203_m19_check01_raw/' \
            '2014_04_01_p203_m19_check01_emAnalysis.mat'

to_path = '/Users/bendichter/dev/calciumImagingAnalysis/data/2014_04_01_p203_m19_check01_raw/out.nwb'

CellMax2NWB(from_path=from_path).save(to_path)
