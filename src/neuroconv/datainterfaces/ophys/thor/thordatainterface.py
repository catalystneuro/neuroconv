"""Interface for Thor TIFF files with OME metadata."""

import warnings
from datetime import datetime, timezone

import numpy as np
from pydantic import FilePath, validate_call

from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils import DeepDict, get_json_schema_from_method_signature


class ThorImagingInterface(BaseImagingExtractorInterface):
    """
    Interface for Thor TIFF files with OME metadata.

    This interface is designed to work with data acquired using ThorImageLS software
    (not to be confused with the ThorLabs hardware itself). The interface reads TIFF files
    exported by ThorImageLS software, which follows the OME-TIFF standard, along with an
    Experiment.xml file that contains metadata about the acquisition.

    Note that it is possible that data was acquired with a Thor microscope but not with
    the ThorImageLS software, in which case this interface may not work correctly.
    """

    display_name = "ThorLabs TIFF Imaging"
    associated_suffixes = (".tif", ".tiff")
    info = "Interface for Thor TIFF files Exporter with ThorImageLS."

    @classmethod
    def get_source_schema(cls) -> dict:
        """
        Get the source schema for the Thor imaging interface.

        Returns
        -------
        dict
            The JSON schema for the Thor imaging interface source data,
            containing file path and channel name parameters.
        """
        source_schema = get_json_schema_from_method_signature(method=cls.__init__, exclude=[])

        return source_schema

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *args,
        channel_name: str | None = None,
        verbose: bool = False,
        metadata_key: str | None = None,
    ):  # TODO: change to * (keyword only) on or after August 2026
        """
        Initialize reading of a TIFF file.

        Parameters
        ----------
        file_path : FilePath
            Path to first OME TIFF file (e.g., ChanA_001_001_001_001.tif)
        channel_name : str, optional
            Name of the channel to extract (must match name in Experiment.xml)
        verbose : bool, default: False
            If True, print verbose output
        metadata_key : str, optional
            # TODO: improve docstring once #1653 (ophys metadata documentation) is merged
            Metadata key for this interface. When None, defaults to "thor_imaging"
            or "thor_imaging_channel_{channel_name}" if channel_name is provided.
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "channel_name",
                "verbose",
            ]
            num_positional_args_before_args = 1  # file_path
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
                f"Passing arguments positionally to ThorImagingInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            channel_name = positional_values.get("channel_name", channel_name)
            verbose = positional_values.get("verbose", verbose)

        if metadata_key is None:
            metadata_key = f"thor_imaging_channel_{channel_name}" if channel_name is not None else "thor_imaging"

        super().__init__(file_path=file_path, channel_name=channel_name, verbose=verbose, metadata_key=metadata_key)
        self.channel_name = channel_name

    @classmethod
    def get_extractor_class(cls):
        from roiextractors import ThorTiffImagingExtractor

        return ThorTiffImagingExtractor

    def _initialize_extractor(self, interface_kwargs: dict):
        self.extractor_kwargs = interface_kwargs.copy()
        self.extractor_kwargs.pop("verbose", None)
        self.extractor_kwargs.pop("photon_series_type", None)
        self.extractor_kwargs.pop("metadata_key", None)

        extractor_class = self.get_extractor_class()
        extractor_instance = extractor_class(**self.extractor_kwargs)
        return extractor_instance

    def _get_session_start_time(self):
        """Extract session start time from the experiment XML."""
        xml_dict = self.imaging_extractor._experiment_xml_dict
        thor_experiment = xml_dict["ThorImageExperiment"]
        date_info = thor_experiment["Date"]
        if isinstance(date_info, list):
            first_entry_with_date = next((entry for entry in date_info if "@date" in entry), None)
            unix_timestamps = first_entry_with_date["@uTime"]
        else:
            unix_timestamps = date_info["@uTime"]
        return datetime.fromtimestamp(float(unix_timestamps), tz=timezone.utc)

    def _get_device_description(self):
        """Extract device description from the experiment XML."""
        xml_dict = self.imaging_extractor._experiment_xml_dict
        thor_experiment = xml_dict["ThorImageExperiment"]
        software_version = thor_experiment["Software"]["@version"]
        return f"ThorLabs 2P Microscope running ThorImageLS {software_version}"

    def get_metadata(self, *, use_new_metadata_format: bool = False) -> DeepDict:
        """
        Retrieve the metadata for the Thor imaging data.

        Parameters
        ----------
        use_new_metadata_format : bool, default: False
            When False, returns the old list-based metadata format (backward compatible).
            When True, returns dict-based metadata with ThorImageLS provenance.

        Returns
        -------
        DeepDict
            Dictionary containing metadata including device information, imaging plane details,
            and photon series configuration.
        """
        self.session_start_time = self._get_session_start_time()
        device_description = self._get_device_description()

        if use_new_metadata_format:
            metadata = super().get_metadata(use_new_metadata_format=True)
            metadata["NWBFile"]["session_start_time"] = self.session_start_time
            metadata["Devices"] = {self.metadata_key: {"description": device_description}}
            metadata["Ophys"] = {
                "MicroscopySeries": {
                    self.metadata_key: {
                        "description": "Imaging data acquired with ThorImageLS.",
                    },
                },
            }
            return metadata

        metadata = super().get_metadata()
        metadata["NWBFile"]["session_start_time"] = self.session_start_time

        metadata.setdefault("Ophys", {})["Device"] = [{"name": "ThorMicroscope", "description": device_description}]

        # LSM metadata
        lsm = thor_experiment["LSM"]
        pixel_size = float(lsm["@pixelSizeUM"])
        width_um = float(lsm["@widthUM"])
        height_um = float(lsm["@heightUM"])

        ChannelName = _to_camel_case(self.channel_name)

        optical_channel_dict = {"name": ChannelName, "description": "", "emission_lambda": np.nan}
        optical_channels = [optical_channel_dict]

        imaging_plane_name = f"ImagingPlane{ChannelName}"
        channel_imaging_plane_metadata = {
            "name": imaging_plane_name,
            "optical_channel": optical_channels,
            "description": "2P Imaging Plane",
            "device": "ThorMicroscope",
            "excitation_lambda": np.nan,  # Placeholder
            "indicator": "unknown",
            "location": "unknown",
            "grid_spacing": [pixel_size * 1e-6, pixel_size * 1e-6],  # Convert um to meters
            "grid_spacing_unit": "meters",
        }
        metadata["Ophys"]["ImagingPlane"] = [channel_imaging_plane_metadata]

        # TwoPhotonSeries metadata
        two_photon_series_name = f"TwoPhotonSeries{ChannelName}"
        two_photon_series_metadata = {
            "name": two_photon_series_name,
            "imaging_plane": imaging_plane_name,
            "field_of_view": [width_um * 1e-6, height_um * 1e-6],  # Convert um to meters
            "unit": "n.a.",
        }
        metadata["Ophys"]["TwoPhotonSeries"] = [two_photon_series_metadata]

        return metadata


def _to_camel_case(s: str) -> str:
    """
    Convert a string to CamelCase.

    Parameters
    ----------
    s : str
        Input string, potentially with underscores

    Returns
    -------
    str
        CamelCase string, or "Default" if input is empty
    """
    if not s:
        return "Default"
    parts = s.split("_")
    return parts[0] + "".join(word.title() for word in parts[1:])
