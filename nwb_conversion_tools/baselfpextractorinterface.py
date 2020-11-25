"""Authors: Cody Baker and Ben Dichter."""
import numpy as np
import spikeextractors as se
from pynwb import NWBFile
from pynwb.ecephys import ElectricalSeries, LFP
from hdmf.backends.hdf5.h5_utils import H5DataIO
from hdmf.data_utils import DataChunkIterator

from .baserecordingextractorinterface import BaseRecordingExtractorInterface
from .utils import check_module


class BaseLFPExtractorInterface(BaseRecordingExtractorInterface):
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

        if nwbfile.electrodes is None \
                or lfp_extractor.get_num_channels() <= len(nwbfile.electrodes.id.data[:]):
            electrode_inds = list(range(lfp_extractor.get_num_channels()))
        else:
            electrode_inds = list(range(len(nwbfile.electrodes.id.data[:])))
        table_region = nwbfile.create_electrode_table_region(electrode_inds, "Electrode table reference.")

        ecephys_mod = check_module(
            nwbfile,
            'ecephys',
            "intermediate data from extracellular electrophysiology recordings, e.g., LFP"
        )
        if 'LFP' not in ecephys_mod.data_interfaces:
            ecephys_mod.add_data_interface(LFP(name='LFP'))

        if isinstance(lfp_extractor.get_traces(), np.memmap):
            n_bytes = np.dtype(lfp_extractor.get_dtype()).itemsize
            buffer_size = int(buffer_mb * 1e6) // (lfp_extractor.get_num_channels() * n_bytes)
            lfp_data = DataChunkIterator(
                lfp_extractor.get_traces(),
                buffer_size=buffer_size
            )
        else:
            def data_generator(recording, channels_ids):
                #  generates data chunks for iterator
                for id in channels_ids:
                    data = recording.get_traces(channel_ids=[id]).flatten()
                    yield data
            lfp_data = DataChunkIterator(
                data=data_generator(
                    recording=lfp_extractor,
                    channels_ids=lfp_extractor.get_channel_ids()
                ),
                iter_axis=1,  # nwb standard is time as zero axis
                maxshape=(lfp_extractor.get_num_frames(), lfp_extractor.get_num_channels())
            )
        ecephys_mod.data_interfaces['LFP'].add_electrical_series(
            ElectricalSeries(
                name='LFP',
                description="Local field potential signal.",
                data=H5DataIO(lfp_data, compression="gzip"),
                electrodes=table_region,
                conversion=1e-6,
                rate=lfp_extractor.get_sampling_frequency(),
                resolution=np.nan
            )
        )
