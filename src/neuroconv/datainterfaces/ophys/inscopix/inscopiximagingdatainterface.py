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
    curated subset of the JSON, and the `extraProperties.microscope.multiplane`
    block we use to detect multiplane recordings lives in the full metadata
    block rather than that subset.
    """
    import json
    import struct

    with open(file_path, "rb") as file_handle:
        file_handle.seek(-8, 2)
        json_length = struct.unpack("<Q", file_handle.read(8))[0]
        file_handle.seek(-(json_length + 1 + 8), 2)
        payload = file_handle.read(json_length).decode("utf-8")
    return json.loads(payload)


def is_file_multiplane(file_path) -> bool:
    """
    Detect whether an .isxd file is a multiplane recording.

    Reads the ``microscope.multiplane.enabled`` flag from the JSON metadata
    block at the end of the file. This flag is written by the Inscopix
    acquisition software (IDPS) and records whether multiplane mode was enabled
    for the recording. When the ``microscope.multiplane`` block is absent
    (older files, or files rewritten by ``isx.Movie.write``, which drops the
    whole ``extraProperties`` tree) we cannot tell, so we assume single-plane.

    This trusts the acquisition configuration rather than reading the per-frame
    electronic-focus (efocus) values directly. For raw acquisition files the
    flag and the efocus cycling agree by construction, so the flag is
    sufficient. A per-frame efocus reader (which would additionally catch
    derived/processed files whose inherited flag no longer matches their actual
    frames) was designed and deliberately left out, since that case can only
    arise from closed IDPS processing and could not be shown to be a real
    input. See the "Inscopix multiplane detection" vault note for the efocus
    design (both the byte-read and ctypes-binding variants) and the full
    reasoning.
    """
    import warnings

    metadata = _read_isxd_outer_metadata(file_path)
    microscope = (metadata.get("extraProperties") or {}).get("microscope") or {}
    multiplane_block = microscope.get("multiplane")
    if multiplane_block is not None:
        return bool(multiplane_block.get("enabled"))

    warnings.warn(
        f"Could not determine plane count for {file_path}: the file has no "
        "`microscope.multiplane` block in its JSON metadata (its extraProperties may have "
        "been stripped, e.g. by isx.Movie.write). Proceeding as single-plane. If this is a "
        "multiplane recording the resulting NWB file will be incorrect; please report such "
        "files at https://github.com/catalystneuro/neuroconv/issues.",
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
