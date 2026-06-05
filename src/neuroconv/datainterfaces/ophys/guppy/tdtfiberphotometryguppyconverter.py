from typing import Literal

from pydantic import DirectoryPath, validate_call
from pynwb import NWBFile

from .guppydatainterface import GuppyInterface
from ..tdt_fp.tdtfiberphotometrydatainterface import TDTFiberPhotometryInterface
from ....nwbconverter import ConverterPipe


class TDTFiberPhotometryGuppyConverter(ConverterPipe):
    """Bundle raw TDT fiber photometry acquisition with GuPPy-derived processing outputs.

    Combines :class:`TDTFiberPhotometryInterface` (raw acquisition added to ``nwbfile.acquisition``
    via the ``ndx-fiber-photometry`` extension) with :class:`GuppyInterface` (derived traces,
    transient tables, and cross-correlations added to a ``fiber_photometry`` ProcessingModule).

    GuPPy and TDT share a single origin (recording start = ``session_start_time``): GuPPy emits
    timestamps in seconds since recording start, the same clock the raw TDT streams use. No
    cross-system re-alignment is therefore needed -- both interfaces write on the shared clock,
    rooted at ``nwbfile.session_start_time`` (taken from the TDT tank).
    """

    display_name = "TDT Fiber Photometry + GuPPy"
    keywords = TDTFiberPhotometryInterface.keywords + GuppyInterface.keywords
    associated_suffixes = TDTFiberPhotometryInterface.associated_suffixes + GuppyInterface.associated_suffixes
    info = "Converter that bundles raw TDT fiber photometry acquisition with GuPPy-derived processing outputs."

    @validate_call
    def __init__(
        self,
        tdt_folder_path: DirectoryPath,
        guppy_folder_path: DirectoryPath,
        *,
        verbose: bool = False,
    ):
        """Initialize the TDT + GuPPy converter.

        Parameters
        ----------
        tdt_folder_path : DirectoryPath
            Path to the TDT tank folder containing the raw acquisition files (Tbk, Tdx, tev,
            tin, tsq).
        guppy_folder_path : DirectoryPath
            Path to the GuPPy ``<session>_output_<N>`` folder containing ``storesList.csv``,
            the per-region derived ``.hdf5`` files, and the ``GuPPyParamtersUsed.json``
            provenance file (discovered automatically by :class:`GuppyInterface`).
        verbose : bool, optional
            Whether to print status messages, default = False.
        """
        tdt_interface = TDTFiberPhotometryInterface(folder_path=tdt_folder_path, verbose=verbose)
        guppy_interface = GuppyInterface(
            folder_path=guppy_folder_path,
            verbose=verbose,
        )
        super().__init__(
            data_interfaces={
                "TDTFiberPhotometry": tdt_interface,
                "Guppy": guppy_interface,
            },
            verbose=verbose,
        )

    def get_metadata(self):
        """Merge sub-interface metadata, with the TDT tank as the authoritative session start time."""
        metadata = super().get_metadata()
        tdt_metadata = self.data_interface_objects["TDTFiberPhotometry"].get_metadata()
        metadata["NWBFile"]["session_start_time"] = tdt_metadata["NWBFile"]["session_start_time"]
        # The TDT side adds a FiberPhotometry lab_meta_data object named "fiber_photometry";
        # rename the GuPPy ProcessingModule to avoid colliding with that name during NWB write.
        metadata["Ophys"]["Guppy"]["ProcessingModule"]["name"] = "guppy"
        return metadata

    def get_metadata_schema(self) -> dict:
        """Allow the ``Ophys`` block to carry both ``Guppy`` and ``FiberPhotometry`` sub-schemas."""
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ophys"]["additionalProperties"] = True
        return metadata_schema

    def get_conversion_options_schema(self) -> dict:
        """Expose top-level stub/window options alongside the per-interface schemas."""
        schema = super().get_conversion_options_schema()
        schema["properties"]["stub_test"] = {
            "type": "boolean",
            "default": False,
            "description": "If True, only a short stub of each trace is written.",
        }
        schema["properties"]["t1"] = {
            "type": "number",
            "default": 0.0,
            "description": "Start time (seconds) for the TDT acquisition window.",
        }
        schema["properties"]["t2"] = {
            "type": "number",
            "default": 0.0,
            "description": "End time (seconds) for the TDT acquisition window. 0 means end of recording.",
        }
        return schema

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        conversion_options: dict | None = None,
        stub_test: bool = False,
        t1: float = 0.0,
        t2: float = 0.0,
    ) -> None:
        """Add raw TDT and GuPPy-derived data to the provided NWBFile."""
        if metadata is None:
            metadata = self.get_metadata()

        conversion_options = conversion_options.copy() if conversion_options else {}
        tdt_options = {"stub_test": stub_test, "t1": t1, "t2": t2}
        tdt_options.update(conversion_options.pop("TDTFiberPhotometry", {}))
        guppy_options: dict = {"stub_test": stub_test}
        guppy_options.update(conversion_options.pop("Guppy", {}))
        merged_conversion_options = {
            "TDTFiberPhotometry": tdt_options,
            "Guppy": guppy_options,
        }
        merged_conversion_options.update(conversion_options)

        super().add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata,
            conversion_options=merged_conversion_options,
        )

    def run_conversion(
        self,
        nwbfile_path: str | None = None,
        nwbfile: NWBFile | None = None,
        metadata: dict | None = None,
        overwrite: bool = False,
        backend: Literal["hdf5", "zarr"] | None = None,
        backend_configuration=None,
        conversion_options: dict | None = None,
        append_on_disk_nwbfile: bool = False,
        stub_test: bool = False,
        t1: float = 0.0,
        t2: float = 0.0,
    ) -> None:
        """Run the NWB conversion for both TDT acquisition and GuPPy processing outputs."""
        conversion_options = conversion_options.copy() if conversion_options else {}
        tdt_options = {"stub_test": stub_test, "t1": t1, "t2": t2}
        tdt_options.update(conversion_options.pop("TDTFiberPhotometry", {}))
        guppy_options: dict = {"stub_test": stub_test}
        guppy_options.update(conversion_options.pop("Guppy", {}))
        merged_conversion_options = {
            "TDTFiberPhotometry": tdt_options,
            "Guppy": guppy_options,
        }
        merged_conversion_options.update(conversion_options)

        super().run_conversion(
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            metadata=metadata,
            overwrite=overwrite,
            backend=backend,
            backend_configuration=backend_configuration,
            conversion_options=merged_conversion_options,
            append_on_disk_nwbfile=append_on_disk_nwbfile,
        )
