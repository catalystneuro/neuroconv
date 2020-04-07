# CELLMax

```python
from nwbn_conversion_tools.ophys.processing.CELLMax import CellMax2NWB
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

CellMax2NWB(nwbfile, from_path='/path/to/emAnalysis.mat').save('out.nwb')
```
