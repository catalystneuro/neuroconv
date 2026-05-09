from typing import Optional

from pydantic import FilePath, validate_call

from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils import DeepDict


def _read_isxd_outer_metadata(file_path) -> dict:
    """
    Read the JSON metadata block stored at the END of an .isxd file.

    The .isxd container places its metadata as a JSON footer rather than a
    header. The on-disk layout, from byte 0 to EOF, is: frame data block, then
    UTF-8 JSON, then a NUL byte, then an 8-byte little-endian uint64 holding
    the JSON length. So to read the JSON we seek 8 bytes from EOF for the
    size, then back size+1+8 bytes for the start of the JSON payload.

    We read this directly from disk (rather than going through the pyisx C
    API) because pyisx's `Movie.get_acquisition_info()` only surfaces a
    curated subset of the JSON, and the fields we need to detect multiplane
    (`hasFrameHeaderFooter`, `timingInfo.numTimes`, and the
    `extraProperties.microscope.multiplane` block) live in the full header
    rather than that subset.
    """
    import json
    import struct

    with open(file_path, "rb") as file_handle:
        file_handle.seek(-8, 2)
        json_length = struct.unpack("<Q", file_handle.read(8))[0]
        file_handle.seek(-(json_length + 1 + 8), 2)
        payload = file_handle.read(json_length).decode("utf-8")
    return json.loads(payload)


def _read_per_frame_efocus(file_path, num_frames_to_read: int) -> list[int]:
    """
    Read the electronic-focus value of each of the first N frames.

    Inscopix microscopes have an electrically tunable lens (ETL) whose focal
    depth is recorded per frame. In single-plane recordings the ETL is parked
    at a fixed depth and every frame's efocus is identical. In multiplane
    recordings the ETL cycles through 2-4 programmed depths between
    consecutive frames, so efocus rotates with a period equal to the plane
    count. The per-frame efocus value is therefore the authoritative signal
    for plane count, more reliable than any configuration flag in the JSON
    header (which records what the user configured in IDPS, not necessarily
    what was acquired).

    Per-frame headers are 2560-uint16 lines that bracket each frame's pixel
    data when the JSON's `hasFrameHeaderFooter` is true. They encode scalar
    metadata into the upper 12 bits of certain pixel positions: `efocus`
    occupies positions FRAME_META_EFOCUS (1270) and FRAME_META_EFOCUS+1 as a
    16-bit little-endian value. Each byte is shifted right by
    `metadataStringLength` (4) to recover the value, per
    `isxMosaicMovieFile.cpp::readFrameMetadata` in isxcore.

    Caller is responsible for confirming `hasFrameHeaderFooter` is true; this
    function will return garbage on files that do not have per-frame headers
    (the C library does not signal an error in that case).
    """
    import ctypes

    import isx
    from isx._internal import IsxMoviePtr, c_api

    # Bind the symbol pyisx leaves unbound. `argtypes` pins the C calling
    # convention; without it ctypes would call with default int promotion and
    # likely segfault when it pushes a pointer through an int slot.
    if not hasattr(c_api.isx_movie_get_frame_header, "argtypes") or not c_api.isx_movie_get_frame_header.argtypes:
        c_api.isx_movie_get_frame_header.argtypes = [
            IsxMoviePtr,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_uint16),
        ]

    # Layout constants from isxcore. NUM_HEADER_VALUES=2560 is the row width;
    # METADATA_BIT_SHIFT=4 is `metadataStringLength`; EFOCUS_OFFSET=1270 is
    # FRAME_META_EFOCUS, the first of two positions holding the 16-bit value.
    NUM_HEADER_VALUES = 2560
    METADATA_BIT_SHIFT = 4
    METADATA_BYTE_MASK = 0xFF
    EFOCUS_OFFSET = 1270

    movie = isx.Movie.read(str(file_path))

    # One ctypes-managed buffer reused across frames; the C function memcpys
    # 2560 uint16 values into it on each call.
    header_buffer = (ctypes.c_uint16 * NUM_HEADER_VALUES)()

    efocus_values: list[int] = []
    for frame_index in range(num_frames_to_read):
        c_api.isx_movie_get_frame_header(movie._ptr, frame_index, header_buffer)
        low_byte = (header_buffer[EFOCUS_OFFSET] >> METADATA_BIT_SHIFT) & METADATA_BYTE_MASK
        high_byte = (header_buffer[EFOCUS_OFFSET + 1] >> METADATA_BIT_SHIFT) & METADATA_BYTE_MASK
        efocus_values.append((high_byte << 8) | low_byte)
    return efocus_values


