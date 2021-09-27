"""Authors: Cody Baker and Ben Dichter."""
from abc import ABC

import spikeextractors as se
import numpy as np
from pynwb import NWBFile

from ...basedatainterface import BaseDataInterface
from ...utils.json_schema import get_base_schema, get_schema_from_method_signature
from ...utils.spike_interface import add_devices, add_electrode_groups, add_electrodes, write_sorting


class BaseSortingExtractorInterface(BaseDataInterface, ABC):
    """Primary class for all SortingExtractor intefaces."""

    SX = None

    def __init__(self, **source_data):
        super().__init__(**source_data)
        self.sorting_extractor = self.SX(**source_data)

    def get_metadata_schema(self):
        """Compile metadata schema for the RecordingExtractor."""
        metadata_schema = super().get_metadata_schema()

        # Initiate Ecephys metadata
        metadata_schema["properties"]["Ecephys"] = get_base_schema(tag="Ecephys")
        metadata_schema["properties"]["Ecephys"]["required"] = []
        metadata_schema["properties"]["Ecephys"]["properties"] = dict(
            UnitProperties=dict(
                type="array",
                minItems=0,
                renderForm=False,
                items={"$ref": "#/properties/Ecephys/properties/definitions/UnitProperties"},
            ),
        )
        # Schema definition for arrays
        metadata_schema["properties"]["Ecephys"]["properties"]["definitions"] = dict(
            UnitProperties=dict(
                type="object",
                additionalProperties=False,
                required=["name"],
                properties=dict(
                    name=dict(type="string", description="name of this units column"),
                    description=dict(type="string", description="description of this units column"),
                ),
            ),
        )
        return metadata_schema

    def run_conversion(
        self, nwbfile: NWBFile, metadata: dict, stub_test: bool = False, write_ecephys_metadata: bool = False
    ):
        """
        Primary function for converting the data in a SortingExtractor to NWB format.

        Parameters
        ----------
        nwbfile: NWBFile
            nwb file to which the recording information is to be added
        metadata: dict
            metadata info for constructing the nwb file (optional).
            Should be of the format
                metadata["Ecephys"]["UnitProperties"] = dict(name=my_name, description=my_description)
        stub_test: bool, optional (default False)
            If True, will truncate the data to run the conversion faster and take up less memory.
        write_ecephys_metadata: bool (optional, defaults to False)
            Write electrode information contained in the metadata.
        """
        if write_ecephys_metadata and "Ecephys" in metadata:
            n_channels = max([len(x["data"]) for x in metadata["Ecephys"]["Electrodes"]])
            recording = se.NumpyRecordingExtractor(
                timeseries=np.array(range(n_channels)),
                sampling_frequency=self.sorting_extractor.get_sampling_frequency(),
            )
            add_devices(recording=recording, nwbfile=nwbfile, metadata=metadata)
            add_electrode_groups(recording=recording, nwbfile=nwbfile, metadata=metadata)
            add_electrodes(recording=recording, nwbfile=nwbfile, metadata=metadata)

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
            # TODO: copy over unit properties (SubRecording and SubSorting do not carry these automatically)
            sorting_extractor = stub_sorting_extractor
        else:
            sorting_extractor = self.sorting_extractor

        property_descriptions = dict()
        for metadata_column in metadata.get("Ecephys", dict()).get("UnitProperties", []):
            property_descriptions.update({metadata_column["name"]: metadata_column["description"]})
            for unit_id in sorting_extractor.get_unit_ids():
                # Special condition for wrapping electrode group pointers to actual object ids rather than string names
                if metadata_column["name"] == "electrode_group":
                    if nwbfile.electrode_groups:
                        sorting_extractor.set_unit_property(
                            unit_id=unit_id,
                            property_name=metadata_column["name"],
                            value=nwbfile.electrode_groups[
                                self.sorting_extractor.get_unit_property(
                                    unit_id=unit_id, property_name="electrode_group"
                                )
                            ],
                        )
        write_sorting(sorting_extractor, property_descriptions=property_descriptions, nwbfile=nwbfile)
