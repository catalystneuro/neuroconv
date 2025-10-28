from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from pydantic import DirectoryPath, FilePath, validate_call
from pynwb import NWBFile

from .miniscopeimagingdatainterface import (
    MiniscopeImagingInterface,
    _MiniscopeMultiRecordingInterface,
)
from ... import MiniscopeBehaviorInterface
from ....nwbconverter import NWBConverter
from ....tools import get_package
from ....utils import get_json_schema_from_method_signature


class MiniscopeConverter(NWBConverter):
    """Bundle Miniscope imaging and optional behavior recordings into a single NWB conversion."""

    display_name = "Miniscope Imaging and Video"
    keywords = MiniscopeImagingInterface.keywords + MiniscopeBehaviorInterface.keywords
    associated_suffixes = MiniscopeImagingInterface.associated_suffixes + MiniscopeBehaviorInterface.associated_suffixes
    info = "Converter for handling both imaging and video recordings from Miniscope."

    @classmethod
    def get_source_schema(cls):
        source_schema = get_json_schema_from_method_signature(cls)
        source_schema["properties"]["folder_path"]["description"] = "The path to the main Miniscope folder."
        source_schema["properties"]["user_configuration_file_path"] = {
            "type": "string",
            "format": "file-path",
            "description": (
                "Path to the Miniscope acquisition User Config JSON file (named 'UserConfigFile.json' in the Miniscope"
                " documentation and source code). When provided, the converter uses this configuration to interpret the"
                " folder hierarchy and device names instead of relying on a fixed directory structure."
            ),
            "default": None,
        }
        return source_schema

    @validate_call
    def __init__(
        self,
        folder_path: DirectoryPath,
        user_configuration_file_path: FilePath | None = None,
        verbose: bool = False,
    ):
        """Instantiate Miniscope imaging (and optional behavior) interfaces.

        Parameters
        ----------
        folder_path : DirectoryPath
            **Root data directory** containing the Miniscope acquisition data. This should be the base directory
            where the configured directory structure (e.g., researcher/experiment/animal/date/time) begins.

            - With config file: The top-level directory containing the hierarchy defined by 'directoryStructure'
            - Without config file (legacy): The directory containing timestamp subfolders with Miniscope/ folders

            IMPORTANT: The 'dataDirectory' field in the User Config file is ignored. Always pass the actual
            data root directory as folder_path.
        user_configuration_file_path : FilePath, optional
            Path to the Miniscope "User Config" JSON file (the Miniscope documentation and source code refer to
            this artifact as ``UserConfigFile.json``). When provided, the converter uses the configuration to
            discover Miniscope device folders and session hierarchy, supporting multiple simultaneous Miniscopes
            and custom directory layouts. If omitted, the converter falls back to the legacy layout (see Notes).
        verbose : bool, default: False
            Controls verbosity.

        Notes
        -----
        The Miniscope acquisition software saves a "User Config" JSON that includes:

        - ``dataDirectory`` and ``directoryStructure``: ordered keys (e.g., researcher, experiment, animal,
          date, time) used to build the on-disk folder hierarchy.
        - ``devices[miniscopes]``: mapping of Miniscope device names (e.g., ``"ACC_miniscope2"``) to their
          acquisition parameters.

        Example 1 - Dual Miniscope with 5-level hierarchy::

            {
                "dataDirectory": "./dual_miniscope_data",
                "directoryStructure": [
                    "researcherName",
                    "experimentName",
                    "animalName",
                    "date",
                    "time"
                ],
                "researcherName": "researcher_name",
                "experimentName": "experiment_name",
                "animalName": "animal_name",
                "devices": {
                    "miniscopes": {
                        "ACC_miniscope2": {...},
                        "HPC_miniscope1": {...}
                    }
                }
            }

        This produces a folder tree such as::

            dual_miniscope_data/
            ├── researcher_name/
            │   └── experiment_name/
            │       └── animal_name/
            │           └── 2025_06_12/
            │               ├── 15_15_04/
            │               │   ├── ACC_miniscope2/
            │               │   │   ├── 0.avi
            │               │   │   ├── 1.avi
            │               │   │   ├── 2.avi
            │               │   │   ├── metaData.json
            │               │   │   └── timeStamps.csv
            │               │   ├── HPC_miniscope1/
            │               │   │   ├── 0.avi
            │               │   │   ├── 1.avi
            │               │   │   ├── 2.avi
            │               │   │   ├── metaData.json
            │               │   │   └── timeStamps.csv
            │               │   └── metaData.json
            │               └── 15_26_31/
            │                   ├── ACC_miniscope2/
            │                   │   ├── 0.avi
            │                   │   ├── 1.avi
            │                   │   ├── metaData.json
            │                   │   └── timeStamps.csv
            │                   ├── HPC_miniscope1/
            │                   │   ├── 0.avi
            │                   │   ├── 1.avi
            │                   │   ├── metaData.json
            │                   │   └── timeStamps.csv
            │                   └── metaData.json

        Example 2 - Single Miniscope with 3-level hierarchy::

            {
                "dataDirectory": "./miniscope_recordings",
                "directoryStructure": [
                    "animalName",
                    "date",
                    "time"
                ],
                "animalName": "mouse_001",
                "devices": {
                    "miniscopes": {
                        "Miniscope": {...}
                    }
                }
            }

        Which yields::

            miniscope_recordings/
            └── mouse_001/
                └── 2022_09_19/
                    └── 09_18_41/
                        ├── Miniscope/
                        │   ├── 0.avi
                        │   ├── 1.avi
                        │   ├── 2.avi
                        │   ├── metaData.json
                        │   └── timeStamps.csv
                        └── metaData.json

        The converter walks the directory structure, creating one imaging interface per Miniscope device and
        preserving their individual timestamps. Behavior video is added only if ``BehavCam_`` folders (with
        metadata) are present. For devices recorded multiple times, each timestamp folder is instantiated as a
        separate interface labeled ``SegmentXX`` (with zero padding based on the total number of segments) so
        repeated recordings remain distinct while sharing a common device definition.

        **Backwards compatibility:** If ``user_configuration_file_path`` is not provided, the converter falls back to the
        original "Tye Lab" layout that expects timestamp subfolders with ``Miniscope/`` and optional ``BehavCam_*/``
        directories (each holding their own ``metaData.json`` and ``timeStamps.csv`` files)::

            main_folder/
            ├── timestamp_one/
            │   ├── Miniscope/
            │   │   ├── 0.avi
            │   │   ├── 1.avi
            │   │   ├── metaData.json
            │   │   └── timeStamps.csv
            │   ├── BehavCam_*/
            │   │   ├── 0.avi
            │   │   ├── metaData.json
            │   │   └── timeStamps.csv
            │   └── metaData.json
            └── timestamp_two/
                └── ...

        Use the configuration file whenever possible to describe other layouts explicitly.
        """
        self.verbose = verbose
        self._folder_path = Path(folder_path)
        self.data_interface_objects: dict[str, object] = {}

        if user_configuration_file_path is not None:
            # Load user configuration
            config_path = Path(user_configuration_file_path)
            with config_path.open() as f:
                user_config = json.load(f)

            # Extract device names from configuration
            miniscope_devices = user_config.get("devices", {}).get("miniscopes", {})
            if not miniscope_devices:
                raise ValueError("'devices[miniscopes]' is missing from the provided User Config file.")
            device_names = list(miniscope_devices.keys())

            # Use folder_path as the base data directory
            base_path = self._folder_path

            # Discover all session folders
            # Build virtual path pattern with {wildcards} for unconstrained levels
            directory_structure = user_config.get("directoryStructure", [])
            path_components = []
            for key in directory_structure:
                expected_value = user_config.get(key)
                if isinstance(expected_value, str) and expected_value:
                    path_components.append(expected_value)  # Exact folder name
                else:
                    path_components.append(f"{{{key}}}")  # Wildcard: {animalName}, {date}, etc.

            virtual_path_pattern = "/".join(path_components) if path_components else ""

            session_folders = self._resolve_folder_path_structure(
                base_path=base_path,
                virtual_path_pattern=virtual_path_pattern,
            )

            # Sort sessions naturally
            natsort = get_package(package_name="natsort", installation_instructions="pip install natsort")
            session_folders = natsort.natsorted(session_folders, key=lambda path: path.as_posix())

            # For each session, find device folders and create interfaces
            device_folders_by_device = {device_name: [] for device_name in device_names}
            for session_folder in session_folders:
                device_folders_in_session = self._find_device_folders_in_session(
                    session_folder=session_folder,
                    device_names=device_names,
                )
                for device_name, device_folder in device_folders_in_session.items():
                    device_folders_by_device[device_name].append(device_folder)

            # Build interfaces from discovered device folders
            imaging_interfaces = self._build_imaging_interfaces_from_device_folders(
                device_folders_by_device=device_folders_by_device,
            )
            if not imaging_interfaces:
                raise ValueError(
                    "No Miniscope imaging folders were discovered using the provided 'user_configuration_file_path'."
                )
            self.data_interface_objects.update(imaging_interfaces)
        else:
            # Legacy mode: use _MiniscopeMultiRecordingInterface for backwards compatibility
            default_interface = _MiniscopeMultiRecordingInterface(folder_path=folder_path)
            default_metadata = default_interface.get_metadata()
            device_metadata = default_metadata["Ophys"]["Device"][0]
            device_name = device_metadata.get("name", "Miniscope")
            sanitized_device_name = device_name.replace(" ", "_")
            default_interface._miniscope_device_label = sanitized_device_name
            default_interface._device_name_from_metadata = device_name
            default_interface._device_metadata_index = 0
            default_interface._imaging_plane_metadata_index = 0
            self.data_interface_objects[f"MiniscopeImaging/{sanitized_device_name}"] = default_interface

        # Attempt to initialize the behavior interface; skip gracefully if the expected files are absent.
        try:
            self.data_interface_objects["MiniscopeBehavCam"] = MiniscopeBehaviorInterface(folder_path=folder_path)
        except AssertionError:
            if self.verbose:
                print(
                    "Miniscope behavior videos were not found under the provided folder and will be omitted from conversion."
                )

    def get_conversion_options_schema(self) -> dict:
        """Allow standard stub options alongside per-interface schemas."""

        schema = super().get_conversion_options_schema()

        # Add top-level stub options for converter-wide settings
        schema["properties"]["stub_test"] = {
            "type": "boolean",
            "default": False,
            "description": "If True, limit each Miniscope segment to 'stub_samples' samples during conversion.",
        }
        schema["properties"]["stub_samples"] = {
            "type": "integer",
            "minimum": 1,
            "default": 100,
            "description": "Number of samples (frames) to include when 'stub_test' is enabled.",
        }
        schema["properties"]["stub_frames"] = {
            "type": "integer",
            "minimum": 1,
            "default": 100,
            "description": "Deprecated. Use 'stub_samples' instead. Number of frames to include when 'stub_test' is enabled.",
        }

        # Note: Individual interfaces inherit stub_samples from BaseImagingExtractorInterface
        # which automatically infers it from the add_to_nwbfile method signature

        return schema

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata,
        conversion_options: dict | None = None,
        stub_test: bool = False,
        stub_frames: int | None = None,
        stub_samples: int = 100,
    ):
        """Add Miniscope interfaces to the provided NWBFile."""
        import warnings

        # Handle deprecation of stub_frames
        if stub_frames is not None:
            warnings.warn(
                "The 'stub_frames' parameter is deprecated and will be removed on or after February 2026. "
                "Use 'stub_samples' instead.",
                FutureWarning,
                stacklevel=2,
            )
            stub_samples = stub_frames

        imaging_interface_keys = [key for key in self.data_interface_objects if key.startswith("MiniscopeImaging")]

        conversion_options = conversion_options.copy() if conversion_options else {}
        stub_test = conversion_options.pop("stub_test", stub_test)
        stub_samples = conversion_options.pop("stub_samples", conversion_options.pop("stub_frames", stub_samples))

        global_ophys_metadata = metadata.get("Ophys", {}) if metadata else {}
        device_list = list(global_ophys_metadata.get("Device", [])) if global_ophys_metadata else []
        imaging_plane_list = list(global_ophys_metadata.get("ImagingPlane", [])) if global_ophys_metadata else []

        device_overrides = {}
        for device_entry in device_list:
            key = device_entry.get("deviceID")
            if key is not None:
                device_overrides[key] = device_entry
            name_key = device_entry.get("name")
            if name_key:
                device_overrides.setdefault(name_key, device_entry)
                sanitized_name_key = name_key.replace(" ", "_")
                device_overrides.setdefault(sanitized_name_key, device_entry)

        imaging_plane_overrides = {}
        for imaging_plane_entry in imaging_plane_list:
            name_key = imaging_plane_entry.get("name")
            if name_key:
                imaging_plane_overrides[name_key] = imaging_plane_entry
            device_ref = imaging_plane_entry.get("device")
            if isinstance(device_ref, str):
                canonical_name = f"ImagingPlane{device_ref.replace(' ', '_')}"
                imaging_plane_overrides.setdefault(canonical_name, imaging_plane_entry)

        interface_entries: list[dict] = []
        for interface_key in imaging_interface_keys:
            interface = self.data_interface_objects[interface_key]
            interface_metadata = interface.get_metadata()
            session_start_time = interface_metadata.get("NWBFile", {}).get("session_start_time")
            interface_entries.append(
                dict(
                    key=interface_key,
                    interface=interface,
                    metadata=interface_metadata,
                    session_start_time=session_start_time,
                )
            )

        for entry in interface_entries:
            interface = entry["interface"]
            interface_metadata = entry["metadata"]

            device_metadata = interface_metadata["Ophys"]["Device"][0]
            original_device_name = getattr(interface, "_device_name_from_metadata", device_metadata.get("name"))
            device_id = device_metadata.get("deviceID")
            device_index = getattr(interface, "_device_metadata_index", None)

            device_override = None
            if device_index is not None and 0 <= device_index < len(device_list):
                device_override = deepcopy(device_list[device_index])
            if device_override is None:
                for candidate in (device_id, original_device_name, device_metadata.get("name")):
                    if candidate in device_overrides:
                        device_override = device_overrides[candidate]
                        break
            if device_override:
                device_metadata.update(device_override)

            device_name = device_metadata.get("name", original_device_name)
            if not device_name:
                device_name = entry["key"].split("/", 1)[-1]

            sanitized_device_label = device_name.replace(" ", "_")
            interface._miniscope_device_label = sanitized_device_label
            interface._device_name_from_metadata = device_name
            entry["sanitized_device_label"] = sanitized_device_label

            segment_label = getattr(interface, "_segment_label", None)
            entry["segment_label"] = segment_label

            imaging_plane_metadata = interface_metadata["Ophys"]["ImagingPlane"][0]
            imaging_plane_index = getattr(interface, "_imaging_plane_metadata_index", None)
            imaging_plane_key = imaging_plane_metadata.get("name")
            override_imaging_plane = None
            if imaging_plane_index is not None and 0 <= imaging_plane_index < len(imaging_plane_list):
                override_imaging_plane = deepcopy(imaging_plane_list[imaging_plane_index])
            if override_imaging_plane is None:
                override_imaging_plane = imaging_plane_overrides.get(imaging_plane_key)
            if override_imaging_plane:
                imaging_plane_metadata.update(override_imaging_plane)

            imaging_plane_name = f"ImagingPlane{sanitized_device_label}"
            imaging_plane_metadata.update(name=imaging_plane_name, device=device_name)

            if "OnePhotonSeries" in interface_metadata["Ophys"]:
                one_photon_metadata = interface_metadata["Ophys"]["OnePhotonSeries"][0]
                one_photon_series_name = (
                    f"OnePhotonSeries{sanitized_device_label}{segment_label}"
                    if segment_label
                    else f"OnePhotonSeries{sanitized_device_label}"
                )
                one_photon_metadata.update(name=one_photon_series_name, imaging_plane=imaging_plane_name)

        start_times = []
        for entry in interface_entries:
            start_time = entry["session_start_time"]
            if isinstance(start_time, datetime):
                start_times.append(start_time)
            else:
                entry["session_start_time"] = None

        if start_times:
            base_time = min(start_times)
            for entry in interface_entries:
                start_time = entry["session_start_time"]
                if start_time is None:
                    continue
                offset = (start_time - base_time).total_seconds()
                if offset:
                    entry["interface"].set_aligned_starting_time(offset)

        for entry in interface_entries:
            interface_key = entry["key"]
            interface = entry["interface"]
            interface_metadata = entry["metadata"]

            interface_options = conversion_options.get(interface_key, {})
            interface_stub_test = interface_options.get("stub_test", stub_test)
            interface_stub_frames = interface_options.get(
                "stub_frames", interface_options.get("stub_samples", stub_samples)
            )
            passthrough_options = {
                key: value
                for key, value in interface_options.items()
                if key not in {"stub_test", "stub_frames", "stub_samples"}
            }

            interface.add_to_nwbfile(
                nwbfile=nwbfile,
                metadata=interface_metadata,
                stub_test=interface_stub_test,
                stub_frames=interface_stub_frames,
                **passthrough_options,
            )

        behavior_interface = self.data_interface_objects.get("MiniscopeBehavCam")
        if behavior_interface is not None:
            behavior_metadata = deepcopy(metadata)
            behavior_options = conversion_options.get("MiniscopeBehavCam", {})
            behavior_interface.add_to_nwbfile(
                nwbfile=nwbfile,
                metadata=behavior_metadata,
                **behavior_options,
            )

    def run_conversion(
        self,
        nwbfile_path: str | None = None,
        nwbfile: NWBFile | None = None,
        metadata: dict | None = None,
        overwrite: bool = False,
        stub_test: bool = False,
        stub_frames: int | None = None,
        stub_samples: int = 100,
        **kwargs,
    ) -> None:
        """
        Run the NWB conversion process for the instantiated data interfaces.

        Parameters
        ----------
        nwbfile_path : str, optional
            Path where the NWBFile will be written. If None, the file is handled in-memory.
        nwbfile : NWBFile, optional
            An in-memory NWBFile object to be written to the file. If None, a new NWBFile is created.
        metadata : dict, optional
            Metadata dictionary with information to create the NWBFile. If None, metadata is auto-generated.
        overwrite : bool, optional
            If True, overwrites the existing NWBFile at `nwbfile_path`. If False (default), data is appended.
        stub_test : bool, optional
            If True, only a subset of the data (up to `stub_samples`) is written for testing purposes,
            by default False.
        stub_frames : int, optional
            Deprecated. Use `stub_samples` instead.
        stub_samples : int, optional
            The number of samples (frames) to include in the subset if `stub_test` is True, by default 100.
        **kwargs
            Additional keyword arguments passed to the parent NWBConverter.run_conversion method.
        """
        import warnings

        # Handle deprecation of stub_frames
        if stub_frames is not None:
            warnings.warn(
                "The 'stub_frames' parameter is deprecated and will be removed on or after February 2026. "
                "Use 'stub_samples' instead.",
                FutureWarning,
                stacklevel=2,
            )
            stub_samples = stub_frames

        # Get existing conversion_options or create empty dict
        conversion_options = kwargs.pop("conversion_options", {})

        # Apply stub_test and stub_frames to all imaging interfaces
        # Note: Using stub_frames for schema compatibility; the interface converts to stub_samples internally
        imaging_interface_keys = [key for key in self.data_interface_objects if key.startswith("MiniscopeImaging")]
        for interface_key in imaging_interface_keys:
            if interface_key not in conversion_options:
                conversion_options[interface_key] = {}
            conversion_options[interface_key].setdefault("stub_test", stub_test)
            conversion_options[interface_key].setdefault("stub_frames", stub_samples)

        super().run_conversion(
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            metadata=metadata,
            overwrite=overwrite,
            conversion_options=conversion_options,
            **kwargs,
        )

    def _find_device_folders_in_session(
        self,
        session_folder: Path,
        device_names: list[str],
    ) -> dict[str, Path]:
        """Find device-specific folders within a session folder.

        Parameters
        ----------
        session_folder : Path
            The session folder to search in.
        device_names : list[str]
            List of device names to look for.

        Returns
        -------
        dict[str, Path]
            Mapping of device_name to device_folder path for devices found in this session.
            Devices not found in this session are omitted (partial recordings supported).
        """
        device_folders = {}

        if not session_folder.exists():
            return device_folders

        for device_name in device_names:
            sanitized_device_name = device_name.replace(" ", "_")
            candidate_names = [sanitized_device_name]
            if sanitized_device_name != device_name:
                candidate_names.append(device_name)

            for candidate_name in candidate_names:
                candidate_path = session_folder / candidate_name
                if candidate_path.exists():
                    device_folders[device_name] = candidate_path
                    break

        return device_folders

    def _build_imaging_interfaces_from_device_folders(
        self,
        *,
        device_folders_by_device: dict[str, list[Path]],
    ) -> dict[str, MiniscopeImagingInterface]:
        """Instantiate imaging interfaces for each Miniscope device/segment discovered on disk."""

        natsort = get_package(package_name="natsort", installation_instructions="pip install natsort")

        imaging_interfaces: dict[str, MiniscopeImagingInterface] = {}
        for device_index, (device_name, folder_paths) in enumerate(device_folders_by_device.items()):
            if not folder_paths:
                raise FileNotFoundError(
                    f"No directories matching Miniscope device '{device_name}' were found under '{self._folder_path}'."
                )

            sorted_folders = natsort.natsorted(folder_paths, key=lambda path: path.as_posix())
            num_segments = len(sorted_folders)
            padding_width = max(len(str(num_segments - 1)) if num_segments > 1 else 1, 2)

            for segment_index, folder_path in enumerate(sorted_folders):
                avi_paths = [
                    path
                    for path in natsort.natsorted(folder_path.glob("*.avi"), key=lambda p: p.as_posix())
                    if path.is_file()
                ]
                if not avi_paths:
                    raise FileNotFoundError(f"No '.avi' files were found in Miniscope folder '{folder_path}'.")

                configuration_path = folder_path / "metaData.json"
                if not configuration_path.exists():
                    raise FileNotFoundError(f"No 'metaData.json' file was found in Miniscope folder '{folder_path}'.")

                timestamps_path = folder_path / "timeStamps.csv"
                interface_kwargs = dict(
                    file_paths=[str(path) for path in avi_paths],
                    configuration_file_path=str(configuration_path),
                    verbose=self.verbose,
                )
                if timestamps_path.exists():
                    interface_kwargs["timeStamps_file_path"] = str(timestamps_path)

                interface = MiniscopeImagingInterface(**interface_kwargs)
                interface_metadata = interface.get_metadata()
                device_metadata = interface_metadata["Ophys"]["Device"][0]
                device_label = device_metadata.get("name", device_name)
                sanitized_device_label = device_label.replace(" ", "_")

                segment_label = f"Segment{segment_index:0{padding_width}d}"

                interface._miniscope_device_label = sanitized_device_label
                interface._device_name_from_metadata = device_label
                interface._segment_label = segment_label
                interface._device_metadata_index = device_index
                interface._imaging_plane_metadata_index = device_index

                interface_key = f"MiniscopeImaging/{sanitized_device_label}/{segment_label}"
                imaging_interfaces[interface_key] = interface

        return imaging_interfaces

    def _resolve_folder_path_structure(
        self,
        base_path: Path,
        virtual_path_pattern: str,
    ) -> list[Path]:
        """Resolve virtual path pattern to actual filesystem paths.

        Walks the filesystem level-by-level following the pattern. Components in {braces}
        are wildcards that match any folder name. Other components must match exactly
        (with space/underscore sanitization).

        Parameters
        ----------
        base_path : Path
            The root directory to start searching from.
        virtual_path_pattern : str
            Path pattern with {wildcards} for unconstrained levels.
            Example: "researcher_name/experiment_name/{animalName}/{date}/{time}"
            - "researcher_name" and "experiment_name" must match exactly
            - {animalName}, {date}, {time} match any folder names

        Returns
        -------
        list[Path]
            List of all discovered session paths matching the pattern.

        Raises
        ------
        FileNotFoundError
            If base_path doesn't exist, no subdirectories found at a level, or
            expected folder name not found.

        Examples
        --------
        Pattern: "researcher_name/{experimentName}/{date}"
        Filesystem::

            base_path/
            └── researcher_name/
                ├── experiment_a/
                │   ├── 2025_06_12/
                │   └── 2025_06_13/
                └── experiment_b/
                    └── 2025_06_14/

        Returns: [
            base_path/researcher_name/experiment_a/2025_06_12,
            base_path/researcher_name/experiment_a/2025_06_13,
            base_path/researcher_name/experiment_b/2025_06_14
        ]
        """
        if not base_path.exists():
            raise FileNotFoundError(f"Miniscope data directory '{base_path}' does not exist.")

        if not virtual_path_pattern:
            return [base_path]

        # Parse pattern into components
        pattern_components = virtual_path_pattern.split("/")
        current_paths = [base_path]

        for level_index, pattern_component in enumerate(pattern_components):
            next_paths = []

            # Check if this component is a wildcard (enclosed in braces)
            is_wildcard = pattern_component.startswith("{") and pattern_component.endswith("}")
            expected_folder_name = None if is_wildcard else pattern_component

            for parent_path in current_paths:
                if not parent_path.exists():
                    continue

                subdirs = [child for child in parent_path.iterdir() if child.is_dir()]

                if not subdirs:
                    expected_text = (
                        f"wildcard {pattern_component}" if is_wildcard else f"directory '{expected_folder_name}'"
                    )
                    raise FileNotFoundError(
                        f"No subdirectories found at level {level_index} under '{parent_path}'. "
                        f"Expected {expected_text}"
                    )

                if is_wildcard:
                    # Wildcard: match any subdirectory
                    next_paths.extend(subdirs)
                else:
                    # Exact match with space/underscore sanitization
                    candidate_names = {expected_folder_name, expected_folder_name.replace(" ", "_")}
                    matches = [d for d in subdirs if d.name in candidate_names]
                    if not matches:
                        available = ", ".join(sorted(d.name for d in subdirs))
                        raise FileNotFoundError(
                            f"Expected directory '{expected_folder_name}' at level {level_index} under '{parent_path}', "
                            f"but found: {available}"
                        )
                    next_paths.extend(matches)

            if not next_paths:
                raise FileNotFoundError(
                    f"No directories resolved at level {level_index} " f"(pattern: '{pattern_component}')"
                )

            current_paths = next_paths

        return current_paths
