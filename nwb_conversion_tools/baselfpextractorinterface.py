"""Authors: Cody Baker and Ben Dichter."""
from abc import ABC

import numpy as np
import spikeextractors as se
from pynwb import NWBFile
from pynwb.ecephys import ElectricalSeries, LFP
from hdmf.backends.hdf5.h5_utils import H5DataIO
from hdmf.data_utils import DataChunkIterator

from .baserecordingextractorinterface import BaseRecordingExtractorInterface
from .utils import check_module


class BaseRecordingExtractorInterface(BaseRecordingExtractorInterface, ABC):
    """Primary class for all LFP data interfaces."""

    def run_conversion(self, nwbfile: NWBFile, metadata: dict = None, stub_test: bool = False,
                       write_ecephys_metadata: bool = False, buffer_mb: int = 500):
        """
        Primary function for converting recording extractor data to nwb.

        Parameters
        ----------
        nwbfile: pynwb.NWBFile
        metadata: dict
        stub_test: bool, optional (default False)
            If True, will truncate the data to run the conversion faster and take up less memory.
        write_ecephys_metadata: bool, optional (default False)
            If True, will use the information in metadata['Ecephys'] to write electrode metadata into the NWBFile.
        buffer_mb: int (optional, defaults to 500MB)
            Maximum amount of memory (in MB) to use per iteration of the DataChunkIterator
            (requires traces to be memmap objects)
        """
        if write_ecephys_metadata and 'Ecephys' in metadata:
            n_channels = max([len(x['data']) for x in metadata['Ecephys']['Electrodes']])
            recording = se.NumpyRecordingExtractor(timeseries=np.array(range(n_channels)), sampling_frequency=1)
            se.NwbRecordingExtractor.add_devices(
                recording=recording,
                nwbfile=nwbfile,
                metadata=metadata
            )
            se.NwbRecordingExtractor.add_electrode_groups(
                recording=recording,
                nwbfile=nwbfile,
                metadata=metadata
            )
            se.NwbRecordingExtractor.add_electrodes(
                recording=recording,
                nwbfile=nwbfile,
                metadata=metadata
            )

        lfp_extractor = self.recording_extractor
        if stub_test or self.subset_channels is not None:
            kwargs = dict()

            if stub_test:
                num_frames = 100
                end_frame = min([num_frames, self.recording_extractor.get_num_frames()])
                kwargs.update(end_frame=end_frame)

            if self.subset_channels is not None:
                kwargs.update(channel_ids=self.subset_channels)

            lfp_extractor = se.SubRecordingExtractor(
                self.recording_extractor,
                **kwargs
            )

        if self.subset_channels is None:
            if nwbfile.electrodes is not None \
                    and lfp_extractor.get_num_channels() <= len(nwbfile.electrodes.id.data[:]):
                electrode_inds = list(range(lfp_extractor.get_num_channels()))
            else:
                electrode_inds = list(range(len(nwbfile.electrodes.id.data[:])))

        table_region = nwbfile.create_electrode_table_region(electrode_inds, 'electrode table reference')
        n_bytes = np.dtype(lfp_extractor.get_dtype()).itemsize
        buffer_size = int(buffer_mb * 1e6) // (lfp_extractor.get_num_channels() * n_bytes)

        if isinstance(lfp_extractor.get_traces(), np.memmap):
            data = H5DataIO(
                DataChunkIterator(
                    lfp_extractor.get_traces(),
                    buffer_size=buffer_size
                ),
                compression='gzip'
            )
            lfp_electrical_series = ElectricalSeries(
                name="LFP",
                description="Local field potential signal.",
                data=data,
                electrodes=table_region,
                conversion=1e-6,
                rate=lfp_extractor.get_sampling_frequency(),
                resolution=np.nan
            )
            ecephys_mod = check_module(
                nwbfile,
                'ecephys',
                "intermediate data from extracellular electrophysiology recordings, e.g., LFP"
            )
            if 'LFP' not in ecephys_mod.data_interfaces:
                ecephys_mod.add_data_interface(LFP(name='LFP'))
            ecephys_mod.data_interfaces['LFP'].add_electrical_series(lfp_electrical_series)
        else:
            raise NotImplementedError("LFP interface is not setup to convert non-memory maps!")
