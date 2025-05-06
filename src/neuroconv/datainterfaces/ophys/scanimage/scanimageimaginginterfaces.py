import datetime
import json
import warnings
from pathlib import Path
from typing import Optional

import numpy as np
from dateutil.parser import parse as dateparse
from pydantic import DirectoryPath, FilePath, validate_call

from ..baseimagingextractorinterface import BaseImagingExtractorInterface


class ScanImageImagingInterface(BaseImagingExtractorInterface):
    """Interface for reading TIFF files produced via ScanImage."""

    extractor = "ScanImageImagingExtractor"

    def __init__(
        self,
        file_path: FilePath,
        channel_name: Optional[str] = None,
        slice_sample: Optional[int] = None,
        plane_index: Optional[int] = None,
        file_paths: Optional[list[str]] = None,
        plane_name: str | None = None,
        fallback_sampling_frequency: float | None = None,
        verbose: bool = False,
    ):
        """
        Initialize the ScanImage Imaging Interface.

        Parameters
        ----------
        file_path : PathType
            Path to the TIFF file. If this is part of a multi-file series, this should be the first file.
        channel_name : str, optional
            Name of the channel to extract. If None and multiple channels are available, the first channel will be used.
        file_paths : List[PathType], optional
            List of file paths to use. If provided, this overrides the automatic
            file detection heuristics. Use this if automatic detection does not work correctly and you know
            exactly which files should be included.  The file paths should be provided in an order that
            reflects the temporal order of the frames in the dataset.
        """

        header_version = self.get_scanimage_version(file_path=file_path)
        if header_version not in [3, 4, 5]:
            raise ValueError(
                f"Unsupported ScanImage version {header_version}. Supported versions are 3, 4, and 5."
                f"Most likely this is a legacy version, use ScanImageLegacyImagingInterface instead."
            )

        if plane_name is not None:

            warnings.warn(
                "The `plane_name` argument is deprecated and will be removed in or after November 2025. Use `plane_index` instead."
            )
            plane_index = int(plane_name)

        if fallback_sampling_frequency is not None:
            warnings.warn(
                "The `fallback_sampling_frequency` argument is deprecated and will be removed in or after November 2025"
            )

        self.channel_name = channel_name
        super().__init__(
            file_path=file_path,
            channel_name=channel_name,
            file_paths=file_paths,
            plane_index=plane_index,
            slice_sample=slice_sample,
        )

    def get_metadata(self):
        """
        Get metadata for the ScanImage imaging data.

        Returns
        -------
        DeepDict
            The metadata dictionary containing imaging metadata from the ScanImage files.
        """
        metadata = super().get_metadata()

        session_start_time = self._get_session_start_time()
        if session_start_time:
            metadata["NWBFile"]["session_start_time"] = session_start_time

        # Extract ScanImage-specific metadata
        if hasattr(self.imaging_extractor, "_general_metadata"):
            # Add general metadata to a custom field
            scanimage_metadata = self.imaging_extractor._general_metadata

            # Update device information
            device_name = "Microscope"
            metadata["Ophys"]["Device"][0].update(name=device_name, description=f"Microscope controlled by ScanImage")

            # Update imaging plane metadata
            imaging_plane_metadata = metadata["Ophys"]["ImagingPlane"][0]
            imaging_plane_metadata.update(
                device=device_name,
                imaging_rate=self.imaging_extractor.get_sampling_frequency(),
                description="Imaging plane from ScanImage acquisition",
            )

            # Update photon series metadata
            photon_series_key = self.photon_series_type  # "TwoPhotonSeries" or "OnePhotonSeries"
            photon_series_metadata = metadata["Ophys"][photon_series_key][0]

            channel_string = self.channel_name.replace(" ", "").capitalize()
            photon_series_name = f"{photon_series_key}{channel_string}"

            photon_series_metadata["name"] = photon_series_name
            photon_series_metadata["description"] = f"Imaging data acquired using ScanImage for {self.channel_name}"

            # Add additional metadata if available
            if "FrameData" in scanimage_metadata:
                frame_data = scanimage_metadata["FrameData"]

                # Calculate scan line rate from line period if available
                if "SI.hRoiManager.linePeriod" in frame_data:
                    scan_line_rate = 1 / float(frame_data["SI.hRoiManager.linePeriod"])
                    photon_series_metadata.update(scan_line_rate=scan_line_rate)
                elif "SI.hScan2D.scannerFrequency" in frame_data:
                    photon_series_metadata.update(scan_line_rate=frame_data["SI.hScan2D.scannerFrequency"])

                # Add version information to device description if available
                if "SI.VERSION_MAJOR" in frame_data:
                    version = f"{frame_data.get('SI.VERSION_MAJOR', '')}.{frame_data.get('SI.VERSION_MINOR', '')}.{frame_data.get('SI.VERSION_UPDATE', '')}"
                    metadata["Ophys"]["Device"][0][
                        "description"
                    ] = f"Microscope and acquisition data with ScanImage (version {version})"

            # Extract ROI metadata if available
            if "RoiGroups" in scanimage_metadata:
                roi_metadata = scanimage_metadata["RoiGroups"]

                # Extract grid spacing and origin coordinates from scanfields
                grid_spacing = None
                grid_spacing_unit = "n.a"
                origin_coords = None
                origin_coords_unit = "n.a"

                if "imagingRoiGroup" in roi_metadata and "rois" in roi_metadata["imagingRoiGroup"]:
                    rois = roi_metadata["imagingRoiGroup"]["rois"]
                    if isinstance(rois, dict) and "scanfields" in rois:
                        scanfields = rois["scanfields"]
                        if "sizeXY" in scanfields and "pixelResolutionXY" in scanfields:
                            fov_size_in_um = np.array(scanfields["sizeXY"])
                            frame_dimension = np.array(scanfields["pixelResolutionXY"])
                            grid_spacing = fov_size_in_um / frame_dimension
                            grid_spacing_unit = "micrometers"

                        if "centerXY" in scanfields:
                            origin_coords = scanfields["centerXY"]
                            origin_coords_unit = "micrometers"

                # Update imaging plane metadata with grid spacing and origin coordinates
                if grid_spacing is not None:
                    imaging_plane_metadata.update(
                        grid_spacing=grid_spacing.tolist(), grid_spacing_unit=grid_spacing_unit
                    )

                if origin_coords is not None:
                    imaging_plane_metadata.update(origin_coords=origin_coords, origin_coords_unit=origin_coords_unit)

        return metadata

    def _get_session_start_time(self):
        """
        Open a ScanImage TIFF file, read the first frame, extract and parse the 'epoch' metadata
        as the session start time.

        Parameters
        ----------
        tiff_path : str or Path
            Path to the TIFF file.

        Returns
        -------
        datetime
            Parsed datetime from the 'epoch' metadata.

        Raises
        ------
        ValueError
            If 'epoch' metadata is not found or is malformed.
        """

        from tifffile import TiffReader

        tiff_file_path = self.imaging_extractor.file_path
        with TiffReader(tiff_file_path) as tif:
            image_description = tif.pages[0].tags["ImageDescription"].value

        import re

        match = re.search(r"epoch\s*=\s*\[([^\]]+)\]", image_description)
        if not match:
            raise ValueError(f"'epoch' field not found in {tiff_file_path}")

        epoch_values = match.group(1).split()
        import warnings

        if len(epoch_values) != 6:
            warnings.warn(
                f"Expected 6 values in 'epoch' field, found {len(epoch_values)}: \n" f"Epoch field {epoch_values}."
            )
            return None

        year, month, day, hour, minute, seconds = map(float, epoch_values)
        second_int = int(seconds)
        microsecond = int((seconds - second_int) * 1e6)

        return datetime.datetime(int(year), int(month), int(day), int(hour), int(minute), second_int, microsecond)

    @staticmethod
    def get_scanimage_version(file_path: str) -> int:
        """
        Extract the ScanImage version from a BigTIFF file without validation.

        Parameters:
        -----------
        file_path : str or Path
            Path to the ScanImage TIFF file

        Returns:
        --------
        int
            ScanImage version number
        """
        with open(file_path, "rb") as f:
            # Skip the TIFF header (16 bytes) and the Magic Number (4 bytes)
            f.seek(20)

            # Read ScanImage version (4 bytes)
            version_bytes = f.read(4)
            scanimage_version = int.from_bytes(version_bytes, byteorder="little")

            return scanimage_version