def _detect_efocus_cycle(efocus_values: list[int]) -> int | None:
    """
    Return the cycle period if the efocus sequence cycles, otherwise None.

    A genuine multiplane recording produces an efocus sequence that repeats
    with a fixed short period N equal to the plane count (e.g. period 3 for
    a 3-plane config). Constant sequences (single-plane) return None.
    Irregular sequences with no period (dropped frames, dual-color channel
    switching, lens settling artifacts) also return None.

    Inscopix's miniscopes do not advertise plane counts above ~4, so we cap
    the search at period 6 to avoid finding spurious long-period matches in
    short sequences.
    """
    if len(set(efocus_values)) <= 1:
        return None
    num_values = len(efocus_values)
    max_period = min(num_values // 2, 6)
    for period in range(2, max_period + 1):
        if all(efocus_values[i] == efocus_values[i + period] for i in range(num_values - period)):
            return period
    return None


def is_file_multiplane(file_path) -> bool:
    """
    Detect whether an .isxd file is a multiplane recording.

    Layered detection:
    1. If the file has per-frame headers (`hasFrameHeaderFooter` true) and
       enough frames for a robust cycle test, sample efocus across the first
       few frames and return whether they cycle. This is authoritative
       because it observes what the ETL actually did during acquisition.
    2. Otherwise, fall back to the JSON `microscope.multiplane.enabled` flag,
       which records what was configured in IDPS but may disagree with the
       recording (older recordings, GUI toggles after configuration, etc.).
    3. If neither signal is available, treat as single-plane and warn so the
       user knows we could not verify.
    """
    import warnings

    metadata = _read_isxd_outer_metadata(file_path)

    if metadata.get("hasFrameHeaderFooter"):
        num_recorded_frames = metadata.get("timingInfo", {}).get("numTimes", 0)
        # Twelve consecutive frames let _detect_efocus_cycle confirm any cycle
        # of period 2-6 with at least one full repetition past the first.
        num_frames_to_check = min(num_recorded_frames, 12)
        if num_frames_to_check >= 4:
            efocus_values = _read_per_frame_efocus(file_path, num_frames_to_check)
            return _detect_efocus_cycle(efocus_values) is not None

    extra_properties = metadata.get("extraProperties") or {}
    multiplane_block = (extra_properties.get("microscope") or {}).get("multiplane")
    if multiplane_block is not None:
        return bool(multiplane_block.get("enabled"))

    warnings.warn(
        f"Could not verify plane count for {file_path}; the file has neither per-frame "
        "headers nor a `microscope.multiplane` block in its JSON metadata. Proceeding as "
        "single-plane. If this is a multiplane recording, the resulting NWB file will be "
        "incorrect. Please report files that hit this path at "
        "https://github.com/catalystneuro/neuroconv/issues so we can extend the detection.",
        stacklevel=2,
    )
    return False


class InscopixImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for Inscopix Imaging Extractor."""

    display_name = "Inscopix Imaging"
    associated_suffixes = (".isxd",)
    info = "Interface for handling Inscopix imaging data."

    @classmethod
    def get_extractor_class(cls):
        from roiextractors import InscopixImagingExtractor

        return InscopixImagingExtractor

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        verbose: bool = False,
        metadata_key: str | None = None,
        **kwargs,
    ):
        """
        Parameters
        ----------
        file_path : FilePath
            Path to the .isxd Inscopix file.
        verbose : bool, optional
            If True, outputs additional information during processing.
        metadata_key : str, optional
            # TODO: improve docstring once #1653 (ophys metadata documentation) is merged
            Metadata key for this interface. When None, defaults to "inscopix_imaging".
        **kwargs : dict, optional
            Additional keyword arguments passed to the parent class.

        Raises
        ------
        NotImplementedError
            If the file is a multiplane recording, which roiextractors cannot
            yet separate into per-plane series.
        """
        if is_file_multiplane(file_path):
            raise NotImplementedError(
                f"Multiplane ISXD file detected at {file_path}.\n"
                f"roiextractors cannot yet separate the per-plane frames; loading as 2D would "
                f"interleave focal planes into one time series.\n"
                f"Track support at https://github.com/catalystneuro/roiextractors/issues "
                f"and the upstream pyisx wrapper gap at https://github.com/inscopix/pyisx/issues/36."
            )

        if metadata_key is None:
            metadata_key = "inscopix_imaging"

        kwargs.setdefault("photon_series_type", "OnePhotonSeries")
        super().__init__(
            file_path=file_path,
            verbose=verbose,
            metadata_key=metadata_key,
            **kwargs,
        )

    def get_metadata(self, *, use_new_metadata_format: bool = False) -> DeepDict:
        """
        Retrieve the metadata for the Inscopix imaging data.

        Parameters
        ----------
        use_new_metadata_format : bool, default: False
            When False, returns the old list-based metadata format (backward compatible).
            When True, returns dict-based metadata with Inscopix provenance.

        Returns
        -------
        DeepDict
            Dictionary containing metadata including device information, imaging plane details,
            photon series configuration, and Inscopix-specific acquisition parameters.
        """
        # Get metadata from parent
        metadata = (
            super().get_metadata()
            if not use_new_metadata_format
            else super().get_metadata(use_new_metadata_format=True)
        )

        extractor = self.imaging_extractor
        extractor_metadata = extractor._get_metadata()

        # Extract individual components
        session_info = extractor_metadata.get("session", {})
        device_info = extractor_metadata.get("device", {})
        subject_info = extractor_metadata.get("subject", {})
        session_start_time = extractor_metadata.get("session_start_time")

        # Session start time
        if session_start_time:
            metadata["NWBFile"]["session_start_time"] = session_start_time

        # Session name and experimenter
        if session_info.get("session_name"):
            metadata["NWBFile"]["session_id"] = session_info["session_name"]
        if session_info.get("experimenter_name"):
            metadata["NWBFile"]["experimenter"] = [session_info["experimenter_name"]]

        # Device information
        if use_new_metadata_format:
            device_entry = {}
            if device_info.get("device_name"):
                device_entry["name"] = device_info["device_name"]
            description_parts = []
            if device_info.get("device_serial_number"):
                description_parts.append(f"Serial: {device_info['device_serial_number']}")
            if device_info.get("acquisition_software_version"):
                description_parts.append(f"Software: {device_info['acquisition_software_version']}")
            if description_parts:
                device_entry["description"] = f"Inscopix Microscope ({', '.join(description_parts)})"
            if device_entry:
                metadata["Devices"] = {self.metadata_key: device_entry}

            # MicroscopySeries
            microscopy_series_entry = {
                "description": "Imaging data acquired with Inscopix nVista.",
            }
            if device_info.get("exposure_time_ms"):
                microscopy_series_entry["exposure_time_ms"] = device_info["exposure_time_ms"]
            if device_info.get("microscope_gain"):
                microscopy_series_entry["microscope_gain"] = device_info["microscope_gain"]
            if device_info.get("microscope_focus"):
                microscopy_series_entry["microscope_focus"] = device_info["microscope_focus"]
            if device_info.get("efocus"):
                microscopy_series_entry["efocus"] = device_info["efocus"]
            if device_info.get("led_power_ex_mw_per_mm2"):
                microscopy_series_entry["led_power_ex_mw_per_mm2"] = device_info["led_power_ex_mw_per_mm2"]
            if device_info.get("led_power_og_mw_per_mm2"):
                microscopy_series_entry["led_power_og_mw_per_mm2"] = device_info["led_power_og_mw_per_mm2"]

            metadata["Ophys"] = {
                "MicroscopySeries": {
                    self.metadata_key: microscopy_series_entry,
                },
            }
        else:
            if device_info:
                device_metadata = metadata["Ophys"]["Device"][0]

                # Update the actual device name
                if device_info.get("device_name"):
                    device_metadata["name"] = device_info["device_name"]

                # Build device description
                microscope_info = []
                if device_info.get("device_serial_number"):
                    microscope_info.append(f"Serial: {device_info['device_serial_number']}")
                if device_info.get("acquisition_software_version"):
                    microscope_info.append(f"Software: {device_info['acquisition_software_version']}")

                if microscope_info:
                    device_metadata["description"] = f"Inscopix Microscope ({', '.join(microscope_info)})"

                # Update imaging plane metadata with acquisition details
                imaging_plane_metadata = metadata["Ophys"]["ImagingPlane"][0]

                # Update imaging plane device reference to match the actual device name
                if device_info.get("device_name"):
                    imaging_plane_metadata["device"] = device_info["device_name"]

                acquisition_details = []
                if device_info.get("exposure_time_ms"):
                    acquisition_details.append(f"Exposure Time (ms): {device_info['exposure_time_ms']}")
                if device_info.get("microscope_gain"):
                    acquisition_details.append(f"Gain: {device_info['microscope_gain']}")
                if device_info.get("microscope_focus"):
                    acquisition_details.append(f"Focus: {device_info['microscope_focus']}")
                if device_info.get("efocus"):
                    acquisition_details.append(f"eFocus: {device_info['efocus']}")
                if device_info.get("led_power_ex_mw_per_mm2"):
                    acquisition_details.append(f"EX LED Power (mw/mm^2): {device_info['led_power_ex_mw_per_mm2']}")
                if device_info.get("led_power_og_mw_per_mm2"):
                    acquisition_details.append(f"OG LED Power (mw/mm^2): {device_info['led_power_og_mw_per_mm2']}")

                if acquisition_details:
                    current_description = imaging_plane_metadata.get(
                        "description", "The plane or volume being imaged by the microscope."
                    )
                    imaging_plane_metadata["description"] = f"{current_description} ({'; '.join(acquisition_details)})"

        # Subject information
        subject_metadata = {}
        has_any_subject_data = False

        # Subject ID
        if subject_info and subject_info.get("animal_id"):
            subject_metadata["subject_id"] = subject_info["animal_id"]
            has_any_subject_data = True

        species_value = None
        strain_value = None

        if subject_info and subject_info.get("species"):
            species_raw = subject_info["species"]
            # If it contains genotype info or matches NWB format, put it in species; otherwise strain
            # e.g., "CaMKIICre"
            if " " in species_raw and species_raw[0].isupper() and species_raw.split()[1][0].islower():
                species_value = species_raw
            else:
                strain_value = species_raw

            if species_value:
                subject_metadata["species"] = species_value
                has_any_subject_data = True
            if strain_value:
                subject_metadata["strain"] = strain_value
                has_any_subject_data = True

        # Sex mapping
        sex_mapping = {"m": "M", "male": "M", "f": "F", "female": "F", "u": "U", "unknown": "U"}
        if subject_info and subject_info.get("sex"):
            mapped_sex = sex_mapping.get(subject_info["sex"].lower(), "U")
            subject_metadata["sex"] = mapped_sex
            has_any_subject_data = True

        # Additional subject fields
        if subject_info:
            if subject_info.get("description"):
                subject_metadata["description"] = subject_info["description"]
                has_any_subject_data = True
            if subject_info.get("date_of_birth"):
                subject_metadata["date_of_birth"] = subject_info["date_of_birth"]
                has_any_subject_data = True
            if subject_info.get("weight") and subject_info["weight"] > 0:
                subject_metadata["weight"] = str(subject_info["weight"])
                has_any_subject_data = True

        # Add Subject if we have ANY subject information, filling required fields with defaults
        if has_any_subject_data:
            if "subject_id" not in subject_metadata:
                subject_metadata["subject_id"] = "Unknown"
            if "species" not in subject_metadata:
                subject_metadata["species"] = "Unknown species"
            if "sex" not in subject_metadata:
                subject_metadata["sex"] = "U"

            if "Subject" in metadata:
                metadata["Subject"].update(subject_metadata)
            else:
                metadata["Subject"] = subject_metadata

        return metadata

    def add_to_nwbfile(
        self,
        nwbfile,
        metadata: Optional[dict] = None,
        **kwargs,
    ):
        """
        Add the Inscopix data to the NWB file.

        Parameters
        ----------
        nwbfile : NWBFile
            NWB file to add the data to.
        metadata : dict, optional
            Metadata dictionary. If None, will be generated dynamically with OnePhotonSeries.
        **kwargs
            Additional keyword arguments passed to the parent add_to_nwbfile method.

        # TODO: add logic for determining whether the microscope is `nVista 2P` and change photon_series_type to TwoPhotonSeries accordingly.
        """
        kwargs["photon_series_type"] = "OnePhotonSeries"
        # TODO: add logic for determining whether the microscope is `nVista 2P` and change photon_series_type to TwoPhotonSeries accordingly.
        super().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, **kwargs)
