This dataset is a shortened version of the public `YutaMouse42-151117` dataset provided by the BuzsakiLab
The public dataset is available [here](https://app.globus.org/file-manager?origin_id=188a6110-96db-11eb-b7a9-f57b2d55370d&origin_path=%2FSenzaiY%2FYutaMouse43%2FYutaMouse43-151117%2F)

The `.xml` format contains general metadata of the recording and can be used to extract
- the number of channels: `nChannels`
- the grouping of channels: groups
- the sampling rate: `samplingRate`
- the number of bits per recording sample (for dat, eeg and spk files): `nBits`
- the number of samples per recorded waveform: `nsamples`
- the amplification factor: `amplification`
- the voltage range: `voltageRange`

The `.eeg`/`.lfp` format contains continuously sampled data at a 'low' sampling rate and has the dimensions `(totalSamples, nChannels`). The test files here contain 10 total samples.

The `.spk.*` format contains waveforms of spikes across multiple channels. It has the dimensions `(nSpikes,nSamples, nChannels`). The test files here contain 10 spikes each.

The `.res.*` format contains the timestamps of the detected waveforms . It is an ASCII file with one timestamp per spike.

The `.clu.*` format contains the assignment of spike to clusters . It is an ASCII file with cluster id per spike.


Note: The `YutaMouse42-151117.lfp` file in this dataset is copy of the `YutaMouse42-151117.eeg` file.


For an overview of the data layout for different formats, see also http://neurosuite.sourceforge.net/formats.html