class ScanImageLegacyImagingInterface(BaseImagingExtractorInterface):
    """Interface for reading TIFF files produced via ScanImage v3.8."""

    display_name = "ScanImage Imaging"
    associated_suffixes = (".tif",)
    info = "Interface for ScanImage v3.8 TIFF files."

    ExtractorName = "ScanImageTiffImagingExtractor"

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to Tiff file."
        return source_schema

    def _source_data_to_extractor_kwargs(self, source_data: dict) -> dict:
        extractor_kwargs = source_data.copy()
        extractor_kwargs.pop("fallback_sampling_frequency", None)
        extractor_kwargs["sampling_frequency"] = self.sampling_frequency

        return extractor_kwargs

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        fallback_sampling_frequency: float | None = None,
        verbose: bool = False,
    ):
        """
        DataInterface for reading Tiff files that are generated by ScanImage v3.8. This interface extracts the metadata
        from the exif of the tiff file.

        Parameters
        ----------
        file_path: FilePath
            Path to tiff file.
        fallback_sampling_frequency: float, optional
            The sampling frequency can usually be extracted from the scanimage metadata in
            exif:ImageDescription:state.acq.frameRate. If not, use this.
        """
        from roiextractors.extractors.tiffimagingextractors.scanimagetiff_utils import (
            extract_extra_metadata,
        )

        self.image_metadata = extract_extra_metadata(file_path=file_path)

        if "state.acq.frameRate" in self.image_metadata:
            sampling_frequency = float(self.image_metadata["state.acq.frameRate"])
        elif "SI.hRoiManager.scanFrameRate" in self.image_metadata:
            sampling_frequency = float(self.image_metadata["SI.hRoiManager.scanFrameRate"])
        else:
            assert_msg = (
                "sampling frequency not found in image metadata, "
                "input the frequency using the argument `fallback_sampling_frequency`"
            )
            assert fallback_sampling_frequency is not None, assert_msg
            sampling_frequency = fallback_sampling_frequency

        self.sampling_frequency = sampling_frequency
        super().__init__(file_path=file_path, fallback_sampling_frequency=fallback_sampling_frequency, verbose=verbose)

    def get_metadata(self) -> dict:
        """
        Get metadata for the ScanImage imaging data.

        Returns
        -------
        dict
            Dictionary containing metadata including session start time and device information
            specific to the ScanImage system.
        """
        device_number = 0  # Imaging plane metadata is a list with metadata for each plane

        metadata = super().get_metadata()

        if "state.internal.triggerTimeString" in self.image_metadata:
            extracted_session_start_time = dateparse(self.image_metadata["state.internal.triggerTimeString"])
            metadata["NWBFile"].update(session_start_time=extracted_session_start_time)

        # Extract many scan image properties and attach them as dic in the description
        ophys_metadata = metadata["Ophys"]
        two_photon_series_metadata = ophys_metadata["TwoPhotonSeries"][device_number]
        if self.image_metadata is not None:
            extracted_description = json.dumps(self.image_metadata)
            two_photon_series_metadata.update(description=extracted_description)

        return metadata


