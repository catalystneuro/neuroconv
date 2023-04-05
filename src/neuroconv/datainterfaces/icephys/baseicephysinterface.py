from typing import Optional, Tuple
from warnings import warn

import numpy as np
from pynwb import NWBHDF5IO, NWBFile

from ...baseextractorinterface import BaseExtractorInterface
from ...tools.nwb_helpers import make_nwbfile_from_metadata
from ...utils import (
    FilePathType,
    get_metadata_schema_for_icephys,
    get_schema_from_hdmf_class,
    get_schema_from_method_signature,
)

try:
    from ndx_dandi_icephys import DandiIcephysMetadata

    HAVE_NDX_DANDI_ICEPHYS = True
except ImportError:
    DandiIcephysMetadata = None
    HAVE_NDX_DANDI_ICEPHYS = False


class BaseIcephysInterface(BaseExtractorInterface):
    """Primary class for all intracellular NeoInterfaces."""

    ExtractorModuleName = "neo"

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_schema_from_method_signature(method=cls.__init__, exclude=[])
        return source_schema

    def __init__(self, file_paths: list):
        from ...tools.neo import get_number_of_electrodes, get_number_of_segments

        super().__init__(file_paths=file_paths)

        self.readers_list = list()
        for f in file_paths:
            self.readers_list.append(self.get_extractor()(filename=f))

        self.subset_channels = None
        self.n_segments = get_number_of_segments(neo_reader=self.readers_list[0], block=0)
        self.n_channels = get_number_of_electrodes(neo_reader=self.readers_list[0])

    def get_metadata_schema(self) -> dict:
        metadata_schema = super().get_metadata_schema()
        if DandiIcephysMetadata:
            metadata_schema["properties"]["ndx-dandi-icephys"] = get_schema_from_hdmf_class(DandiIcephysMetadata)
        metadata_schema["properties"]["Icephys"] = get_metadata_schema_for_icephys()
        return metadata_schema

    def get_metadata(self) -> dict:
        from ...tools.neo import get_number_of_electrodes

        metadata = super().get_metadata()
        metadata["Icephys"] = dict(
            Device=[dict(name="DeviceIcephys", description="no description")],
            Electrode=[
                dict(name=f"electrode-{i}", description="no description", device="DeviceIcephys")
                for i in range(get_number_of_electrodes(self.readers_list[0]))
            ],
        )
        return metadata

    def get_original_timestamps(self) -> np.ndarray:
        raise NotImplementedError(
            "Unable to retrieve the original unaltered timestamps for this interface! "
            "Define the `get_original_timestamps` method for this interface."
        )

    def get_timestamps(self) -> np.ndarray:
        raise NotImplementedError(
            "Unable to retrieve timestamps for this interface! Define the `get_timestamps` method for this interface."
        )

    def align_timestamps(self, aligned_timestamps: np.ndarray):
        raise NotImplementedError(
            "The protocol for synchronizing the timestamps of this interface has not been specified!"
        )

    def _run_conversion(
        self,
        nwbfile: NWBFile,
        metadata: dict = None,
        icephys_experiment_type: str = "voltage_clamp",
        skip_electrodes: Tuple[int] = (),
        # TODO: to be removed
        save_path: Optional[FilePathType] = None,  # pragma: no cover
    ):
        """
        Primary function for converting raw (unprocessed) intracellular data to the NWB standard.

        Parameters
        ----------
        nwbfile : NWBFile
            NWB file to which the recording information is to be added
        metadata : dict, optional
            metadata info for constructing the nwb file (optional).
        icephys_experiment_type : {'voltage_clamp', 'current_clamp', 'izero'}
            Type of icephys recording.
        skip_electrodes : tuple, optional
            Electrode IDs to skip. Defaults to ().
        save_path: string, optional
        """
        from ...tools.neo import write_neo_to_nwb

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
                overwrite=overwrite if i == 0 else False,
                icephys_experiment_type=metadata["Icephys"]["Sessions"][i]["icephys_experiment_type"],
                stimulus_type=metadata["Icephys"]["Sessions"][i]["stimulus_type"],
                skip_electrodes=skip_electrodes,
            )

        if save_path:
            with NWBHDF5IO(save_path, "w") as io:
                io.write(nwbfile)
