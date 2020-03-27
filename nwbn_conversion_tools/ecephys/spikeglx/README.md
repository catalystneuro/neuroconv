```python
from nwbn_conversion_tools.ecephys.spikeglx import Spikeglx2NWB
import yaml

metafile = 'metafile.yml'
with open(metafile, 'r') as f:
    metadata = yaml.safe_load(f)
npx_file = 'G4_190620_keicontrasttrack_10secBaseline1_g0_t0.imec0.ap.bin'

extractor = Spikeglx2NWB(nwbfile=None, metadata=metadata, npx_file=npx_file)

# To visualize NWB contents:
print(extractor.nwbfile)

# To add Acquisition:
extractor.add_acquisition(es_name='ElectricalSeries', metadata=metadata['Ephys'])

# Run spike sorting and store results on NWB:
extractor.run_spike_sorting()

# To save content to NWB file:
extractor.save(to_path='output.nwb')
```