class ScanImageMultiFileImagingInterface(BaseImagingExtractorInterface):
    """
    Interface for reading multi-file (buffered) TIFF files produced via ScanImage.

    It extracts metadata from the first TIFF file in the provided folder and determines the number of available planes.
    If there is more than one plane and no specific plane is provided, it creates an instance of ScanImageMultiPlaneMultiFileImagingInterface.
    If there is only one plane or a specific plane is provided, it creates an instance of ScanImageSinglePlaneMultiFileImagingInterface.
    """

    display_name = "ScanImage Multi-File Imaging"
    associated_suffixes = (".tif",)
    info = "Interface for ScanImage multi-file (buffered) TIFF files."

    ExtractorName = "ScanImageTiffSinglePlaneMultiFileImagingExtractor"

    @classmethod
    def get_source_schema(cls) -> dict:
        """
        Get the source schema for the ScanImage multi-file imaging interface.

        Returns
        -------
        dict
            The schema dictionary containing input parameters and descriptions
            for initializing the ScanImage multi-file interface.
        """
        source_schema = super().get_source_schema()
        source_schema["properties"]["folder_path"]["description"] = "Path to the folder containing the TIFF files."
        return source_schema

    @validate_call
    def __new__(
        cls,
        folder_path: DirectoryPath,
        file_pattern: str,
        channel_name: str | None = None,
        plane_name: str | None = None,
        extract_all_metadata: bool = False,
        verbose: bool = False,
    ):
        from natsort import natsorted
        from roiextractors.extractors.tiffimagingextractors.scanimagetiff_utils import (
            extract_extra_metadata,
            parse_metadata,
        )

        file_paths = natsorted(Path(folder_path).glob(file_pattern))
        first_file_path = file_paths[0]

        image_metadata = extract_extra_metadata(file_path=first_file_path)

        version = get_scanimage_major_version(scanimage_metadata=image_metadata)
        if version == "3.8":
            raise ValueError("ScanImage version 3.8 is not supported.")

        parsed_metadata = parse_metadata(metadata=image_metadata)
        available_planes = [f"{i}" for i in range(parsed_metadata["num_planes"])]
        if len(available_planes) > 1 and plane_name is None:
            return ScanImageMultiPlaneMultiFileImagingInterface(
                folder_path=folder_path,
                file_pattern=file_pattern,
                channel_name=channel_name,
                image_metadata=image_metadata,
                parsed_metadata=parsed_metadata,
                extract_all_metadata=extract_all_metadata,
                verbose=verbose,
            )

        return ScanImageSinglePlaneMultiFileImagingInterface(
            folder_path=folder_path,
            file_pattern=file_pattern,
            channel_name=channel_name,
            plane_name=plane_name,
            image_metadata=image_metadata,
            parsed_metadata=parsed_metadata,
            extract_all_metadata=extract_all_metadata,
            verbose=verbose,
        )


