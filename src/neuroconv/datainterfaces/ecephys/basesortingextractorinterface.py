"""Authors: Cody Baker and Ben Dichter."""
from typing import Optional

import numpy as np
from pynwb import NWBFile
from pynwb.device import Device
from pynwb.ecephys import ElectrodeGroup

from ...baseextractorinterface import BaseExtractorInterface
from ...utils import get_base_schema, get_schema_from_hdmf_class, OptionalFilePathType


class BaseSortingExtractorInterface(BaseExtractorInterface):
    """Primary class for all SortingExtractor intefaces."""

    ExtractorModuleName: Optional[str] = "spikeinterface.extractors"

    def __init__(self, verbose=True, **source_data):
        super().__init__(**source_data)
        self.sorting_extractor = self.Extractor(**source_data)
        self.verbose = verbose

    def get_metadata_schema(self):
        """Compile metadata schema for the RecordingExtractor."""
        metadata_schema = super().get_metadata_schema()

        # Initiate Ecephys metadata
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ecephys"] = get_base_schema(tag="Ecephys")
        metadata_schema["properties"]["Ecephys"]["required"] = []
        metadata_schema["properties"]["Ecephys"]["properties"] = dict(
            Device=dict(type="array", minItems=1, items={"$ref": "#/properties/Ecephys/properties/definitions/Device"}),
            ElectrodeGroup=dict(
                type="array", minItems=1, items={"$ref": "#/properties/Ecephys/properties/definitions/ElectrodeGroup"}
            ),
            Electrodes=dict(
                type="array",
                minItems=0,
                renderForm=False,
                items={"$ref": "#/properties/Ecephys/properties/definitions/Electrodes"},
            ),
            UnitProperties=dict(
                type="array",
                minItems=0,
                renderForm=False,
                items={"$ref": "#/properties/Ecephys/properties/definitions/UnitProperties"},
            ),
        )

        # Schema definition for arrays
        metadata_schema["properties"]["Ecephys"]["properties"]["definitions"] = dict(
            Device=get_schema_from_hdmf_class(Device),
            ElectrodeGroup=get_schema_from_hdmf_class(ElectrodeGroup),
            Electrodes=dict(
                type="object",
                additionalProperties=False,
                required=["name"],
                properties=dict(
                    name=dict(type="string", description="name of this electrodes column"),
                    description=dict(type="string", description="description of this electrodes column"),
                ),
            ),
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

    def subset_sorting(self):
        from spikeextractors import SortingExtractor, SubSortingExtractor
        from spikeinterface import BaseSorting

        max_min_spike_time = max(
            [
                min(x)
                for y in self.sorting_extractor.get_unit_ids()
                for x in [self.sorting_extractor.get_unit_spike_train(y)]
                if any(x)
            ]
        )
        end_frame = 1.1 * max_min_spike_time
        if isinstance(self.sorting_extractor, SortingExtractor):
            stub_sorting_extractor = SubSortingExtractor(
                self.sorting_extractor,
                unit_ids=self.sorting_extractor.get_unit_ids(),
                start_frame=0,
                end_frame=end_frame,
            )
        elif isinstance(self.sorting_extractor, BaseSorting):
            stub_sorting_extractor = self.sorting_extractor.frame_slice(start_frame=0, end_frame=end_frame)
        else:
            raise TypeError(f"{self.sorting_extractor} should be either se.SortingExtractor or si.BaseSorting")
        return stub_sorting_extractor

    def run_conversion(
        self,
        nwbfile_path: OptionalFilePathType = None,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        overwrite: bool = False,
        stub_test: bool = False,
        write_ecephys_metadata: bool = False,
    ):
        """
        Primary function for converting the data in a SortingExtractor to NWB format.

        Parameters
        ----------
        nwbfile_path: FilePathType
            Path for where to write or load (if overwrite=False) the NWBFile.
            If specified, the context will always write to this location.
        nwbfile: NWBFile, optional
            If passed, this function will fill the relevant fields within the NWBFile object.
            E.g., calling
                write_recording(recording=my_recording_extractor, nwbfile=my_nwbfile)
            will result in the appropriate changes to the my_nwbfile object.
            If neither 'nwbfile_path' nor 'nwbfile' are specified, an NWBFile object will be automatically generated
            and returned by the function.
        metadata: dict
            Information for constructing the nwb file (optional) and units table descriptions.
            Should be of the format::

                metadata["Ecephys"]["UnitProperties"] = dict(name=my_name, description=my_description)
        overwrite: bool, optional
            Whether or not to overwrite the NWBFile if one exists at the nwbfile_path.
            The default is False (append mode).
        stub_test: bool, optional (default False)
            If True, will truncate the data to run the conversion faster and take up less memory.
        write_ecephys_metadata: bool (optional, defaults to False)
            Write electrode information contained in the metadata.
        """
        from spikeinterface import NumpyRecording

        from ...tools.spikeinterface import add_devices, add_electrode_groups, add_electrodes, write_sorting

        if write_ecephys_metadata and "Ecephys" in metadata:
            n_channels = max([len(x["data"]) for x in metadata["Ecephys"]["Electrodes"]])
            recording = NumpyRecording(
                traces_list=[np.empty(shape=n_channels)],
                sampling_frequency=self.sorting_extractor.get_sampling_frequency(),
            )
            add_devices(recording=recording, nwbfile=nwbfile, metadata=metadata)
            add_electrode_groups(recording=recording, nwbfile=nwbfile, metadata=metadata)
            add_electrodes(recording=recording, nwbfile=nwbfile, metadata=metadata)
        if stub_test:
            sorting_extractor = self.subset_sorting()
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
        write_sorting(
            sorting_extractor,
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            metadata=metadata,
            overwrite=overwrite,
            verbose=self.verbose,
            property_descriptions=property_descriptions,
        )
