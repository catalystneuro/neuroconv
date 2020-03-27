```python
from nwbn_conversion_tools.ecephys.spikeglx import Spikeglx2NWB
import yaml

# Metadata
metafile = 'metafile.yml'
with open(metafile, 'r') as f:
    metadata = yaml.safe_load(f)

# Paths to source data
source_paths = dict()
source_paths['npx_file'] = {
    'type': 'file',
    'path': 'PATH_TO_FILE/filename.imec0.ap.bin'
}

converter = Spikeglx2NWB(nwbfile=None, metadata=metadata, source_paths=source_paths)

# To visualize NWB contents:
print(converter.nwbfile)

# To add Acquisition:
converter.run_conversion()

# Run spike sorting and store results on NWB:
converter.run_spike_sorting()

# To save content to NWB file:
converter.save(to_path='output.nwb')
```