class ScanImageMultiPlaneImagingInterface(BaseImagingExtractorInterface):
    """Interface for reading multi plane (volumetric) TIFF files produced via ScanImage."""

    display_name = "ScanImage Volumetric Imaging"
    associated_suffixes = (".tif",)
    info = "Interface for ScanImage multi plane (volumetric) TIFF files."

    ExtractorName = "ScanImageTiffMultiPlaneImagingExtractor"

    def _source_data_to_extractor_kwargs(self, source_data: dict) -> dict:
        extractor_kwargs = source_data.copy()
        extractor_kwargs.pop("image_metadata")
        extractor_kwargs["metadata"] = self.image_metadata

        return extractor_kwargs

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        channel_name: str | None = None,
        image_metadata: dict | None = None,
        parsed_metadata: dict | None = None,
        verbose: bool = False,
    ):
        """
        DataInterface for reading multi-file (buffered) TIFF files that are generated by ScanImage.

        Parameters
        ----------
        file_path : FilePath
            Path to the TIFF file.
        channel_name : str
            Name of the channel for this extractor.
        """
        from roiextractors.extractors.tiffimagingextractors.scanimagetiff_utils import (
            extract_extra_metadata,
            parse_metadata,
        )

        image_metadata = image_metadata or extract_extra_metadata(file_path=file_path)
        self.image_metadata = image_metadata
        parsed_metadata = parsed_metadata or parse_metadata(metadata=self.image_metadata)

        if parsed_metadata["num_planes"] == 1:
            raise ValueError(
                "Only one plane detected. For single plane imaging data use ScanImageSinglePlaneImagingInterface instead."
            )

        available_channels = parsed_metadata["channel_names"]
        if channel_name is None:
            if len(available_channels) > 1:
                raise ValueError(
                    "More than one channel is detected! \n "
                    "Please specify which channel you wish to load with the `channel_name` argument \n "
                    f"Available channels are: {available_channels}"
                )
            channel_name = available_channels[0]
        assert (
            channel_name in available_channels
        ), f"Channel '{channel_name}' not found! \n Available channels are: {available_channels}"

        two_photon_series_name_suffix = None
        if len(available_channels) > 1:
            two_photon_series_name_suffix = f"{channel_name.replace(' ', '')}"
        self.two_photon_series_name_suffix = two_photon_series_name_suffix

        self.metadata = image_metadata
        self.parsed_metadata = parsed_metadata
        super().__init__(
            file_path=file_path,
            channel_name=channel_name,
            image_metadata=image_metadata,
            parsed_metadata=parsed_metadata,
            verbose=verbose,
        )

    def get_metadata(self) -> dict:
        """
        Get metadata for the ScanImage imaging data.

        Returns
        -------
        dict
            Dictionary containing metadata including session start time and device information
            specific to the ScanImage system.
        """
        metadata = super().get_metadata()

        extracted_session_start_time = datetime.datetime.strptime(
            self.image_metadata["epoch"], "[%Y %m %d %H %M %S.%f]"
        )
        metadata["NWBFile"].update(session_start_time=extracted_session_start_time)

        ophys_metadata = metadata["Ophys"]
        two_photon_series_metadata = ophys_metadata["TwoPhotonSeries"][0]

        if self.image_metadata is not None:
            extracted_description = json.dumps(self.image_metadata)
            two_photon_series_metadata.update(description=extracted_description)

        if self.two_photon_series_name_suffix is None:
            return metadata

        imaging_plane_metadata = ophys_metadata["ImagingPlane"][0]
        channel_name = self.source_data["channel_name"]
        optical_channel_metadata = [
            channel for channel in imaging_plane_metadata["optical_channel"] if channel["name"] == channel_name
        ]
        imaging_plane_name = f"ImagingPlane{self.two_photon_series_name_suffix}"
        imaging_plane_metadata.update(
            name=imaging_plane_name,
            optical_channel=optical_channel_metadata,
        )
        two_photon_series_metadata.update(
            name=f"TwoPhotonSeries{self.two_photon_series_name_suffix}",
            imaging_plane=imaging_plane_name,
        )

        return metadata


