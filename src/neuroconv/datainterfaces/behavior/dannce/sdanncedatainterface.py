from pathlib import Path

from pydantic import FilePath, validate_call

from .danncedatainterface import DANNCEInterface
from ....utils import DeepDict


class SDANNCEInterface(DANNCEInterface):
    """Data interface for social-DANNCE (sDANNCE) multi-animal 3D pose estimation datasets."""

    display_name = "sDANNCE"
    keywords = ("sDANNCE", "social DANNCE", "3D pose estimation", "behavior", "pose estimation")
    associated_suffixes = (".mat",)
    info = "Interface for social-DANNCE (sDANNCE) 3D pose estimation output data."

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        animal_index: int,
        frametimes_file_path: FilePath | None = None,
        video_file_path: FilePath | None = None,
        sampling_rate: float | None = None,
        landmark_names: list[str] | None = None,
        subject_name: str = "ind1",
        pose_estimation_metadata_key: str = "PoseEstimationSDANNCE",
        verbose: bool = False,
    ):
        """
        Interface for writing sDANNCE 3D pose estimation output files to NWB.

        sDANNCE (social DANNCE) produces multi-animal predictions in a single ``.mat`` file.
        One instance of this interface writes a single animal — construct one instance per
        animal, using ``animal_index`` to select which animal to write.

        Parameters
        ----------
        file_path : FilePath
            Path to the sDANNCE prediction .mat file (e.g., save_data_AVG.mat).
        animal_index : int
            Index of the animal to write, selecting along the animal axis of the 4D ``pred``
            array (shape ``(n_frames, n_animals, 3, n_landmarks)``).
        frametimes_file_path : FilePath, optional
            See :class:`DANNCEInterface`.
        video_file_path : FilePath, optional
            See :class:`DANNCEInterface`.
        sampling_rate : float, optional
            See :class:`DANNCEInterface`.
        landmark_names : list of str, optional
            See :class:`DANNCEInterface`.
        subject_name : str, default: "ind1"
            The subject name used for linking the skeleton to the NWB subject.
        pose_estimation_metadata_key : str, default: "PoseEstimationSDANNCE"
            Controls where in the metadata the pose estimation data is stored and the name of the
            PoseEstimation container in the NWB file.
        verbose : bool, default: False
            Controls verbosity of the conversion process.
        """
        self._animal_index = animal_index
        super().__init__(
            file_path=file_path,
            frametimes_file_path=frametimes_file_path,
            video_file_path=video_file_path,
            sampling_rate=sampling_rate,
            landmark_names=landmark_names,
            subject_name=subject_name,
            pose_estimation_metadata_key=pose_estimation_metadata_key,
            verbose=verbose,
        )

    def _load_dannce_data(self, file_path: Path) -> None:
        """Load the sDANNCE .mat prediction file and slice out ``animal_index``."""
        super()._load_dannce_data(file_path)

        if self._pred.ndim != 4 or self._p_max.ndim != 3:
            raise ValueError(
                "SDANNCEInterface expects 4D 'pred' and 3D 'p_max' (sDANNCE multi-animal output). "
                "For single-animal DANNCE output, use DANNCEInterface."
            )

        n_animals = self._pred.shape[1]
        if not 0 <= self._animal_index < n_animals:
            raise IndexError(f"animal_index {self._animal_index} is out of range for a file with {n_animals} animals.")

        self._pred = self._pred[:, self._animal_index, :, :]
        self._p_max = self._p_max[:, self._animal_index, :]

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()

        container = metadata["PoseEstimation"]["PoseEstimationContainers"][self.pose_estimation_metadata_key]
        container["description"] = "3D keypoint coordinates estimated using sDANNCE (social DANNCE)."
        container["source_software"] = "sDANNCE"
        container["scorer"] = "sDANNCE"

        device_metadata_key = container["devices"][0]
        device = metadata["PoseEstimation"]["Devices"][device_metadata_key]
        device["description"] = "Multi-camera system used for 3D pose estimation with sDANNCE."

        return metadata
