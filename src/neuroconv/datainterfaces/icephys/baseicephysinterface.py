"""Author: Luiz Tauffer."""
from typing import Optional, Tuple
from warnings import warn

from pynwb import NWBFile, NWBHDF5IO

from ...baseextractorinterface import BaseExtractorInterface
from ...tools.nwb_helpers import make_nwbfile_from_metadata
from ...utils import (
    OptionalFilePathType,
    get_schema_from_hdmf_class,
    get_schema_from_method_signature,
    get_metadata_schema_for_icephys,
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
    def get_source_schema(cls):
        source_schema = get_schema_from_method_signature(class_method=cls.__init__, exclude=[])
        return source_schema

    def __init__(self, file_paths: list):
        from ...tools.neo import get_number_of_electrodes, get_number_of_segments

        super().__init__(file_paths=file_paths)

        self.readers_list = list()
        for f in file_paths:
            self.readers_list.append(self.Extractor(filename=f))

        self.subset_channels = None
        self.n_segments = get_number_of_segments(neo_reader=self.readers_list[0], block=0)
        self.n_channels = get_number_of_electrodes(neo_reader=self.readers_list[0])

    def get_metadata_schema(self):

        metadata_schema = super().get_metadata_schema()
        if DandiIcephysMetadata:
            metadata_schema["properties"]["ndx-dandi-icephys"] = get_schema_from_hdmf_class(DandiIcephysMetadata)
        metadata_schema["properties"]["Icephys"] = get_metadata_schema_for_icephys()
        return metadata_schema

    def get_metadata(self):
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

    def run_conversion(
        self,
        nwbfile: NWBFile = None,
        nwbfile_path: OptionalFilePathType = None,
        metadata: dict = None,
        overwrite: bool = False,
        icephys_experiment_type: Optional[str] = None,
        skip_electrodes: Tuple[int] = (),
        # TODO: to be removed
        save_path: OptionalFilePathType = None,  # pragma: no cover
    ):
        """
        Primary function for converting raw (unprocessed) intracellular data to the NWB standard.

        Parameters
        ----------
        nwbfile: NWBFile
            nwb file to which the recording information is to be added
        nwbfile_path: FilePathType
            Path for where to write or load (if overwrite=False) the NWBFile.
            If specified, the context will always write to this location.
        metadata: dict
            metadata info for constructing the nwb file (optional).
        overwrite: bool
            Whether or not to overwrite the NWBFile if one exists at the nwbfile_path.
        icephys_experiment_type: str (optional)
            Type of Icephys experiment. Allowed types are: 'voltage_clamp', 'current_clamp',
                and 'izero' (all current and amplifier settings turned off).
            If no value is passed, 'voltage_clamp' is used as default.
        skip_electrodes: tuple, optional
            Electrode IDs to skip. Defaults to ().
        """
        from ...tools.neo import write_neo_to_nwb

        if nwbfile is None:
            nwbfile = make_nwbfile_from_metadata(metadata)

        # TODO on or after August 1st, 2022, remove argument and deprecation warnings
        if save_path is not None:  # pragma: no cover
            will_be_removed_str = "will be removed on or after October 1st, 2022. Please use 'nwbfile_path' instead."
            if nwbfile_path is not None:
                if save_path == nwbfile_path:
                    warn(
                        "Passed both 'save_path' and 'nwbfile_path', but both are equivalent! "
                        f"'save_path' {will_be_removed_str}",
                        DeprecationWarning,
                    )
                else:
                    warn(
                        "Passed both 'save_path' and 'nwbfile_path' - using only the 'nwbfile_path'! "
                        f"'save_path' {will_be_removed_str}",
                        DeprecationWarning,
                    )
            else:
                warn(
                    f"The keyword argument 'save_path' to 'spikeinterface.write_recording' {will_be_removed_str}",
                    DeprecationWarning,
                )
                nwbfile_path = save_path

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
