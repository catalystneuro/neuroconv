from typing import List, Literal, Optional, Union

import numpy as np
from pynwb import NWBFile
from pynwb.device import Device
from pynwb.ecephys import ElectrodeGroup

from .baserecordingextractorinterface import BaseRecordingExtractorInterface
from ...baseextractorinterface import BaseExtractorInterface
from ...utils import (
    DeepDict,
    OptionalFilePathType,
    get_base_schema,
    get_schema_from_hdmf_class,
)


class BaseSortingExtractorInterface(BaseExtractorInterface):
    """Primary class for all SortingExtractor interfaces."""

    keywords = BaseExtractorInterface.keywords + ["extracellular electrophysiology", "spike sorting"]

    ExtractorModuleName = "spikeinterface.extractors"

    def __init__(self, verbose=True, **source_data):
        super().__init__(**source_data)
        self.sorting_extractor = self.get_extractor()(**source_data)
        self.verbose = verbose
        self._number_of_segments = self.sorting_extractor.get_num_segments()

    def get_metadata_schema(self) -> dict:
        """Compile metadata schema for the RecordingExtractor."""

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

    def register_recording(self, recording_interface: BaseRecordingExtractorInterface):
        self.sorting_extractor.register_recording(recording=recording_interface.recording_extractor)

    def get_original_timestamps(self) -> np.ndarray:
        raise NotImplementedError(
            "Unable to fetch original timestamps for a SortingInterface since it relies upon an attached recording."
        )

    def get_timestamps(self) -> Union[np.ndarray, List[np.ndarray]]:
        if not self.sorting_extractor.has_recording():
            raise NotImplementedError(
                "In order to align timestamps for a SortingInterface, it must have a recording "
                "object attached to it! Please attach one by calling `.register_recording(recording_interface=...)`."
            )
        if self._number_of_segments == 1:
            return self.sorting_extractor._recording.get_times()
        else:
            return [
                self.sorting_extractor._recording.get_times(segment_index=segment_index)
                for segment_index in range(self._number_of_segments)
            ]

    def align_timestamps(self, aligned_timestamps: Union[np.ndarray, List[np.ndarray]]):
        """
        Replace all timestamps for the attached interface with those aligned to the common session start time.

        Must be in units seconds relative to the common 'session_start_time'.
        Must have a RecordingInterface attached; call `.register_recording(recording_interface=...)` to accomplish this.

        When a SortingInterface has a recording attached, it infers the timing via the frame indices of the
        timestamps from the corresponding recording segment. This method aligns the timestamps of that recording
        so that the SortingExtractor can automatically infer the timing from the frames.

        Parameters
        ----------
        aligned_timestamps : numpy.ndarray or list of numpy.ndarray
            The synchronized timestamps for data in this interface.
            If there is more than one segment in the sorting/recording pair, then
        """
        if not self.sorting_extractor.has_recording():
            raise NotImplementedError(
                "In order to align timestamps for a SortingInterface, it must have a recording "
                "object attached to it! Please attach one by calling `.register_recording(recording_interface=...)`."
            )

        if self._number_of_segments == 1:
            self.sorting_extractor._recording.set_times(times=aligned_timestamps)
        else:
            assert isinstance(
                aligned_timestamps, list
            ), "Recording has multiple segment! Please pass a list of timestamps to align each segment."
            assert (
                len(aligned_timestamps) == self._number_of_segments
            ), f"The number of timestamp vectors ({len(aligned_timestamps)}) does not match the number of segments ({self._number_of_segments})!"

            for segment_index in range(self._number_of_segments):
                self.sorting_extractor._recording.set_times(
                    times=aligned_timestamps[segment_index], segment_index=segment_index
                )

    def align_starting_time(self, starting_time: float):
        for sorting_segment in self.sorting_extractor._sorting_segments:
            if sorting_segment._t_start is None:
                sorting_segment._t_start = starting_time
            else:
                sorting_segment._t_start += starting_time

    def subset_sorting(self):
        max_min_spike_time = max(
            [
                min(x)
                for y in self.sorting_extractor.get_unit_ids()
                for x in [self.sorting_extractor.get_unit_spike_train(y)]
                if any(x)
            ]
        )
        end_frame = 1.1 * max_min_spike_time
        stub_sorting_extractor = self.sorting_extractor.frame_slice(start_frame=0, end_frame=end_frame)
        return stub_sorting_extractor

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: Optional[DeepDict] = None,
        stub_test: bool = False,
        write_ecephys_metadata: bool = False,
        write_as: Literal["units", "processing"] = "units",
        units_name: str = "units",
        units_description: str = "Autogenerated by neuroconv.",
    ):
        """
        Primary function for converting the data in a SortingExtractor to NWB format.

        Parameters
        ----------
        nwbfile : NWBFile
            Fill the relevant fields within the NWBFile object.
        metadata : DeepDict
            Information for constructing the NWB file (optional) and units table descriptions.
            Should be of the format::

                metadata["Ecephys"]["UnitProperties"] = dict(name=my_name, description=my_description)
        stub_test : bool, default: False
            If True, will truncate the data to run the conversion faster and take up less memory.
        write_ecephys_metadata : bool, default: False
            Write electrode information contained in the metadata.
        write_as : {'units', 'processing'}
            How to save the units table in the nwb file. Options:
            - 'units' will save it to the official NWBFile.Units position; recommended only for the final form of the data.
            - 'processing' will save it to the processing module to serve as a historical provenance for the official table.
        units_name : str, default: 'units'
            The name of the units table. If write_as=='units', then units_name must also be 'units'.
        units_description : str, default: 'Autogenerated by neuroconv.'
        """
        from spikeinterface import NumpyRecording

        from ...tools.spikeinterface import (
            add_devices,
            add_electrode_groups,
            add_electrodes,
            add_sorting,
        )

        if write_ecephys_metadata and "Ecephys" in metadata:
            n_channels = max([len(x["data"]) for x in metadata["Ecephys"]["Electrodes"]])
            recording = NumpyRecording(
                traces_list=[np.empty(shape=n_channels)],
                sampling_frequency=self.sorting_extractor.get_sampling_frequency(),
            )
            add_devices(nwbfile=nwbfile, metadata=metadata)
            add_electrode_groups(recording=recording, nwbfile=nwbfile, metadata=metadata)
            add_electrodes(recording=recording, nwbfile=nwbfile, metadata=metadata)
        if stub_test:
            sorting_extractor = self.subset_sorting()
        else:
            sorting_extractor = self.sorting_extractor
        property_descriptions = dict()
        for metadata_column in metadata["Ecephys"].get("UnitProperties", []):
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
        add_sorting(
            sorting_extractor,
            nwbfile=nwbfile,
            property_descriptions=property_descriptions,
            write_as=write_as,
            units_name=units_name,
            units_description=units_description,
        )
