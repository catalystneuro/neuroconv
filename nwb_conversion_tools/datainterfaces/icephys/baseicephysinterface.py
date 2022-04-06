"""Author: Luiz Tauffer."""
from abc import ABC
from typing import Optional

from pynwb import NWBFile
from pynwb.device import Device
from pynwb.icephys import IntracellularElectrode

from ...basedatainterface import BaseDataInterface
from ...tools.neo import (
    get_number_of_electrodes,
    get_number_of_segments,
    write_neo_to_nwb,
)
from ...utils import (
    OptionalFilePathType,
    get_schema_from_hdmf_class,
    get_schema_from_method_signature,
    get_base_schema,
)


try:
    from ndx_dandi_icephys import DandiIcephysMetadata

    HAVE_NDX_DANDI_ICEPHYS = True
except ImportError:
    HAVE_NDX_DANDI_ICEPHYS = False


class BaseIcephysInterface(BaseDataInterface, ABC):
    """Primary class for all intracellular NeoInterfaces."""

    neo_class = None

    @classmethod
    def get_source_schema(cls):
        source_schema = get_schema_from_method_signature(class_method=cls.__init__, exclude=[])
        return source_schema

    def __init__(self, file_paths: list):
        super().__init__(file_paths=file_paths)

        self.readers_list = list()
        for f in file_paths:
            self.readers_list.append(self.neo_class(filename=f))

        self.subset_channels = None
        self.n_segments = get_number_of_segments(neo_reader=self.readers_list[0], block=0)
        self.n_channels = get_number_of_electrodes(neo_reader=self.readers_list[0])

    def get_metadata_schema(self):
        metadata_schema = super().get_metadata_schema()

        metadata_schema["properties"]["Icephys"] = get_base_schema(tag="Icephys")
        metadata_schema["properties"]["Icephys"]["required"] = ["Device", "Electrode"]
        metadata_schema["properties"]["Icephys"]["properties"] = dict(
            Device=dict(type="array", minItems=1, items={"$ref": "#/properties/Icephys/properties/definitions/Device"}),
            Electrode=dict(
                type="array",
                minItems=1,
                items={"$ref": "#/properties/Icephys/properties/definitions/Electrode"},
            ),
        )
        metadata_schema["properties"]["Icephys"]["properties"]["definitions"] = dict(
            Device=get_schema_from_hdmf_class(Device),
            Electrode=get_schema_from_hdmf_class(IntracellularElectrode),
        )
        return metadata_schema

    def get_metadata(self):
        metadata = super().get_metadata()
        metadata["Icephys"] = dict(
            Device=[dict(name="DeviceIcephys", description="no description")],
            Electrode=[
                dict(name=f"electrode-{i}", description="no description", device="DeviceIcephys")
                for i in range(get_number_of_electrodes(self.readers_list[0]))
            ],
        )
        return metadata

    def run_conversion(
        self,
        nwbfile: NWBFile,
        metadata: dict = None,
        stub_test: bool = False,
        use_times: bool = False,
        save_path: OptionalFilePathType = None,
        overwrite: bool = False,
        write_as: str = "raw",
        es_key: str = None,
        icephys_experiment_type: Optional[str] = None,
    ):
        """
        Primary function for converting raw (unprocessed) RecordingExtractor data to the NWB standard.

        Parameters
        ----------
        nwbfile: NWBFile
            nwb file to which the recording information is to be added
        metadata: dict
            metadata info for constructing the nwb file (optional).
            Should be of the format
                metadata['Ecephys']['ElectricalSeries'] = dict(name=my_name, description=my_description)
        use_times: bool
            If True, the times are saved to the nwb file using recording.frame_to_time(). If False (default),
            the sampling rate is used.
        save_path: PathType
            Required if an nwbfile is not passed. Must be the path to the nwbfile
            being appended, otherwise one is created and written.
        overwrite: bool
            If using save_path, whether or not to overwrite the NWBFile if it already exists.
        stub_test: bool, optional (default False)
            If True, will truncate the data to run the conversion faster and take up less memory.
        buffer_mb: int (optional, defaults to 500MB)
            Maximum amount of memory (in MB) to use per iteration of the internal DataChunkIterator.
            Requires trace data in the RecordingExtractor to be a memmap object.
        write_as: str (optional, defaults to 'raw')
            Options: 'raw', 'lfp' or 'processed'
        es_key: str (optional)
            Key in metadata dictionary containing metadata info for the specific electrical series
        icephys_experiment_type: str (optional)
            Type of Icephys experiment. Allowed types are: 'voltage_clamp', 'current_clamp' and 'izero'.
            If no value is passed, 'voltage_clamp' is used as default.
        """
        if (
            HAVE_NDX_DANDI_ICEPHYS
            and "ndx-dandi-icephys" in metadata
            and "DandiIcephysMetadata" not in nwbfile.lab_meta_data
        ):
            nwbfile.add_lab_meta_data(DandiIcephysMetadata(**metadata["ndx-dandi-icephys"]))

        for i, reader in enumerate(self.readers_list):
            write_neo_to_nwb(
                neo_reader=reader,
                nwbfile=nwbfile,
                metadata=metadata,
                use_times=use_times,
                write_as=write_as,
                es_key=es_key,
                save_path=save_path,
                overwrite=overwrite if i == 0 else False,
                icephys_experiment_type=metadata["Icephys"]["Sessions"][i]["icephys_experiment_type"],
                stimulus_type=metadata["Icephys"]["Sessions"][i]["stimulus_type"],
            )