class ScanImageMultiPlaneMultiFileImagingInterface(BaseImagingExtractorInterface):
    """Interface for reading volumetric multi-file (buffered) TIFF files produced via ScanImage."""

    display_name = "ScanImage Volumetric Multi-File Imaging"
    associated_suffixes = (".tif",)
    info = "Interface for ScanImage multi-file (buffered) volumetric TIFF files."

    ExtractorName = "ScanImageTiffMultiPlaneMultiFileImagingExtractor"

    @validate_call
    def __init__(
        self,
        folder_path: DirectoryPath,
        file_pattern: str,
        channel_name: str | None = None,
        extract_all_metadata: bool = False,
        image_metadata: dict | None = None,
        parsed_metadata: dict | None = None,
        verbose: bool = False,
    ):
        """
        DataInterface for reading multi-file (buffered) TIFF files that are generated by ScanImage.

        Parameters
        ----------
        folder_path : DirectoryPath
            Path to the folder containing the TIFF files.
        file_pattern : str
            Pattern for the TIFF files to read -- see pathlib.Path.glob for details.
        channel_name : str
            The name of the channel to load, to determine what channels are available use ScanImageTiffSinglePlaneImagingExtractor.get_available_channels(file_path=...).
        extract_all_metadata : bool
            If True, extract metadata from every file in the folder. If False, only extract metadata from the first
            file in the folder. The default is False.
        """
        from natsort import natsorted
        from roiextractors.extractors.tiffimagingextractors.scanimagetiff_utils import (
            extract_extra_metadata,
            parse_metadata,
        )

        file_paths = natsorted(Path(folder_path).glob(file_pattern))
        first_file_path = file_paths[0]

        image_metadata = image_metadata or extract_extra_metadata(file_path=first_file_path)
        self.image_metadata = image_metadata

        version = get_scanimage_major_version(scanimage_metadata=image_metadata)
        if version == "3.8":
            raise ValueError(
                "ScanImage version 3.8 is not supported. \n " "Please use ScanImageImagingInterface instead."
            )

        parsed_metadata = parsed_metadata or parse_metadata(metadata=image_metadata)
        if parsed_metadata["num_planes"] == 1:
            raise ValueError(
                "Only one plane detected. For single plane imaging data use ScanImageSinglePlaneMultiFileImagingInterface instead."
            )

        available_channels = parsed_metadata["channel_names"]
        if channel_name is None:
            if len(available_channels) > 1:
                raise ValueError(
                    "More than one channel is detected! \n "
                    "Please specify which channel you wish to load with the `channel_name` argument \n "
                    f"Available channels are: {available_channels}"
                )
            channel_name = available_channels[0]
        assert (
            channel_name in available_channels
        ), f"Channel '{channel_name}' not found! \n Available channels are: {available_channels}"

        two_photon_series_name_suffix = None
        if len(available_channels) > 1:
            two_photon_series_name_suffix = f"{channel_name.replace(' ', '')}"
        self.two_photon_series_name_suffix = two_photon_series_name_suffix

        super().__init__(
            folder_path=folder_path,
            file_pattern=file_pattern,
            channel_name=channel_name,
            extract_all_metadata=extract_all_metadata,
            verbose=verbose,
        )

    def get_metadata(self) -> dict:
        """
        Get metadata for the ScanImage imaging data.

        Returns
        -------
        dict
            Dictionary containing metadata including session start time, device information,
            and imaging plane configuration specific to the ScanImage system.
        """
        metadata = super().get_metadata()

        extracted_session_start_time = datetime.datetime.strptime(
            self.image_metadata["epoch"], "[%Y %m %d %H %M %S.%f]"
        )
        metadata["NWBFile"].update(session_start_time=extracted_session_start_time)

        ophys_metadata = metadata["Ophys"]
        two_photon_series_metadata = ophys_metadata["TwoPhotonSeries"][0]

        if self.image_metadata is not None:
            extracted_description = json.dumps(self.image_metadata)
            two_photon_series_metadata.update(description=extracted_description)

        if self.two_photon_series_name_suffix is None:
            return metadata

        imaging_plane_metadata = ophys_metadata["ImagingPlane"][0]
        channel_name = self.source_data["channel_name"]
        optical_channel_metadata = [
            channel for channel in imaging_plane_metadata["optical_channel"] if channel["name"] == channel_name
        ]
        imaging_plane_name = f"ImagingPlane{self.two_photon_series_name_suffix}"
        imaging_plane_metadata.update(
            name=imaging_plane_name,
            optical_channel=optical_channel_metadata,
        )
        two_photon_series_metadata.update(
            name=f"TwoPhotonSeries{self.two_photon_series_name_suffix}",
            imaging_plane=imaging_plane_name,
        )

        return metadata


