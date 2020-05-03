# CELLMax

Convert CELLMaz data to NWB:

```python
from nwb_conversion_tools.ophys.CELLMax import CellMax2NWB
from pynwb import NWBFile
from datetime import datetime
from dateutil.tz import tzlocal

CellMax2NWB(from_path='/path/to/emAnalysis.mat').save('out.nwb')
```
