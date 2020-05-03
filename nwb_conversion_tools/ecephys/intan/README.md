## Intan converter

Conversion of Intan Technologies electrophysiology data from `rhd` to `nwb`.
This converter is built on top of the publicly available [Python RHD file reader](http://intantech.com/downloads.html?tabSelect=Software).

Example of usage:
```python
from nwb_conversion_tools.ecephys import Intan2NWB
import yaml

# Metadata
metafile = 'metafile.yml'
with open(metafile, 'r') as f:
    metadata = yaml.safe_load(f)

# Source paths
source_paths = dict(
    dir_ecephys_rhd=dict(
        type='dir',
        path='PATH_TO_DIR'
    )
)

# Initialize converter
converter = Intan2NWB(metadata=metadata, source_paths=source_paths)

# Run conversion
converter.run_conversion()

# To visualize NWB contents:
print(converter.nwbfile)

# To save content to NWB file:
converter.save(to_path='output.nwb')
```