class ScanImageSinglePlaneImagingInterface(BaseImagingExtractorInterface):
    """Interface for reading TIFF files produced via ScanImage."""

    display_name = "ScanImage Single Plane Imaging"
    associated_suffixes = (".tif",)
    info = "Interface for ScanImage TIFF files."

    ExtractorName = "ScanImageTiffSinglePlaneImagingExtractor"

    def _source_data_to_extractor_kwargs(self, source_data: dict) -> dict:
        extractor_kwargs = source_data.copy()
        extractor_kwargs.pop("image_metadata")
        extractor_kwargs["metadata"] = self.image_metadata

        return extractor_kwargs

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        channel_name: str | None = None,
        plane_name: str | None = None,
        image_metadata: dict | None = None,
        parsed_metadata: dict | None = None,
        verbose: bool = False,
    ):
        """
        DataInterface for reading multi-file (buffered) TIFF files that are generated by ScanImage.

        Parameters
        ----------
        file_path : FilePath
            Path to the TIFF file.
        channel_name : str
            The name of the channel to load, to determine what channels are available use ScanImageTiffSinglePlaneImagingExtractor.get_available_channels(file_path=...).
        plane_name : str
            The name of the plane to load, to determine what planes are available use ScanImageTiffSinglePlaneImagingExtractor.get_available_planes(file_path=...).
        """
        from roiextractors.extractors.tiffimagingextractors.scanimagetiff_utils import (
            extract_extra_metadata,
            parse_metadata,
        )

        image_metadata = image_metadata or extract_extra_metadata(file_path=file_path)
        self.image_metadata = image_metadata

        version = get_scanimage_major_version(scanimage_metadata=image_metadata)
        if version == "3.8":
            raise ValueError(
                "ScanImage version 3.8 is not supported. \n " "Please use ScanImageImagingInterface instead."
            )

        parsed_metadata = parsed_metadata or parse_metadata(metadata=image_metadata)
        available_channels = parsed_metadata["channel_names"]
        if channel_name is None:
            if len(available_channels) > 1:
                raise ValueError(
                    "More than one channel is detected! \n "
                    "Please specify which channel you wish to load with the `channel_name` argument \n "
                    f"Available channels are: {available_channels}"
                )
            channel_name = available_channels[0]
        assert (
            channel_name in available_channels
        ), f"Channel '{channel_name}' not found! \n Available channels are: {available_channels}"

        available_planes = [f"{i}" for i in range(parsed_metadata["num_planes"])]
        if plane_name is None:
            if len(available_planes) > 1:
                raise ValueError(
                    "More than one plane is detected! \n "
                    "Please specify which plane you wish to load with the `plane_name` argument \n "
                    f"Available planes are: {available_planes}"
                )
            plane_name = available_planes[0]
        assert (
            plane_name in available_planes
        ), f"Plane '{plane_name}' not found! \n Available planes are: {available_planes}"

        two_photon_series_name_suffix = None
        if len(available_channels) > 1:
            two_photon_series_name_suffix = f"{channel_name.replace(' ', '')}"
        if len(available_planes) > 1:
            two_photon_series_name_suffix = f"{two_photon_series_name_suffix}Plane{plane_name}"
        self.two_photon_series_name_suffix = two_photon_series_name_suffix

        self.metadata = image_metadata
        self.parsed_metadata = parsed_metadata
        super().__init__(
            file_path=file_path,
            channel_name=channel_name,
            plane_name=plane_name,
            image_metadata=image_metadata,
            parsed_metadata=parsed_metadata,
            verbose=verbose,
        )

    def get_metadata(self) -> dict:
        """
        Get metadata for the ScanImage imaging data.

        Returns
        -------
        dict
            Dictionary containing metadata including session start time, device information,
            and imaging plane configuration specific to the ScanImage system.
        """
        metadata = super().get_metadata()

        extracted_session_start_time = datetime.datetime.strptime(
            self.image_metadata["epoch"], "[%Y %m %d %H %M %S.%f]"
        )
        metadata["NWBFile"].update(session_start_time=extracted_session_start_time)

        ophys_metadata = metadata["Ophys"]
        two_photon_series_metadata = ophys_metadata["TwoPhotonSeries"][0]

        if self.image_metadata is not None:
            extracted_description = json.dumps(self.image_metadata)
            two_photon_series_metadata.update(description=extracted_description)

        if self.two_photon_series_name_suffix is None:
            return metadata

        imaging_plane_metadata = ophys_metadata["ImagingPlane"][0]
        channel_name = self.source_data["channel_name"]
        optical_channel_metadata = [
            channel for channel in imaging_plane_metadata["optical_channel"] if channel["name"] == channel_name
        ]
        imaging_plane_name = f"ImagingPlane{self.two_photon_series_name_suffix}"
        imaging_plane_metadata.update(
            name=imaging_plane_name,
            optical_channel=optical_channel_metadata,
        )
        two_photon_series_metadata.update(
            name=f"TwoPhotonSeries{self.two_photon_series_name_suffix}",
            imaging_plane=imaging_plane_name,
        )

        return metadata


