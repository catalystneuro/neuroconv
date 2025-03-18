import importlib.util

import numpy as np
from pydantic import FilePath, validate_call
from pynwb import NWBFile

from ...baseextractorinterface import BaseExtractorInterface
from ...tools.nwb_helpers import make_nwbfile_from_metadata
from ...utils import (
    get_json_schema_from_method_signature,
    get_metadata_schema_for_icephys,
    get_schema_from_hdmf_class,
)


class BaseIcephysInterface(BaseExtractorInterface):
    """Primary class for all intracellular NeoInterfaces."""

    keywords = ("intracellular electrophysiology", "patch clamp", "current clamp")

    ExtractorModuleName = "neo"

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_json_schema_from_method_signature(method=cls.__init__, exclude=[])
        return source_schema

    @validate_call
    def __init__(self, file_paths: list[FilePath]):
        # Check if the ndx_dandi_icephys module is available
        dandi_icephys_spec = importlib.util.find_spec("ndx_dandi_icephys")
        if dandi_icephys_spec is not None:
            from ndx_dandi_icephys import DandiIcephysMetadata

            self.DandiIcephysMetadata = DandiIcephysMetadata

            self.HAVE_NDX_DANDI_ICEPHYS = True
        else:
            self.DandiIcephysMetadata = None
            self.HAVE_NDX_DANDI_ICEPHYS = False

        from ...tools.neo import get_number_of_electrodes, get_number_of_segments

        self.source_data = dict()
        self.source_data["file_paths"] = file_paths

        self.readers_list = list()
        for f in file_paths:
            self.readers_list.append(self.get_extractor()(filename=f))

        self.subset_channels = None
        self.n_segments = get_number_of_segments(neo_reader=self.readers_list[0], block=0)
        self.n_channels = get_number_of_electrodes(neo_reader=self.readers_list[0])

        self._timestamps = None

    def get_metadata_schema(self) -> dict:
        metadata_schema = super().get_metadata_schema()
        if self.DandiIcephysMetadata is not None:
            metadata_schema["properties"]["ndx-dandi-icephys"] = get_schema_from_hdmf_class(self.DandiIcephysMetadata)
        metadata_schema["properties"]["Icephys"] = get_metadata_schema_for_icephys()
        return metadata_schema

    def get_metadata(self) -> dict:
        from ...tools.neo import get_number_of_electrodes

        metadata = super().get_metadata()
        metadata["Icephys"] = dict(
            Device=[dict(name="DeviceIcephys", description="no description")],
            Electrodes=[
                dict(name=f"electrode-{i}", description="no description", device="DeviceIcephys")
                for i in range(get_number_of_electrodes(self.readers_list[0]))
            ],
        )
        return metadata

    def get_original_timestamps(self) -> np.ndarray:
        raise NotImplementedError("Icephys interfaces do not yet support timestamps.")

    def get_timestamps(self) -> np.ndarray:
        raise NotImplementedError("Icephys interfaces do not yet support timestamps.")

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray):
        raise NotImplementedError("Icephys interfaces do not yet support timestamps.")

    def set_aligned_starting_time(self, aligned_starting_time: float):
        raise NotImplementedError("This icephys interface has not specified the method for aligning starting time.")

    def align_by_interpolation(self, unaligned_timestamps: np.ndarray, aligned_timestamps: np.ndarray):
        raise NotImplementedError("Icephys interfaces do not yet support timestamps.")

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict = None,
        icephys_experiment_type: str = "voltage_clamp",
        skip_electrodes: tuple[int] = (),
    ):
        """
        Primary function for converting raw (unprocessed) intracellular data to the NWB standard.

        Parameters
        ----------
        nwbfile : NWBFile
            nwb file to which the recording information is to be added
        metadata : dict, optional
            metadata info for constructing the nwb file (optional).
        icephys_experiment_type : {'voltage_clamp', 'current_clamp', 'izero'}
            Type of icephys recording.
        skip_electrodes : tuple, optional
            Electrode IDs to skip. Defaults to ().
        """
        from ...tools.neo import add_neo_to_nwb

        if nwbfile is None:
            nwbfile = make_nwbfile_from_metadata(metadata)

        if (
            self.HAVE_NDX_DANDI_ICEPHYS
            and "ndx-dandi-icephys" in metadata
            and "DandiIcephysMetadata" not in nwbfile.lab_meta_data
        ):
            nwbfile.add_lab_meta_data(self.DandiIcephysMetadata(**metadata["ndx-dandi-icephys"]))

        for i, reader in enumerate(self.readers_list):
            add_neo_to_nwb(
                neo_reader=reader,
                nwbfile=nwbfile,
                metadata=metadata,
                icephys_experiment_type=metadata["Icephys"]["Sessions"][i]["icephys_experiment_type"],
                stimulus_type=metadata["Icephys"]["Sessions"][i]["stimulus_type"],
                skip_electrodes=skip_electrodes,
            )
