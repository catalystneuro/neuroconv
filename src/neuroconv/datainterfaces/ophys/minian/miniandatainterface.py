import warnings
from copy import deepcopy
from typing import Optional

from numpy import ndarray
from pydantic import DirectoryPath, FilePath, validate_call
from pynwb import NWBFile

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface
from ....utils import DeepDict


class MinianSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for MinianSegmentationExtractor.

    Minian is a calcium imaging analysis pipeline that outputs segmented ROIs and their temporal dynamics
    as .zarr files. The standard Minian output includes:

    - Spatial footprints (A.zarr): ROI masks
    - Temporal components (C.zarr): Denoised fluorescence traces
    - Background components (b.zarr, f.zarr): Background masks and temporal dynamics
    - Deconvolved traces (S.zarr): Spike inference results
    - Baseline fluorescence (b0.zarr): Baseline estimates

    **Sampling Frequency and Timestamps:**
    Minian does not natively store sampling frequency information in its output. For NWB conversion,
    either a sampling frequency or timestamps are required. This interface supports:

    1. Providing sampling_frequency directly (recommended for regular sampling)
    2. Using a timeStamps.csv file (often copied from Miniscope outputs)
    3. If neither is provided, the interface will raise an informative error

    The timeStamps.csv file should contain 'Frame Number' and 'Time Stamp (ms)' columns and is
    typically placed in the same folder as the .zarr outputs."""

    display_name = "Minian Segmentation"
    associated_suffixes = (".zarr",)
    info = "Interface for Minian segmentation data."

    @classmethod
    def get_extractor_class(cls):
        from roiextractors import MinianSegmentationExtractor

        return MinianSegmentationExtractor

    def _initialize_extractor(self, interface_kwargs):
        self.extractor_kwargs = deepcopy(interface_kwargs)
        self.extractor_kwargs.pop("verbose", None)  # Remove interface params

        extractor_class = self.get_extractor_class()
        extractor_instance = extractor_class(**self.extractor_kwargs)
        return extractor_instance

    @classmethod
    def get_source_schema(cls) -> dict:
        source_metadata = super().get_source_schema()
        source_metadata["properties"]["folder_path"]["description"] = "Path to .zarr output."
        source_metadata["properties"]["sampling_frequency"] = {
            "type": "number",
            "description": "The sampling frequency in Hz. If not provided, will attempt to derive from timeStamps.csv.",
        }
        source_metadata["properties"]["timestamps_path"] = {
            "type": "string",
            "description": "Path to the timeStamps.csv file. If not provided, assumes default location at folder_path/timeStamps.csv.",
        }
        return source_metadata

    @validate_call
    def __init__(
        self,
        folder_path: DirectoryPath,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        sampling_frequency: Optional[float] = None,
        timestamps_path: Optional[FilePath] = None,
        verbose: bool = False,
    ):
        """

        Parameters
        ----------
        folder_path : str or Path
            Path to .zarr path.
        sampling_frequency : float, optional
            The sampling frequency in Hz. If not provided, will attempt to derive from timeStamps.csv.
        timestamps_path : str or Path, optional
            Path to the timeStamps.csv file. If not provided, assumes default location at folder_path/timeStamps.csv.
        verbose : bool, default False
            Whether to print progress
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "sampling_frequency",
                "timestamps_path",
                "verbose",
            ]
            num_positional_args_before_args = 1  # folder_path
            if len(args) > len(parameter_names):
                raise TypeError(
                    f"__init__() takes at most {len(parameter_names) + num_positional_args_before_args + 1} positional arguments but "
                    f"{len(args) + num_positional_args_before_args + 1} were given. "
                    "Note: Positional arguments are deprecated and will be removed on or after August 2026. "
                    "Please use keyword arguments."
                )
            positional_values = dict(zip(parameter_names, args))
            passed_as_positional = list(positional_values.keys())
            warnings.warn(
                f"Passing arguments positionally to MinianSegmentationInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            sampling_frequency = positional_values.get("sampling_frequency", sampling_frequency)
            timestamps_path = positional_values.get("timestamps_path", timestamps_path)
            verbose = positional_values.get("verbose", verbose)

        super().__init__(
            folder_path=folder_path, sampling_frequency=sampling_frequency, timestamps_path=timestamps_path
        )
        self.verbose = verbose

    def get_original_timestamps(self, start_sample: Optional[int] = None, end_sample: Optional[int] = None) -> ndarray:
        return self.segmentation_extractor.get_native_timestamps(start_sample=start_sample, end_sample=end_sample)

    def get_timestamps(self, start_sample: Optional[int] = None, end_sample: Optional[int] = None) -> ndarray:
        return self.segmentation_extractor.get_timestamps(start_sample=start_sample, end_sample=end_sample)

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: Optional[dict] = None,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        stub_test: bool = False,
        stub_frames: int = 100,
        include_background_segmentation: bool = True,
        include_roi_centroids: bool = True,
        include_roi_acceptance: bool = False,
        mask_type: Optional[str] = "image",  # Literal["image", "pixel", "voxel"]
        plane_segmentation_name: Optional[str] = None,
        iterator_options: Optional[dict] = None,
    ):
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "stub_test",
                "stub_frames",
                "include_background_segmentation",
                "include_roi_centroids",
                "include_roi_acceptance",
                "mask_type",
                "plane_segmentation_name",
                "iterator_options",
            ]
            num_positional_args_before_args = 2  # nwbfile, metadata
            if len(args) > len(parameter_names):
                raise TypeError(
                    f"add_to_nwbfile() takes at most {len(parameter_names) + num_positional_args_before_args} positional arguments but "
                    f"{len(args) + num_positional_args_before_args} were given. "
                    "Note: Positional arguments are deprecated and will be removed on or after August 2026. "
                    "Please use keyword arguments."
                )
            positional_values = dict(zip(parameter_names, args))
            passed_as_positional = list(positional_values.keys())
            warnings.warn(
                f"Passing arguments positionally to MinianSegmentationInterface.add_to_nwbfile() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            stub_test = positional_values.get("stub_test", stub_test)
            stub_frames = positional_values.get("stub_frames", stub_frames)
            include_background_segmentation = positional_values.get(
                "include_background_segmentation", include_background_segmentation
            )
            include_roi_centroids = positional_values.get("include_roi_centroids", include_roi_centroids)
            include_roi_acceptance = positional_values.get("include_roi_acceptance", include_roi_acceptance)
            mask_type = positional_values.get("mask_type", mask_type)
            plane_segmentation_name = positional_values.get("plane_segmentation_name", plane_segmentation_name)
            iterator_options = positional_values.get("iterator_options", iterator_options)

        super().add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata,
            stub_test=stub_test,
            stub_frames=stub_frames,
            include_background_segmentation=include_background_segmentation,
            include_roi_centroids=include_roi_centroids,
            include_roi_acceptance=include_roi_acceptance,
            mask_type=mask_type,
            plane_segmentation_name=plane_segmentation_name,
            iterator_options=iterator_options,
        )

    def get_metadata(self) -> DeepDict:
        """
        Get metadata for the Minian segmentation data.

        Returns
        -------
        DeepDict
            The metadata dictionary containing imaging metadata from the Minian output.
            This includes:
            - session_id: Unique identifier for the session.
            - subject_id: Unique identifier for the subject.
        """
        metadata = super().get_metadata()
        metadata["NWBFile"]["session_id"] = self.segmentation_extractor._get_session_id()
        # metadata["Subject"]["subject_id"] = self.segmentation_extractor._get_subject_id()
        return metadata