class ScanImageSinglePlaneMultiFileImagingInterface(BaseImagingExtractorInterface):
    """Interface for reading multi-file (buffered) TIFF files produced via ScanImage."""

    display_name = "ScanImage Single Plane Multi-File Imaging"
    associated_suffixes = (".tif",)
    info = "Interface for ScanImage multi-file (buffered) TIFF files."

    ExtractorName = "ScanImageTiffSinglePlaneMultiFileImagingExtractor"

    @validate_call
    def __init__(
        self,
        folder_path: DirectoryPath,
        file_pattern: str,
        channel_name: str | None = None,
        plane_name: str | None = None,
        image_metadata: dict | None = None,
        parsed_metadata: dict | None = None,
        extract_all_metadata: bool = False,
        verbose: bool = False,
    ):
        """
        DataInterface for reading multi-file (buffered) TIFF files that are generated by ScanImage.

        Parameters
        ----------
        folder_path : DirectoryPath
            Path to the folder containing the TIFF files.
        file_pattern : str
            Pattern for the TIFF files to read -- see pathlib.Path.glob for details.
        channel_name : str
            The name of the channel to load, to determine what channels are available use ScanImageTiffSinglePlaneImagingExtractor.get_available_channels(file_path=...).
        plane_name : str
            The name of the plane to load, to determine what planes are available use ScanImageTiffSinglePlaneImagingExtractor.get_available_planes(file_path=...).
        extract_all_metadata : bool
            If True, extract metadata from every file in the folder. If False, only extract metadata from the first
            file in the folder. The default is False.
        """
        from natsort import natsorted
        from roiextractors.extractors.tiffimagingextractors.scanimagetiff_utils import (
            extract_extra_metadata,
            parse_metadata,
        )

        file_paths = natsorted(Path(folder_path).glob(file_pattern))
        first_file_path = file_paths[0]

        image_metadata = image_metadata or extract_extra_metadata(file_path=first_file_path)
        self.image_metadata = image_metadata

        version = get_scanimage_major_version(scanimage_metadata=image_metadata)
        if version == "3.8":
            raise ValueError(
                "ScanImage version 3.8 is not supported. \n " "Please use ScanImageImagingInterface instead."
            )

        parsed_metadata = parsed_metadata or parse_metadata(metadata=image_metadata)
        available_channels = parsed_metadata["channel_names"]
        if channel_name is None:
            if len(available_channels) > 1:
                raise ValueError(
                    "More than one channel is detected! \n "
                    "Please specify which channel you wish to load with the `channel_name` argument \n "
                    f"Available channels are: {available_channels}"
                )
            channel_name = available_channels[0]
        assert (
            channel_name in available_channels
        ), f"Channel '{channel_name}' not found! \n Available channels are: {available_channels}"

        available_planes = [f"{i}" for i in range(parsed_metadata["num_planes"])]
        if plane_name is None:
            if len(available_planes) > 1:
                raise ValueError(
                    "More than one plane is detected! \n "
                    "Please specify which plane you wish to load with the `plane_name` argument \n "
                    f"Available planes are: {available_planes}"
                )
            plane_name = available_planes[0]
        assert (
            plane_name in available_planes
        ), f"Plane '{plane_name}' not found! \n Available planes are: {available_planes}"

        two_photon_series_name_suffix = None
        if len(available_channels) > 1:
            two_photon_series_name_suffix = f"{channel_name.replace(' ', '')}"
        if len(available_planes) > 1:
            two_photon_series_name_suffix = f"{two_photon_series_name_suffix}Plane{plane_name}"
        self.two_photon_series_name_suffix = two_photon_series_name_suffix

        super().__init__(
            folder_path=folder_path,
            file_pattern=file_pattern,
            channel_name=channel_name,
            plane_name=plane_name,
            extract_all_metadata=extract_all_metadata,
            verbose=verbose,
        )

    def get_metadata(self) -> dict:
        """
        Get metadata for the ScanImage imaging data.

        Returns
        -------
        dict
            Dictionary containing metadata including session start time, device information,
            and imaging plane configuration specific to the ScanImage system.
        """
        metadata = super().get_metadata()

        extracted_session_start_time = datetime.datetime.strptime(
            self.image_metadata["epoch"], "[%Y %m %d %H %M %S.%f]"
        )
        metadata["NWBFile"].update(session_start_time=extracted_session_start_time)

        ophys_metadata = metadata["Ophys"]
        two_photon_series_metadata = ophys_metadata["TwoPhotonSeries"][0]

        if self.image_metadata is not None:
            extracted_description = json.dumps(self.image_metadata)
            two_photon_series_metadata.update(description=extracted_description)

        if self.two_photon_series_name_suffix is None:
            return metadata

        imaging_plane_metadata = ophys_metadata["ImagingPlane"][0]
        channel_name = self.source_data["channel_name"]
        optical_channel_metadata = [
            channel for channel in imaging_plane_metadata["optical_channel"] if channel["name"] == channel_name
        ]
        imaging_plane_name = f"ImagingPlane{self.two_photon_series_name_suffix}"
        imaging_plane_metadata.update(
            name=imaging_plane_name,
            optical_channel=optical_channel_metadata,
        )
        two_photon_series_metadata.update(
            name=f"TwoPhotonSeries{self.two_photon_series_name_suffix}",
            imaging_plane=imaging_plane_name,
        )

        return metadata


def get_scanimage_major_version(scanimage_metadata: dict) -> str:
    """
    Determine the version of ScanImage that produced the TIFF file.

    Parameters
    ----------
    scanimage_metadata : dict
        Dictionary of metadata extracted from a TIFF file produced via ScanImage.

    Returns
    -------
    version: str
        The version of ScanImage that produced the TIFF file.

    Raises
    ------
    ValueError
        If the ScanImage version could not be determined from metadata.
    """
    if "SI.VERSION_MAJOR" in scanimage_metadata:
        return scanimage_metadata["SI.VERSION_MAJOR"]
    elif "state.software.version" in scanimage_metadata:
        return scanimage_metadata["state.software.version"]

    raise ValueError("ScanImage version could not be determined from metadata.")
