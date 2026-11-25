"""DataInterface for B-SOiD behavioral segmentation output."""

from pathlib import Path

import numpy as np
from pydantic import FilePath, validate_call

from ._bsoid_reader import _get_sampling_frequency_from_file_name, _read_labels_and_frame_indices
from ..basebehavioralsegmentationinterface import BaseBehavioralSegmentationInterface
from ....utils import DeepDict


class BSOiDInterface(BaseBehavioralSegmentationInterface):
    """DataInterface for the per-frame labels of B-SOiD (Behavioral Segmentation of Open-field In DeepLabCut).

    Reads the labels file B-SOiD writes for one predicted pose file, ``labels_pose`` from the Streamlit app
    (version 1.4 and later) or ``bsoid_labels`` from the ``bsoid_umap`` command-line pipeline (version 1.3), and
    writes its behavior groups as an ``ndx-ethogram`` ``EthogramBouts`` table with its ``Ethogram`` catalogue.
    The ``.mat`` files of the MATLAB code (versions 1.0 to 1.2) are not read: that code does not save its labels, so
    a ``.mat`` holds whatever variables its user saved, under names they chose.

    Notes
    -----
    - **The layout of the file follows the pose input.** The labels file is the pose table B-SOiD read with a
      ``B-SOiD labels`` column prepended. From a DeepLabCut CSV it keeps the ``bodyparts`` and ``coords`` header
      rows as data rows; from a DeepLabCut or SLEAP ``.h5`` it has no header rows.
    - **The app of version 1.5 and later writes its labels two rows early on DeepLabCut CSV input.** It labels the
      two header rows with the labels of the first two frames, so every label sits two rows before its frame. The
      interface recognizes this by the labelled header rows, which bsoid_umap and the app of version 1.4 leave blank,
      and puts every label back on its frame.
    - **Times come from the pose frame index.** The file carries the frame index of the pose it was made from, in
      the ``scorer`` column for DeepLabCut CSV input and in the unnamed index otherwise. It need not start at 0 when
      the pose was trimmed, and dividing it by the frame rate gives the same times ``DeepLabCutInterface`` writes for
      that pose.
    - **The group ids carry no meaning outside the model that assigned them.** The catalogue enumerates the groups
      present in this file, since the file does not record how many the model has.
    - **The pose in the file is not written.** Add it from the pose file with ``DeepLabCutInterface`` or
      ``SLEAPInterface`` and link it through metadata.
    """

    display_name = "B-SOiD"
    keywords = ("B-SOiD", "behavioral segmentation", "pose segmentation", "unsupervised behavior")
    associated_suffixes = (".csv",)
    info = "Interface for the behavior groups of B-SOiD (Behavioral Segmentation of Open-field In DeepLabCut)."

    source_software = "B-SOiD"
    behavior_definition = (
        "B-SOiD behavior group; the id is specific to the model that assigned it and carries no meaning outside it."
    )

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = (
            "Path to the B-SOiD labels file of one recording: `labels_pose` from the app or `bsoid_labels` from "
            "bsoid_umap."
        )
        return source_schema

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        sampling_frequency_hz: float | None = None,
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """Initialize BSOiDInterface.

        Parameters
        ----------
        file_path : FilePath
            Path to the B-SOiD labels file of one recording: the ``labels_pose`` file the app writes into the
            ``BSOID`` folder next to each pose file, or the ``bsoid_labels`` file of bsoid_umap.
        sampling_frequency_hz : float, optional
            Frame rate of the pose, in Hz. B-SOiD writes it into the file name (``labels_pose_60Hz...``), where it
            is read from by default. Required when the file was renamed and the name no longer carries it.
        metadata_key : str, optional
            Key of this interface's entries in ``metadata["Behavior"]["Ethograms"]`` and
            ``metadata["Behavior"]["EthogramBouts"]``, and of its object in ``temporal_alignment``. Defaults to
            ``"bsoid"``. Change it, and the names in the two entries, when writing two recordings into one NWB
            file.
        verbose : bool, default False
            Controls verbosity of the conversion process.
        """
        if Path(file_path).suffix == ".mat":
            raise ValueError(
                f"'{Path(file_path).name}' is a MATLAB file. BSOiDInterface reads the CSV labels files of the Python "
                "versions of B-SOiD (1.3 and later), not the output of its MATLAB code (versions 1.0 to 1.2). If you "
                "need it, please open an issue at https://github.com/catalystneuro/neuroconv/issues"
            )
        if sampling_frequency_hz is None:
            sampling_frequency_hz = _get_sampling_frequency_from_file_name(file_path)
            if sampling_frequency_hz is None:
                raise ValueError(
                    f"The name of '{Path(file_path).name}' does not carry the frame rate B-SOiD writes into it "
                    "(`labels_pose_<fps>Hz` or `bsoid_labels_<fps>Hz`), so pass sampling_frequency_hz."
                )

        self.metadata_key = metadata_key or "bsoid"
        self._sampling_frequency_hz = sampling_frequency_hz
        self._labels, self._frame_indices = _read_labels_and_frame_indices(file_path)

        super().__init__(file_path=file_path, verbose=verbose)

    def _get_labels(self) -> np.ndarray:
        return self._labels

    def _get_native_times(self) -> np.ndarray:
        return self._frame_indices / self._sampling_frequency_hz

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()

        metadata["Behavior"]["Ethograms"][self.metadata_key] = dict(
            name="BSOiDEthogram",
            description="B-SOiD behavior group catalogue: one row per group present in this recording.",
        )
        # The links to the pose and the video (source_pose_metadata_key, source_video_metadata_key) are absent
        # because the labels file evidences neither.
        metadata["Behavior"]["EthogramBouts"][self.metadata_key] = dict(
            name="BSOiDEthogramBouts",
            description=(
                f"B-SOiD behavior groups of '{Path(self.source_data['file_path']).name}' as run-length-encoded bouts."
            ),
            labeling_method="automated",
            ethogram_metadata_key=self.metadata_key,
        )

        return metadata
