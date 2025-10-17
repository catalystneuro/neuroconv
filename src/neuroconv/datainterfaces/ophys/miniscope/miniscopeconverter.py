from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
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
            Root directory containing the Miniscope acquisition.
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
            imaging_interfaces = self._build_imaging_interfaces_from_user_config(
                user_config_path=Path(user_configuration_file_path)
            )
            if not imaging_interfaces:
                raise ValueError(
                    "No Miniscope imaging folders were discovered using the provided 'user_configuration_file_path'."
                )
            self.data_interface_objects.update(imaging_interfaces)
        else:
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
        return schema

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata,
        conversion_options: dict | None = None,
        stub_test: bool = False,
        stub_frames: int = 100,
    ):
        """Add Miniscope interfaces to the provided NWBFile."""
        imaging_interface_keys = [key for key in self.data_interface_objects if key.startswith("MiniscopeImaging")]

        conversion_options = conversion_options.copy() if conversion_options else {}
        stub_test = conversion_options.pop("stub_test", stub_test)
        stub_frames = conversion_options.pop("stub_frames", stub_frames)

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

        def _normalize_start_time(dt: datetime | None) -> datetime | None:
            if dt is None:
                return None
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)

        normalized_times = []
        for entry in interface_entries:
            start_time = entry["session_start_time"]
            normalized = _normalize_start_time(start_time) if isinstance(start_time, datetime) else None
            entry["normalized_start_time"] = normalized
            if normalized is not None:
                normalized_times.append(normalized)

        if normalized_times:
            base_time = min(normalized_times)
            for entry in interface_entries:
                normalized = entry.get("normalized_start_time")
                if normalized is None:
                    continue
                offset = (normalized - base_time).total_seconds()
                if offset:
                    entry["interface"].set_aligned_starting_time(offset)

        for entry in interface_entries:
            interface_key = entry["key"]
            interface = entry["interface"]
            interface_metadata = entry["metadata"]

            interface_options = conversion_options.get(interface_key, {})
            interface_stub_test = interface_options.get("stub_test", stub_test)
            interface_stub_frames = interface_options.get("stub_frames", stub_frames)
            passthrough_options = {
                key: value for key, value in interface_options.items() if key not in {"stub_test", "stub_frames"}
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

        # Apply stub_test and stub_samples to all imaging interfaces
        imaging_interface_keys = [key for key in self.data_interface_objects if key.startswith("MiniscopeImaging")]
        for interface_key in imaging_interface_keys:
            if interface_key not in conversion_options:
                conversion_options[interface_key] = {}
            conversion_options[interface_key].setdefault("stub_test", stub_test)
            conversion_options[interface_key].setdefault("stub_samples", stub_samples)

        super().run_conversion(
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            metadata=metadata,
            overwrite=overwrite,
            conversion_options=conversion_options,
            **kwargs,
        )

    def _build_imaging_interfaces_from_user_config(
        self, user_config_path: Path
    ) -> dict[str, MiniscopeImagingInterface]:
        """Create Miniscope imaging interfaces using the acquisition User Config file."""

        with user_config_path.open() as f:
            user_config = json.load(f)

        miniscope_devices = user_config.get("devices", {}).get("miniscopes", {})
        if not miniscope_devices:
            raise ValueError("'devices[miniscopes]' is missing from the provided User Config file.")

        device_directories = self._get_configured_device_directories(
            user_config=user_config,
            user_config_path=user_config_path,
            device_names=list(miniscope_devices.keys()),
        )

        return self._build_imaging_interfaces_from_directories(device_directories=device_directories)

    def _get_configured_device_directories(
        self,
        *,
        user_config: dict,
        user_config_path: Path,
        device_names: list[str],
    ) -> dict[str, list[Path]]:
        """Fetch recording folder paths for each Miniscope device using the User Config description.

        This method resolves the data directory path and walks through the configured directory structure
        to discover all recording sessions containing the specified Miniscope devices.

        Parameters
        ----------
        user_config : dict
            The parsed User Config JSON containing 'dataDirectory', 'directoryStructure', and device
            configuration fields.
        user_config_path : Path
            Path to the User Config file, used to resolve relative paths in the configuration.
        device_names : list[str]
            List of Miniscope device names (e.g., ["ACC_miniscope2", "HPC_miniscope1"]) to search for
            within each session.

        Returns
        -------
        dict[str, list[Path]]
            Dictionary mapping each device name to a list of directory paths containing its recordings.
            For example: {"ACC_miniscope2": [Path(...)/15_15_04/ACC_miniscope2, Path(...)/15_26_31/ACC_miniscope2]}

        Notes
        -----
        Path Resolution Strategy:
            1. If 'dataDirectory' is specified in the config, try these candidate paths in order:
               - The path as-is (verbatim from config)
               - If the path is relative, also try:
                 * Relative to the User Config file location
                 * Relative to the converter's folder_path
            2. Always add converter's folder_path as a final fallback
            3. Use the first candidate path that exists on disk

        Session Discovery:
            - Calls _resolve_session_paths to walk the directory structure using the configured hierarchy
              (e.g., researcherName/experimentName/animalName/date/time)
            - Sorts discovered sessions using natural sorting for consistent ordering

        Device Discovery:
            - For each session path, searches for subdirectories matching each device name
            - Handles both sanitized names (spaces replaced with underscores) and original names
            - Skips sessions that don't contain a particular device (supporting partial recordings)

        Examples
        --------
        Given a config with two devices and two recording sessions::

            user_config = {
                "dataDirectory": "./data",
                "directoryStructure": ["animalName", "date", "time"],
                "animalName": "mouse_001",
                "devices": {"miniscopes": {"ACC_miniscope2": {...}, "HPC_miniscope1": {...}}}
            }

        And a file structure::

            data/
            └── mouse_001/
                └── 2025_06_12/
                    ├── 15_15_04/
                    │   ├── ACC_miniscope2/
                    │   └── HPC_miniscope1/
                    └── 15_26_31/
                        ├── ACC_miniscope2/
                        └── HPC_miniscope1/

        Returns::

            {
                "ACC_miniscope2": [
                    Path("data/mouse_001/2025_06_12/15_15_04/ACC_miniscope2"),
                    Path("data/mouse_001/2025_06_12/15_26_31/ACC_miniscope2")
                ],
                "HPC_miniscope1": [
                    Path("data/mouse_001/2025_06_12/15_15_04/HPC_miniscope1"),
                    Path("data/mouse_001/2025_06_12/15_26_31/HPC_miniscope1")
                ]
            }
        """
        data_directory = user_config.get("dataDirectory")
        candidate_base_paths = []
        if data_directory:
            candidate_path = Path(data_directory)
            candidate_base_paths.append(candidate_path)
            if not candidate_path.is_absolute():
                candidate_base_paths.append((user_config_path.parent / candidate_path).resolve())
                candidate_base_paths.append((self._folder_path / candidate_path).resolve())
        candidate_base_paths.append(self._folder_path)

        base_path = next((path for path in candidate_base_paths if path.exists()), None)
        if base_path is None:
            searched = ", ".join(str(path) for path in candidate_base_paths)
            raise FileNotFoundError(
                "Unable to locate Miniscope data directory based on the configuration. "
                f"Attempted: {searched or '<none>'}."
            )

        session_paths = self._resolve_session_paths(
            base_path=base_path,
            directory_structure=user_config.get("directoryStructure", []),
            user_config=user_config,
        )

        natsort = get_package(package_name="natsort", installation_instructions="pip install natsort")
        session_paths = natsort.natsorted(session_paths, key=lambda path: path.as_posix())

        device_directories: dict[str, list[Path]] = {device_name: [] for device_name in device_names}
        for session_path in session_paths:
            if not session_path.exists():
                continue
            for device_name in device_names:
                sanitized_device_name = device_name.replace(" ", "_")
                candidate_names = [sanitized_device_name]
                if sanitized_device_name != device_name:
                    candidate_names.append(device_name)

                found_directory = None
                for candidate_name in candidate_names:
                    candidate_path = session_path / candidate_name
                    if candidate_path.exists():
                        found_directory = candidate_path
                        break

                if found_directory is not None:
                    device_directories[device_name].append(found_directory)

        return device_directories

    def _build_imaging_interfaces_from_directories(
        self,
        *,
        device_directories: dict[str, list[Path]],
    ) -> dict[str, MiniscopeImagingInterface]:
        """Instantiate imaging interfaces for each Miniscope device/segment discovered on disk."""

        natsort = get_package(package_name="natsort", installation_instructions="pip install natsort")

        imaging_interfaces: dict[str, MiniscopeImagingInterface] = {}
        for device_index, (device_name, folder_paths) in enumerate(device_directories.items()):
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

    def _resolve_session_paths(
        self,
        *,
        base_path: Path,
        directory_structure: list[str],
        user_config: dict,
    ) -> list[Path]:
        """Discover session directories by walking the filesystem and validating against the User Config.

        This method walks through a hierarchical directory structure based on the 'directoryStructure' field
        in the User Config, discovering all session paths that match the configured hierarchy. It supports
        both constrained paths (when config values are specified) and exploratory discovery (when values are
        not specified).

        Parameters
        ----------
        base_path : Path
            The root directory to start searching from (typically the resolved data directory).
        directory_structure : list[str]
            Ordered list of configuration keys defining the directory hierarchy
            (e.g., ["researcherName", "experimentName", "animalName", "date", "time"]).
        user_config : dict
            The User Config dictionary containing expected values for each key in directory_structure.

        Returns
        -------
        list[Path]
            List of all discovered session paths (the leaf directories after traversing the full hierarchy).
            If directory_structure is empty, returns [base_path].

        Notes
        -----
        Directory Traversal Logic:
            For each level in the directory hierarchy (each key in directory_structure):

            1. **If config value is specified** (e.g., user_config["animalName"] = "mouse_001"):
               - First checks if the parent directory name already matches (supports nested configs)
               - Otherwise looks for subdirectories matching the expected value (or sanitized version)
               - Raises FileNotFoundError if no match is found
               - Supports space/underscore variations (e.g., "Miniscope V4" → "Miniscope_V4")

            2. **If config value is NOT specified** (e.g., user_config["date"] is missing):
               - Discovers ALL subdirectories at that level
               - Allows exploration of multiple dates, sessions, etc.

            3. **Error Handling**:
               - Raises FileNotFoundError if no subdirectories exist when expected
               - Provides helpful error messages listing available directories

        Examples
        --------
        Example 1 - Fully constrained path::

            base_path = Path("./data")
            directory_structure = ["animalName", "date", "time"]
            user_config = {"animalName": "mouse_001", "date": "2025_06_12"}
            # Note: "time" is not in config, so all time directories are discovered

        With file structure::

            data/
            └── mouse_001/
                └── 2025_06_12/
                    ├── 15_15_04/
                    └── 15_26_31/

        Returns::

            [Path("data/mouse_001/2025_06_12/15_15_04"),
             Path("data/mouse_001/2025_06_12/15_26_31")]

        Example 2 - Exploratory discovery::

            directory_structure = ["animalName", "date", "time"]
            user_config = {}  # No constraints specified

        With file structure::

            data/
            ├── mouse_001/
            │   └── 2025_06_12/
            │       └── 15_15_04/
            └── mouse_002/
                └── 2025_06_13/
                    └── 09_30_00/

        Returns::

            [Path("data/mouse_001/2025_06_12/15_15_04"),
             Path("data/mouse_002/2025_06_13/09_30_00")]

        Example 3 - Empty directory structure::

            directory_structure = []

        Returns::

            [base_path]  # Base path itself is the session
        """
        if not base_path.exists():
            raise FileNotFoundError(f"Configured Miniscope data directory '{base_path}' does not exist.")

        if not directory_structure:
            return [base_path]

        current_paths: list[Path] = [base_path]
        for key in directory_structure:
            expected_value = user_config.get(key)
            next_paths: list[Path] = []

            for parent_path in current_paths:
                if not parent_path.exists():
                    continue

                subdirectories = [child for child in parent_path.iterdir() if child.is_dir()]
                if isinstance(expected_value, str) and expected_value:
                    candidate_names = {expected_value, expected_value.replace(" ", "_")}
                    parent_matches = parent_path.name in candidate_names
                    if parent_matches:
                        next_paths.append(parent_path)
                        continue

                    if not subdirectories:
                        raise FileNotFoundError(
                            f"Expected a subdirectory for configuration key '{key}' under '{parent_path}', but none were found."
                        )

                    matches = [child for child in subdirectories if child.name in candidate_names]
                    if not matches:
                        available = ", ".join(sorted(child.name for child in subdirectories)) or "<none>"
                        raise FileNotFoundError(
                            f"Expected directory '{expected_value}' for configuration key '{key}' under '{parent_path}', "
                            f"but found: {available}."
                        )
                    next_paths.extend(matches)
                else:
                    if not subdirectories:
                        raise FileNotFoundError(
                            f"Expected a subdirectory for configuration key '{key}' under '{parent_path}', but none were found."
                        )
                    next_paths.extend(subdirectories)

            if not next_paths:
                raise FileNotFoundError(
                    f"Unable to resolve any directories for configuration key '{key}' starting from {[str(p) for p in current_paths]}."
                )

            current_paths = next_paths

        return current_paths
