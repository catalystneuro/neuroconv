"""Authors: Cody Baker and Ben Dichter."""
from abc import ABC

import spikeextractors as se
import numpy as np
from pynwb import NWBFile
from pynwb.ecephys import SpikeEventSeries

from ...basedatainterface import BaseDataInterface
from ...utils.json_schema import get_schema_from_hdmf_class, get_base_schema, get_schema_from_method_signature
from ...utils.spike_interface import add_devices, add_electrode_groups, add_electrodes, write_sorting


class BaseSortingExtractorInterface(BaseDataInterface, ABC):
    """Primary class for all SortingExtractor intefaces."""

    SX = None

    @classmethod
    def get_source_schema(cls):
        """Compile input schema for the SortingExtractor."""
        return get_schema_from_method_signature(cls.__init__)

    def __init__(self, **source_data):
        super().__init__(**source_data)
        self.sorting_extractor = self.SX(**source_data)

    def get_metadata_schema(self):
        """Compile metadata schema for the RecordingExtractor."""
        metadata_schema = get_base_schema(
            properties=dict(SpikeEventSeries=get_schema_from_hdmf_class(SpikeEventSeries))
        )
        return metadata_schema

    def run_conversion(
        self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False, write_ecephys_metadata: bool = False
    ):
        """
        Primary function for converting the data in a SortingExtractor to the NWB standard.

        Parameters
        ----------
        nwbfile: NWBFile
            nwb file to which the recording information is to be added
        metadata: dict
            metadata info for constructing the nwb file (optional).
            Should be of the format
                metadata['Ecephys']['UnitProperties'] = dict(name=my_name, description=my_description)
        stub_test: bool, optional (default False)
            If True, will truncate the data to run the conversion faster and take up less memory.
        write_ecephys_metadata: bool (optional, defaults to False)
            Write electrode information contained in the metadata.
        """
        if "UnitProperties" not in metadata:
            metadata["UnitProperties"] = []
        if write_ecephys_metadata and "Ecephys" in metadata:
            n_channels = max([len(x["data"]) for x in metadata["Ecephys"]["Electrodes"]])
            recording = se.NumpyRecordingExtractor(timeseries=np.array(range(n_channels)), sampling_frequency=1)

            add_devices(recording=recording, nwbfile=nwbfile, metadata=metadata)

            add_electrode_groups(recording=recording, nwbfile=nwbfile, metadata=metadata)

            add_electrodes(recording=recording, nwbfile=nwbfile, metadata=metadata)

        property_descriptions = dict()
        if stub_test:
            max_min_spike_time = max(
                [
                    min(x)
                    for y in self.sorting_extractor.get_unit_ids()
                    for x in [self.sorting_extractor.get_unit_spike_train(y)]
                    if any(x)
                ]
            )
            stub_sorting_extractor = se.SubSortingExtractor(
                self.sorting_extractor,
                unit_ids=self.sorting_extractor.get_unit_ids(),
                start_frame=0,
                end_frame=1.1 * max_min_spike_time,
            )
            sorting_extractor = stub_sorting_extractor
        else:
            sorting_extractor = self.sorting_extractor

        for metadata_column in metadata["UnitProperties"]:
            assert len(metadata_column["data"]) == len(
                sorting_extractor.get_unit_ids()
            ), f"The metadata_column '{metadata_column['name']}' data must have the same dimension as the sorting IDs!"

            property_descriptions.update({metadata_column["name"]: metadata_column["description"]})
            for unit_idx, unit_id in enumerate(sorting_extractor.get_unit_ids()):
                if metadata_column["name"] == "electrode_group":
                    if nwbfile.electrode_groups:
                        data = nwbfile.electrode_groups[metadata_column["data"][unit_idx]]
                        sorting_extractor.set_unit_property(unit_id, metadata_column["name"], data)
                else:
                    data = metadata_column["data"][unit_idx]
                    sorting_extractor.set_unit_property(unit_id, metadata_column["name"], data)

        write_sorting(sorting_extractor, property_descriptions=property_descriptions, nwbfile=nwbfile)
