from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils import ArrayType, FilePathType


class Hdf5ImagingInterface(BaseImagingExtractorInterface):
    """Interface for HDF5 imaging data."""

    display_name = "HDF5 Imaging"
    associated_suffixes = (".h5", ".hdf5")
    info = "Interface for HDF5 imaging data."

    def __init__(
        self,
        file_path: FilePathType,
        mov_field: str = "mov",
        sampling_frequency: float = None,
        start_time: float = None,
        metadata: dict = None,
        channel_names: ArrayType = None,
        verbose: bool = True,
    ):
        """

        Parameters
        ----------
        file_path : FilePathType
            Path to .h5 or .hdf5 file.
        mov_field : str, default: 'mov'
        sampling_frequency : float, optional
        start_time : float, optional
        metadata : dict, optional
        channel_names : list of str, optional
        verbose : bool, default: True
        """
        super().__init__(
            file_path=file_path,
            mov_field=mov_field,
            sampling_frequency=sampling_frequency,
            start_time=start_time,
            metadata=metadata,
            channel_names=channel_names,
            verbose=verbose,
        )
