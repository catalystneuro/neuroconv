import datetime
import json
from pathlib import Path
from typing import Optional

from dateutil.parser import parse as dateparse
from pydantic import DirectoryPath, FilePath, validate_call

from ..baseimagingextractorinterface import BaseImagingExtractorInterface


class ScanImageImagingInterface(BaseImagingExtractorInterface):
    """
    Interface for reading TIFF files produced via ScanImage.

    It extracts metadata from the provided TIFF file and determines the ScanImage version.
    For the legacy version 3.8, it creates an instance of ScanImageLegacyImagingInterface.
    For newer versions, it parses the metadata and determines the number of planes.
    If there is more than one plane and no specific plane is provided, it creates an instance of ScanImageMultiPlaneImagingInterface.
    If there is only one plane or a specific plane is provided, it creates an instance of ScanImageSinglePlaneImagingInterface.
    """

    display_name = "ScanImage Imaging"
    associated_suffixes = (".tif",)
    info = "Interface for ScanImage TIFF files."

    ExtractorName = "ScanImageTiffImagingExtractor"

    @classmethod
    def get_source_schema(cls) -> dict:
        """
        Get the source schema for the ScanImage imaging interface.

        Returns
        -------
        dict
            The schema dictionary containing input parameters and descriptions
            for initializing the ScanImage interface.
        """
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to Tiff file."
        return source_schema

    @validate_call
    def __new__(
        cls,
        file_path: FilePath,
        channel_name: Optional[str] = None,
        plane_name: Optional[str] = None,
        fallback_sampling_frequency: Optional[float] = None,
        verbose: bool = False,
    ):
        from roiextractors.extractors.tiffimagingextractors.scanimagetiff_utils import (
            extract_extra_metadata,
            parse_metadata,
        )

        image_metadata = extract_extra_metadata(file_path=file_path)
        version = get_scanimage_major_version(scanimage_metadata=image_metadata)
        if version == "3.8":
            return ScanImageLegacyImagingInterface(
                file_path=file_path,
                fallback_sampling_frequency=fallback_sampling_frequency,
                verbose=verbose,
            )

        parsed_metadata = parse_metadata(metadata=image_metadata)
        available_planes = [f"{i}" for i in range(parsed_metadata["num_planes"])]
        if len(available_planes) > 1 and plane_name is None:
            return ScanImageMultiPlaneImagingInterface(
                file_path=file_path,
                channel_name=channel_name,
                image_metadata=image_metadata,
                parsed_metadata=parsed_metadata,
                verbose=verbose,
            )

        return ScanImageSinglePlaneImagingInterface(
            file_path=file_path,
            channel_name=channel_name,
            plane_name=plane_name,
            image_metadata=image_metadata,
            parsed_metadata=parsed_metadata,
            verbose=verbose,
        )


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
        fallback_sampling_frequency: Optional[float] = None,
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
        channel_name: Optional[str] = None,
        plane_name: Optional[str] = None,
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
        channel_name: Optional[str] = None,
        image_metadata: Optional[dict] = None,
        parsed_metadata: Optional[dict] = None,
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
        channel_name: Optional[str] = None,
        extract_all_metadata: bool = False,
        image_metadata: Optional[dict] = None,
        parsed_metadata: Optional[dict] = None,
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
        channel_name: Optional[str] = None,
        plane_name: Optional[str] = None,
        image_metadata: Optional[dict] = None,
        parsed_metadata: Optional[dict] = None,
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
        channel_name: Optional[str] = None,
        plane_name: Optional[str] = None,
        image_metadata: Optional[dict] = None,
        parsed_metadata: Optional[dict] = None,
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
