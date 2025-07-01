"""
Generate minimal EDF+C file.
See also pyedflib and format specifications
https://github.com/holgern/pyedflib
https://www.edfplus.info/

Author: Julia Sprenger
"""

from pyedflib import highlevel
from pathlib import Path
import numpy as np

current_dir = Path(__file__).parent.absolute()

# write an edf file with 5 channels á 265 samples (1 second)
channel_names = ['ch1', 'ch2', 'ch3', 'ch4', 'ch5']
dimensions = ['mV', 'uV', 'pA', '', 'C']
transducer = ['unknown', 'A', 'B', '', 'Z']
prefilter = ['true', 'false', 'false', 'true', 'true']
signal_headers = highlevel.make_signal_headers(list_of_labels=channel_names, sample_rate=256)
digital_min, digital_max = signal_headers[0]['digital_min'], signal_headers[0]['digital_max']
signals = np.random.randint(digital_min, digital_max, size=(5, 256), dtype=np.int16)

for i in range(len(signal_headers)):
    signal_headers[i]['dimension'] = dimensions[i]
    signal_headers[i]['transducer'] = transducer[i]
    signal_headers[i]['prefilter'] = prefilter[i]
header = highlevel.make_header(patientname='patient_x', gender='Female')
highlevel.write_edf(str(current_dir / 'edf+C.edf'), signals, signal_headers, header, digital=True)

# export plain signal also as txt file (transposed for compatibility with AnalogSignal)
np.savetxt(str(current_dir / 'edf+C.txt'), signals.T, fmt='%d')
