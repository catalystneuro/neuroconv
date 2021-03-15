"""Authors: Cody Baker and Ben Dichter."""
from abc import ABC

import spikeextractors as se
import numpy as np
from pynwb import NWBFile
from pynwb.ecephys import SpikeEventSeries

from .basedatainterface import BaseDataInterface
from .utils import get_schema_from_hdmf_class
from .json_schema_utils import get_base_schema, get_schema_from_method_signature, fill_defaults


class BaseSortingExtractorInterface(BaseDataInterface, ABC):
    SX = None

    @classmethod
    def get_source_schema(cls):
        return get_schema_from_method_signature(cls.SX.__init__)

    def __init__(self, **source_data):
        super().__init__(**source_data)
        self.sorting_extractor = self.SX(**source_data)

    def get_metadata_schema(self):
        metadata_schema = get_base_schema(
            required=['SpikeEventSeries'],
            properties=dict(
                SpikeEventSeries=get_schema_from_hdmf_class(SpikeEventSeries)
            )
        )
        # fill_defaults(metadata_schema, self.get_metadata())

        return metadata_schema

    def run_conversion(self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False, 
                       write_ecephys_metadata: bool = False):
        if 'UnitProperties' not in metadata:
            metadata['UnitProperties'] = []
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

        property_descriptions = dict()
        if stub_test:
            max_min_spike_time = max([min(x) for y in self.sorting_extractor.get_unit_ids()
                                      for x in [self.sorting_extractor.get_unit_spike_train(y)] if any(x)])
            stub_sorting_extractor = se.SubSortingExtractor(
                self.sorting_extractor,
                unit_ids=self.sorting_extractor.get_unit_ids(),
                start_frame=0,
                end_frame=1.1 * max_min_spike_time
            )
            sorting_extractor = stub_sorting_extractor
        else:
            sorting_extractor = self.sorting_extractor

        for metadata_column in metadata['UnitProperties']:
            assert len(metadata_column['data']) == len(sorting_extractor.get_unit_ids()), \
                f"The metadata_column '{metadata_column['name']}' data must have the same dimension as the sorting IDs!"

            property_descriptions.update({metadata_column['name']: metadata_column['description']})
            for unit_idx, unit_id in enumerate(sorting_extractor.get_unit_ids()):
                if metadata_column['name'] == 'electrode_group':
                    if nwbfile.electrode_groups:
                        data = nwbfile.electrode_groups[metadata_column['data'][unit_idx]]
                        sorting_extractor.set_unit_property(unit_id, metadata_column['name'], data)
                else:
                    data = metadata_column['data'][unit_idx]
                    sorting_extractor.set_unit_property(unit_id, metadata_column['name'], data)

        se.NwbSortingExtractor.write_sorting(
            sorting_extractor,
            property_descriptions=property_descriptions,
            nwbfile=nwbfile
        )
