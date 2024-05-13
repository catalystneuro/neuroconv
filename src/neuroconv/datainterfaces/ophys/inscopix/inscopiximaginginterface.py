from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils import FilePathType


class InscopixImagingInterface(BaseImagingExtractorInterface):
    """Interface for Inscopix imaging data."""

    display_name = "Inscopix Imaging"
    associated_suffixes = (".isxd",)
    info = "Interface for Inscopix imaging data."

    def __init__(self, file_path: FilePathType, verbose: bool = True):
        """

        Parameters
        ----------
        file_path : FilePathType
            Path to .h5 or .hdf5 file.
        verbose : bool, default: True
        """
        super().__init__(file_path=file_path, verbose=verbose)
