"""Femtonics imaging interface for NeuroConv."""

from typing import Optional

from pydantic import FilePath

from ...ophys.baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils import DeepDict


class FemtonicsImagingInterface(BaseImagingExtractorInterface):
    """
    Data interface for Femtonics imaging data (.mesc files).

    This interface handles Femtonics two-photon microscopy data stored in MESc
    (Measurement Session Container) format, which is an HDF5-based file format
    containing imaging data, experiment metadata, scan parameters, and hardware configuration.
    """

    display_name = "Femtonics Imaging"
    associated_suffixes = (".mesc",)
    info = "Interface for Femtonics two-photon imaging data in MESc format."

    def __init__(
        self,
        file_path: FilePath,
        session_name: Optional[str] = None,
        munit_name: Optional[str] = None,
        channel_name: Optional[str] = None,
        verbose: bool = False,
    ):
        """
        Initialize the FemtonicsImagingInterface.

        Parameters
        ----------
        file_path : FilePath
            Path to the .mesc file.
        session_name : str, optional
            Name of the MSession to use (e.g., "MSession_0", "MSession_1").
            If None, and there is only one session, then the first available session will be selected automatically. Otherwise this to be specified with the desired session.
            In Femtonics MESc files, an MSession ("Measurement Session") represents a single experimental session,
            which may contain one or more MUnits (imaging acquisitions or experiments). MSessions are typically
            named as "MSession_0", "MSession_1", etc...

        munit_name : str, optional
            Name of the MUnit within the specified session (e.g., "MUnit_0", "MUnit_1").
            If None, and there is only one session, then the first available session will be selected automatically. Otherwise this to be specified with the desired session.

            In Femtonics MESc files, an MUnit ("Measurement Unit") represents a single imaging acquisition or experiment,
            including all associated imaging data and metadata. A single MSession can contain multiple MUnits,
            each corresponding to a separate imaging run/experiment performed during the session.
            MUnits are named as "MUnit_0", "MUnit_1", etc. within each session.

        channel_name : str, optional
            Name of the channel to extract (e.g., 'UG', 'UR').
            If multiple channels are available and no channel is specified, an error will be raised.
            If only one channel is available, it will be used automatically.

        verbose : bool, optional
            Whether to print verbose output. Default is False.
        """

        # Store parameters for later use
        self._file_path = file_path
        self._session_name = session_name
        self._munit_name = munit_name
        self._channel_name = channel_name

        # Initialize the extractor directly with string parameters
        # The extractor now handles validation and selection internally
        super().__init__(
            file_path=file_path,
            session_name=session_name,
            munit_name=munit_name,
            channel_name=channel_name,
            verbose=verbose,
        )

        # Hack till roiextractors removes the get_num_channels method in check_imaging_equal.
        # TODO: remove this once roiextractors 0.6.1
        self.imaging_extractor.get_num_channels = lambda: 1  # Override to ensure only one channel is reported

    def get_metadata(self) -> DeepDict:
        """
        Extract metadata specific to Femtonics imaging data.

        Returns
        -------
        DeepDict
            Dictionary containing extracted metadata including device information,
            optical channels, imaging plane details, and acquisition parameters.
        """
        metadata = super().get_metadata()

        femtonics_metadata = self.imaging_extractor._get_metadata()

        # Extract pixel size information for imaging plane
        pixel_size_info = femtonics_metadata.get("pixel_size_micrometers")
        if pixel_size_info and "x_size" in pixel_size_info and "y_size" in pixel_size_info:
            x_size = pixel_size_info["x_size"]
            y_size = pixel_size_info["y_size"]
            x_units = pixel_size_info.get("x_units")
            y_units = pixel_size_info.get("y_units")

            # Only update if both units are the same or if units are missing
            if x_units == y_units:
                if "Ophys" in metadata and "ImagingPlane" in metadata["Ophys"]:
                    for imaging_plane in metadata["Ophys"]["ImagingPlane"]:
                        imaging_plane["grid_spacing"] = [x_size, y_size]
                        if x_units:
                            imaging_plane["grid_spacing_unit"] = x_units
                        else:
                            import warnings

                            warnings.warn(
                                "Pixel size unit is missing in Femtonics metadata; 'grid_spacing_unit' will be set to 'n.a.'."
                            )
                            imaging_plane["grid_spacing_unit"] = "n.a."

        # Add experimenter information
        experimenter_info = femtonics_metadata.get("experimenter_info", {})
        if experimenter_info.get("username"):
            metadata["NWBFile"]["experimenter"] = [experimenter_info["username"]]

        # Add session information
        session_uuid = femtonics_metadata.get("session_uuid")
        if session_uuid:
            metadata["NWBFile"]["session_id"] = session_uuid

        # Session description - use session_name and munit_name from the extractor's selected values
        selected_session_name = femtonics_metadata.get("session_name")
        selected_munit_name = femtonics_metadata.get("munit_name")
        experimenter_info = femtonics_metadata.get("experimenter_info", {})
        hostname = experimenter_info.get("hostname")

        session_descr = f"Session: {selected_session_name}, MUnit: {selected_munit_name}."
        if hostname:
            session_descr += f" Session performed on workstation: {hostname}."
        metadata["NWBFile"]["session_description"] = session_descr

        # Add PMT settings to optical channels
        pmt_settings = femtonics_metadata.get("pmt_settings", {})
        if pmt_settings:
            imaging_plane = metadata["Ophys"]["ImagingPlane"][0]
            optical_channels = imaging_plane.get("optical_channel", [])
            channel_names = self.imaging_extractor.get_channel_names()
            for i, channel_name in enumerate(channel_names):
                if channel_name in pmt_settings and i < len(optical_channels):
                    settings = pmt_settings[channel_name]
                    desc_parts = []
                    if settings.get("voltage") is not None:
                        desc_parts.append(f"PMT voltage: {settings['voltage']}V")
                    if settings.get("warmup_time") is not None:
                        desc_parts.append(f"Warmup time: {settings['warmup_time']}s")
                    if desc_parts:
                        desc = optical_channels[i].get("description", "")
                        desc = (desc + " " if desc else "") + ", ".join(desc_parts)
                        optical_channels[i]["description"] = desc.strip()

        # Add session start time if available
        session_start_time = femtonics_metadata.get("session_start_time")
        metadata["NWBFile"]["session_start_time"] = session_start_time

        # Add version and revision info to Ophys Device description
        version_info = femtonics_metadata.get("mesc_version_info", {})
        version_strs = []
        if version_info.get("version"):
            version_strs.append(f"version: {version_info['version']}")
        if version_info.get("revision"):
            version_strs.append(f"revision: {version_info['revision']}")
        if version_strs:
            device = metadata["Ophys"]["Device"][0]
            desc = device.get("description", "")
            desc = f"{desc} {', '.join(version_strs)}"
            device["description"] = desc.strip()

        # Add imaging rate to ImagingPlane properties (Femtonics: only one imaging plane, always present)
        sampling_freq = femtonics_metadata["sampling_frequency_hz"]
        imaging_plane = metadata["Ophys"]["ImagingPlane"][0]
        imaging_plane["imaging_rate"] = sampling_freq

        # Add geometric transformations to ImagingPlane description
        geometric_transformations = femtonics_metadata.get("geometric_transformations", {})
        if geometric_transformations:
            imaging_plane = metadata["Ophys"]["ImagingPlane"][0]
            desc = imaging_plane.get("description", "")
            gt_parts = []
            if geometric_transformations.get("translation") is not None:
                gt_parts.append(f"translation: {geometric_transformations['translation']}")
            if geometric_transformations.get("rotation") is not None:
                gt_parts.append(f"rotation: {geometric_transformations['rotation']}")
            if geometric_transformations.get("labeling_origin") is not None:
                gt_parts.append(f"labeling_origin: {geometric_transformations['labeling_origin']}")
            if gt_parts:
                desc = (desc + " " if desc else "") + "Geometric transformations: " + ", ".join(gt_parts)
                imaging_plane["description"] = desc.strip()

        return metadata

    @classmethod
    def get_available_sessions(cls, file_path: FilePath) -> list[str]:
        """
        Get list of available session keys in the file.

        Parameters
        ----------
        file_path : str or Path
            Path to the .mesc file.

        Returns
        -------
        list of str
            List of available session keys.
        """
        Extractor = cls.get_extractor()
        return Extractor.get_available_sessions(file_path=file_path)

    @classmethod
    def get_available_munits(cls, file_path: FilePath, session_name: str = None) -> list[str]:
        """
        Get list of available unit keys in the specified session.

        Parameters
        ----------
        file_path : str or Path
            Path to the .mesc file.
        session_name : str, optional
            Name of the MSession to use (e.g., "MSession_0").
            If None and only one session exists, uses that session automatically.
            If multiple sessions exist, raises an error.

        Returns
        -------
        list of str
            List of available unit keys.
        """
        Extractor = cls.get_extractor()

        # If no session_name provided, only auto-select if there's exactly one session
        if session_name is None:
            available_sessions = cls.get_available_sessions(file_path=file_path)
            if not available_sessions:
                raise ValueError("No sessions found")
            if len(available_sessions) > 1:
                raise ValueError(
                    f"Multiple sessions found: {available_sessions}. " "Please specify 'session_name' to select one."
                )
            session_name = available_sessions[0]

        return Extractor.get_available_munits(file_path=file_path, session_name=session_name)

    @classmethod
    def get_available_channels(cls, file_path: FilePath, session_name: str = None, munit_name: str = None) -> list[str]:
        """
        Get available channels in the specified session/unit combination.

        Parameters
        ----------
        file_path : str or Path
            Path to the .mesc file.
        session_name : str, optional
            Name of the MSession to use (e.g., "MSession_0").
            If None and only one session exists, uses that session automatically.
            If multiple sessions exist, raises an error.
        munit_name : str, optional
            Name of the MUnit within the session (e.g., "MUnit_0").
            If None and only one unit exists in the session, uses that unit automatically.
            If multiple units exist, raises an error.

        Returns
        -------
        list of str
            List of available channel names.
        """
        Extractor = cls.get_extractor()

        # If no session_name provided, only auto-select if there's exactly one session
        if session_name is None:
            available_sessions = cls.get_available_sessions(file_path=file_path)
            if not available_sessions:
                raise ValueError("No sessions found")
            if len(available_sessions) > 1:
                raise ValueError(
                    f"Multiple sessions found: {available_sessions}. " "Please specify 'session_name' to select one."
                )
            session_name = available_sessions[0]

        # If no munit_name provided, only auto-select if there's exactly one unit in the session
        if munit_name is None:
            available_munits = cls.get_available_munits(file_path=file_path, session_name=session_name)
            if not available_munits:
                raise ValueError(f"No units found in session {session_name}")
            if len(available_munits) > 1:
                raise ValueError(
                    f"Multiple units found in session {session_name}: {available_munits}. "
                    "Please specify 'munit_name' to select one."
                )
            munit_name = available_munits[0]

        return Extractor.get_available_channels(file_path=file_path, session_name=session_name, munit_name=munit_name)
