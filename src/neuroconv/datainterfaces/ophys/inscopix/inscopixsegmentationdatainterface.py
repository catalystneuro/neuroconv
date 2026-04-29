import warnings

from pydantic import FilePath

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface
from ....utils import DeepDict


class InscopixSegmentationInterface(BaseSegmentationExtractorInterface):
    """Conversion interface for Inscopix segmentation data."""

    display_name = "Inscopix Segmentation"
    associated_suffixes = (".isxd",)
    info = "Interface for handling Inscopix segmentation."

    @classmethod
    def get_extractor_class(cls):
        from roiextractors import InscopixSegmentationExtractor

        return InscopixSegmentationExtractor

    def __init__(
        self,
        file_path: FilePath,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        verbose: bool = False,
        metadata_key: str | None = None,
    ):
        """
        Parameters
        ----------
        file_path : FilePath
            Path to the .isxd Inscopix file.
        verbose : bool, optional
            If True, outputs additional information during processing.
        metadata_key : str, optional
            Metadata key for this interface. When None, defaults to "inscopix_segmentation".
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
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
                f"Passing arguments positionally to InscopixSegmentationInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            verbose = positional_values.get("verbose", verbose)

        if metadata_key is None:
            metadata_key = "inscopix_segmentation"

        super().__init__(file_path=file_path, verbose=verbose, metadata_key=metadata_key)

    def get_metadata(self, *, use_new_metadata_format: bool = False) -> DeepDict:
        """
        Retrieve the metadata for the Inscopix segmentation data.

        Parameters
        ----------
        use_new_metadata_format : bool, default: False
            When False, returns the old list-based metadata format (backward compatible).
            When True, returns dict-based metadata with Inscopix provenance keyed by
            ``metadata_key`` under ``Devices`` and ``Ophys.PlaneSegmentations``.

        Returns
        -------
        DeepDict
            Dictionary containing metadata including device information, imaging plane details,
            photon series configuration, and Inscopix-specific acquisition parameters.

        TODO: Determine the excitation and emission wavelengths. For each Inscopix microscope they are fixed (e.g. NVista has an emission: 535 and excitation: 475).
        We currently do not know how to map the names returned by get_acquisition_info['MicroscopeType']
        to the actual microscope models, as we do not have example data for each type.
        See related issue: https://github.com/inscopix/pyisx/issues/62

        """
        metadata = (
            super().get_metadata()
            if not use_new_metadata_format
            else super().get_metadata(use_new_metadata_format=True)
        )
        extractor = self.segmentation_extractor

        # Get all metadata from extractor using the consolidated method
        extractor_metadata = extractor._get_metadata()

        # Extract individual components
        session_info = extractor_metadata.get("session", {})
        device_info = extractor_metadata.get("device", {})
        subject_info = extractor_metadata.get("subject", {})
        analysis_info = extractor_metadata.get("analysis", {})
        probe_info = extractor_metadata.get("probe", {})
        session_start_time = extractor_metadata.get("session_start_time")

        # Session start time (shared)
        if session_start_time:
            metadata["NWBFile"]["session_start_time"] = session_start_time

        # Experimenter (shared)
        if session_info.get("experimenter_name"):
            metadata["NWBFile"]["experimenter"] = [session_info["experimenter_name"]]

        if use_new_metadata_format:
            # Session id (new-format convention, matches sibling imaging interface)
            if session_info.get("session_name"):
                metadata["NWBFile"]["session_id"] = session_info["session_name"]

            # Devices
            device_entry = {}
            if device_info.get("device_name"):
                device_entry["name"] = device_info["device_name"]
            desc_parts = []
            if device_info.get("device_serial_number"):
                desc_parts.append(f"Serial: {device_info['device_serial_number']}")
            if device_info.get("acquisition_software_version"):
                desc_parts.append(f"Software: {device_info['acquisition_software_version']}")
            for field in [
                "Probe Diameter (mm)",
                "Probe Flip",
                "Probe Length (mm)",
                "Probe Pitch",
                "Probe Rotation (degrees)",
                "Probe Type",
            ]:
                value = probe_info.get(field) if probe_info else None
                if value is not None:
                    desc_parts.append(f"{field}: {value}")
            if desc_parts:
                device_entry["description"] = f"Inscopix Microscope ({', '.join(desc_parts)})"
            if device_entry:
                metadata["Devices"] = {self.metadata_key: device_entry}

            # PlaneSegmentations
            plane_segmentation_description = "Inscopix cell segmentation"
            if analysis_info.get("cell_identification_method"):
                plane_segmentation_description += f" using {analysis_info['cell_identification_method']}"
            if analysis_info.get("trace_units"):
                plane_segmentation_description += f" with traces in {analysis_info['trace_units']}"

            metadata["Ophys"] = {
                "PlaneSegmentations": {
                    self.metadata_key: {"description": plane_segmentation_description},
                },
            }
        elif session_info.get("session_name"):
            # Old-format session_description (existing behavior preserved)
            session_desc = f"Session: {session_info['session_name']}"
            if subject_info and subject_info.get("description"):
                session_desc += f"; {subject_info['description']}"
            metadata["NWBFile"]["session_description"] = session_desc

        # Device information (old format only; new-format device built above)
        if not use_new_metadata_format and device_info:
            device_metadata = metadata["Ophys"]["Device"][0]

            # Update the actual device name
            if device_info.get("device_name"):
                device_metadata["name"] = device_info["device_name"]

            # Build device description
            device_desc_parts = []
            if device_info.get("device_name"):
                device_desc_parts.append(f"Inscopix {device_info['device_name']}")
            if device_info.get("device_serial_number"):
                device_desc_parts.append(f"SerialNumber: {device_info['device_serial_number']}")
            if device_info.get("acquisition_software_version"):
                device_desc_parts.append(f"Software version {device_info['acquisition_software_version']}")

            # Add probe information specific to segmentation
            if probe_info:
                for field in [
                    "Probe Diameter (mm)",
                    "Probe Flip",
                    "Probe Length (mm)",
                    "Probe Pitch",
                    "Probe Rotation (degrees)",
                    "Probe Type",
                ]:
                    value = probe_info.get(field)
                    if value is not None:
                        device_desc_parts.append(f"{field}: {value}")

            if device_desc_parts:
                device_metadata["description"] = "; ".join(device_desc_parts)

            # Update imaging plane metadata
            imaging_plane_metadata = metadata["Ophys"]["ImagingPlane"][0]

            # Update imaging plane device reference to match the actual device name
            if device_info.get("device_name"):
                imaging_plane_metadata["device"] = device_info["device_name"]

            # Build imaging plane description
            plane_desc = "Inscopix imaging plane"
            if device_info.get("field_of_view_pixels"):
                fov = device_info["field_of_view_pixels"]
                plane_desc += f" with field of view {fov[1]}x{fov[0]} pixels"

            desc_parts = [plane_desc]
            if device_info.get("microscope_focus"):
                desc_parts.append(f"Focus: {device_info['microscope_focus']} µm")
            if device_info.get("exposure_time_ms"):
                desc_parts.append(f"Exposure: {device_info['exposure_time_ms']} ms")
            if device_info.get("microscope_gain"):
                desc_parts.append(f"Gain: {device_info['microscope_gain']}")

            imaging_plane_metadata["description"] = "; ".join(desc_parts)

            # Sampling frequency
            sampling_frequency = extractor.get_sampling_frequency()
            imaging_plane_metadata["imaging_rate"] = sampling_frequency

            # Optical channel
            optical_channel = {
                "name": "OpticalChannelDefault",
                "description": "Inscopix optical channel",
                "emission_lambda": float("nan"),
            }
            if device_info.get("channel"):
                channel = device_info["channel"]
                optical_channel["name"] = f"OpticalChannel{channel.capitalize()}"
                optical_channel["description"] = f"Inscopix {channel} channel"

            # LED power (segmentation uses different field name)
            if device_info.get("led_power_1_mw_per_mm2"):
                led_power = device_info["led_power_1_mw_per_mm2"]
                optical_channel["description"] += f" (LED power: {led_power} mW/mm²)"

            imaging_plane_metadata["optical_channel"] = [optical_channel]

        # Image segmentation description (old format only)
        if not use_new_metadata_format:
            segmentation_desc = "Inscopix cell segmentation"
            if analysis_info and analysis_info.get("cell_identification_method"):
                segmentation_desc += f" using {analysis_info['cell_identification_method']}"
            if analysis_info and analysis_info.get("trace_units"):
                segmentation_desc += f" with traces in {analysis_info['trace_units']}"

            metadata["Ophys"]["ImageSegmentation"]["description"] = segmentation_desc

        # Subject metadata
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
            # If it contains genotype info or doesn't match format, put it in strain instead
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

        # Optional subject fields
        if subject_info:
            if subject_info.get("description"):
                subject_metadata["description"] = subject_info["description"]
                has_any_subject_data = True
            if subject_info.get("date_of_birth"):
                subject_metadata["date_of_birth"] = subject_info["date_of_birth"]
                has_any_subject_data = True
            if subject_info.get("weight") and subject_info["weight"] > 0:
                subject_metadata["weight"] = subject_info["weight"]
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
