from typing import Optional

from pydantic import DirectoryPath, validate_call
from pynwb import NWBFile

from ... import MiniscopeBehaviorInterface, MiniscopeImagingInterface
from ....nwbconverter import NWBConverter
from ....tools.nwb_helpers import make_or_load_nwbfile
from ....utils import get_json_schema_from_method_signature


class MiniscopeConverter(NWBConverter):
    """Primary conversion class for handling Miniscope data streams."""

    display_name = "Miniscope Imaging and Video"
    keywords = MiniscopeImagingInterface.keywords + MiniscopeBehaviorInterface.keywords
    associated_suffixes = MiniscopeImagingInterface.associated_suffixes + MiniscopeBehaviorInterface.associated_suffixes
    info = "Converter for handling both imaging and video recordings from Miniscope."

    @classmethod
    def get_source_schema(cls):
        source_schema = get_json_schema_from_method_signature(cls)
        source_schema["properties"]["folder_path"]["description"] = "The path to the main Miniscope folder."
        return source_schema

    @validate_call
    def __init__(self, folder_path: DirectoryPath, verbose: bool = False):
        """
        Initializes the data interfaces for the Miniscope recording and behavioral data stream.

        The main Miniscope folder is expected to contain both data streams organized as follows::

            C6-J588_Disc5/ (main folder)
            ├── 15_03_28/ (subfolder corresponding to the recording time)
            │   ├── Miniscope/ (subfolder containing the microscope video stream)
            │   │   ├── 0.avi (microscope video)
            │   │   ├── metaData.json (metadata for the microscope device)
            │   │   └── timeStamps.csv (timing of this video stream)
            │   ├── BehavCam_2/ (subfolder containing the behavioral video stream)
            │   │   ├── 0.avi (bevavioral video)
            │   │   ├── metaData.json (metadata for the behavioral camera)
            │   │   └── timeStamps.csv (timing of this video stream)
            │   └── metaData.json (metadata for the recording, such as the start time)
            ├── 15_06_28/
            │   ├── Miniscope/
            │   ├── BehavCam_2/
            │   └── metaData.json
            └── 15_12_28/

        Parameters
        ----------
        folder_path : FolderPathType
            The path to the main Miniscope folder.
        verbose : bool, default: False
            Controls verbosity.
        """
        self.verbose = verbose
        self.data_interface_objects = dict(
            MiniscopeImaging=MiniscopeImagingInterface(folder_path=folder_path),
            MiniscopeBehavCam=MiniscopeBehaviorInterface(folder_path=folder_path),
        )

    def get_conversion_options_schema(self) -> dict:
        """
        Get the schema for the conversion options.

        Returns
        -------
        dict
            The schema dictionary containing conversion options for the Miniscope interface.
        """
        return self.data_interface_objects["MiniscopeImaging"].get_conversion_options_schema()

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata,
        stub_test: bool = False,
        stub_frames: int = 100,
    ):
        """
        Add Miniscope imaging and behavioral camera data to the specified NWBFile.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWBFile object to which the imaging and behavioral data will be added.
        metadata : dict
            Metadata dictionary containing information about the imaging and behavioral recordings.
        stub_test : bool, optional
            If True, only a subset of the data (defined by `stub_frames`) will be added for testing purposes,
            by default False.
        stub_frames : int, optional
            The number of frames to include in the subset if `stub_test` is True, by default 100.
        """
        self.data_interface_objects["MiniscopeImaging"].add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata,
            stub_test=stub_test,
            stub_frames=stub_frames,
        )
        self.data_interface_objects["MiniscopeBehavCam"].add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata,
        )

    def run_conversion(
        self,
        nwbfile_path: Optional[str] = None,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        overwrite: bool = False,
        stub_test: bool = False,
        stub_frames: int = 100,
    ) -> None:
        """
        Run the NWB conversion process for the instantiated data interfaces.

        Parameters
        ----------
        nwbfile_path : str, optional
            Path where the NWBFile will be written. If None, the file is handled in-memory.
        nwbfile : NWBFile, optional
            An in-memory NWBFile object to be written to the file. If None, a new NWBFile is created.
        metadata : dict, optional
            Metadata dictionary with information to create the NWBFile. If None, metadata is auto-generated.
        overwrite : bool, optional
            If True, overwrites the existing NWBFile at `nwbfile_path`. If False (default), data is appended.
        stub_test : bool, optional
            If True, only a subset of the data (up to `stub_frames`) is written for testing purposes,
            by default False.
        stub_frames : int, optional
            The number of frames to include in the subset if `stub_test` is True, by default 100.
        """
        if metadata is None:
            metadata = self.get_metadata()

        self.validate_metadata(metadata=metadata)

        self.temporally_align_data_interfaces()

        with make_or_load_nwbfile(
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            metadata=metadata,
            overwrite=overwrite,
            verbose=self.verbose,
        ) as nwbfile_out:
            self.add_to_nwbfile(nwbfile=nwbfile_out, metadata=metadata, stub_test=stub_test, stub_frames=stub_frames)
