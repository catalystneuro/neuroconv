from ... import MiniscopeBehaviorInterface, MiniscopeImagingInterface
from ....nwbconverter import ConverterPipe
from ....utils import FolderPathType


class MiniscopeConverterPipe(ConverterPipe):
    """Primary conversion class for handling Miniscope data streams."""

    def __init__(
        self,
        folder_path: FolderPathType,
        verbose: bool = True,
    ):
        """
        Initializes the data interfaces for the Miniscope recording and behavioral data stream.

        The main Miniscope folder is expected to contain both data streams organized as follows:

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
        verbose : bool, default: True
            Controls verbosity.
        """

        data_interfaces = dict(
            Miniscope=MiniscopeImagingInterface(folder_path=folder_path),
            BehavCam=MiniscopeBehaviorInterface(folder_path=folder_path),
        )
        super().__init__(data_interfaces=data_interfaces, verbose=verbose)
