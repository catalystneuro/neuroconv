from typing import Literal, Optional

from pydantic import FilePath, validate_call

from ..baseimagingextractorinterface import BaseImagingExtractorInterface


class TiffImagingInterface(BaseImagingExtractorInterface):
    """Interface for multi-page TIFF files."""

    display_name = "TIFF Imaging"
    associated_suffixes = (".tif", ".tiff")
    info = "Interface for multi-page TIFF files."

    @classmethod
    def get_source_schema(cls) -> dict:
        """
        Get the source schema for the TIFF imaging interface.

        Returns
        -------
        dict
            The JSON schema for the TIFF imaging interface source data,
            containing file path and other configuration parameters.
        """
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to Tiff file."
        return source_schema

    @classmethod
    def get_extractor_class(cls):
        """
        Get the extractor class for the TIFF imaging interface.

        Returns
        -------
        class
            MultiTIFFMultiPageExtractor for handling TIFF files.
        """
        from roiextractors import MultiTIFFMultiPageExtractor

        return MultiTIFFMultiPageExtractor

    @validate_call
    def __init__(
        self,
        file_path: Optional[FilePath] = None,
        file_paths: Optional[list[FilePath]] = None,
        sampling_frequency: float = None,
        *,
        dimension_order: str = "ZCT",
        num_channels: int = 1,
        channel_name: Optional[str] = None,
        num_planes: int = 1,
        verbose: bool = False,
        photon_series_type: Literal["OnePhotonSeries", "TwoPhotonSeries"] = "TwoPhotonSeries",
    ):
        """
        Initialize reading of TIFF file(s).

        Parameters
        ----------
        file_path : FilePath, optional
                Use `file_paths` instead. Will be removed in April 2026 or later.
            Path to a single TIFF file. Either file_path or file_paths must be specified.
        file_paths : list[FilePath], optional
            List of paths to TIFF files. Either file_path or file_paths must be specified.
        sampling_frequency : float
            The sampling frequency of the imaging data in Hz.
        dimension_order : str, default: "ZCT"
            Order of dimensions in the TIFF file. For example, "ZCT" means frames are organized as Z-planes, channels, then time.
        num_channels : int, default: 1
            Number of color channels in the TIFF file. Channel names are automatically generated as
            string representations of channel indices: "0", "1", "2", etc. For example, if num_channels=3,
            the available channels will be ["0", "1", "2"].
        channel_name : str, optional
            Name of the channel to extract. Must be a string representation of a channel index
            (e.g., "0", "1", "2", etc.) corresponding to one of the num_channels.
            If None and num_channels is 1, defaults to "0".
            If None and num_channels > 1, an error will be raised.
        num_planes : int, default: 1
            Number of z-planes per volume.
        verbose : bool, default: False
            Whether to print verbose output.
        photon_series_type : {'OnePhotonSeries', 'TwoPhotonSeries'}, default: "TwoPhotonSeries"
            Type of photon series for NWB conversion.

        Notes
        -----
        TIFF Frame Terminology
        ----------------------
        In this documentation, we use "frame" to refer to each acquired image stored in the TIFF file.
        This is equivalent to:

        - **IFD (Image File Directory)** in the TIFF specification - the data structure containing
          metadata and image data for one image
        - **Page** in common TIFF libraries like tifffile - a single image within a multi-page TIFF

        Each frame represents one 2D image acquisition at a specific combination of depth (Z), channel (C),
        and timepoint (T). The dimension order determines the sequence in which frames are acquired and
        stored in the file.

        Dimension Order Notes
        ---------------------
        This class follows a subset of the OME-TIFF dimension order specification, focusing on
        the Z (depth), C (channel), and T dimensions. The XY spatial dimensions are
        assumed to be the first two dimensions of each frame and are not included in the
        dimension_order parameter.

        While we use 'T' for compatibility with the OME-TIFF standard, we emphasize that its
        meaning varies significantly based on position:

        - When T is first (TCZ, TZC): Represents oversampling - multiple samples acquired at
          each depth or channel:

          - TCZ: T samples per channel at each depth position
          - TZC: T samples per depth position for each channel

        - When T is middle (ZTC, CTZ): Represents repetitions - repeated acquisitions of
          sub-structures before varying the outer dimension:

          - ZTC: T repetitions of each Z-stack before switching channels
          - CTZ: T repetitions of the full channel set at each depth

        - When T is last (ZCT, CZT): Represents acquisition cycles - complete acquisitions
          of the entire multi-channel, multi-plane dataset:

          - ZCT: T complete multi-channel volumes where the depth is varied first
          - CZT: T complete multi-channel volumes where the channel is varied first

        For more information on OME-TIFF dimension order, see:
        https://docs.openmicroscopy.org/ome-model/5.6.3/ome-tiff/specification.html

        Acquisition Patterns
        --------------------
        ZCT (Depth → Channel → Acquisition Cycles)
            Acquire a complete Z-stack for the first channel, then switch to the next channel
            and acquire its full Z-stack. After all channels are acquired, this constitutes
            one acquisition cycle. Repeat for T acquisition cycles.

        ZTC (Depth → Repetitions → Channel)
            Acquire full Z-stacks repeated T times for a single channel, then switch to
            the next channel and acquired another T repetitions of the full Z-stack for that
            channel. Repeat the same process for all channels.

        CZT (Channel → Depth → Acquisition Cycles)
            At the first depth position, acquire all channels sequentially. Move to the next
            depth and acquire all channels again. After completing all depths, one acquisition
            cycle is complete. Repeat for T acquisition cycles.

        CTZ (Channel → Repetitions → Depth)
            At a fixed depth position, acquire all channels, then repeat this channel
            acquisition T times. Then move to the next depth position and repeat the
            pattern of T repetitions of all channels.

        TCZ (Oversampling → Channel → Depth)
            At a fixed depth position, acquire T samples for the first channel,
            then acquire T samples for the next channel. After oversampling all channels
            at this depth, move to the next depth position and repeat.

        TZC (Oversampling → Depth → Channel)
            For a fixed channel, acquire T samples at the first depth, then T samples at
            the second depth, continuing through all depths. Switch to the next channel
            and repeat the entire oversampling pattern across depths.

        Special Cases
        -------------
        When data has only a single channel (num_channels=1):

            ZCT, ZTC, CZT → ZT: Volumetric time series (complete volumes acquired sequentially)

            CTZ, TCZ, TZC → TZ: Plane-by-plane time series (T samples at each depth before moving to next)

        When data is planar (num_planes=1):

            ZCT, CZT, CTZ → CT: Channel-first acquisition patterns (one full channel sweep after another)

            ZTC, TCZ, TZC → TC: Time-first acquisition patterns (full data for one channel and then the next)

        When data is both single-channel AND planar:

            All dimension orders → T: Simple planar time series (all orderings equivalent)
        """
        import warnings

        # Handle both file_path and file_paths
        if file_path is not None and file_paths is not None:
            raise ValueError("Cannot specify both 'file_path' and 'file_paths'. Please use one or the other.")

        if file_path is not None:
            warnings.warn(
                "The 'file_path' parameter is deprecated and will be removed in April 2026 or later. "
                "Use 'file_paths' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            file_paths = [file_path]

        if file_paths is None:
            raise ValueError("Either 'file_path' or 'file_paths' must be specified.")

        super().__init__(
            file_paths=file_paths,
            sampling_frequency=sampling_frequency,
            dimension_order=dimension_order,
            num_channels=num_channels,
            channel_name=channel_name,
            num_planes=num_planes,
            verbose=verbose,
            photon_series_type=photon_series_type,
        )
