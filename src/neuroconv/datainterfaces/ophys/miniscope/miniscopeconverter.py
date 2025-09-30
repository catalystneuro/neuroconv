from __future__ import annotations

import json
from copy import deepcopy
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
from ....tools.nwb_helpers import make_or_load_nwbfile
from ....utils import get_json_schema_from_method_signature


class MiniscopeConverter(NWBConverter):
    """Bundle Miniscope imaging and optional behavior recordings into a single NWB conversion."""

    display_name = "Miniscope Imaging and Video"
    keywords = _MiniscopeMultiRecordingInterface.keywords + MiniscopeBehaviorInterface.keywords
    associated_suffixes = (
        _MiniscopeMultiRecordingInterface.associated_suffixes + MiniscopeBehaviorInterface.associated_suffixes
    )
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

        Example 1 – Dual Miniscope layout (stub dataset)::

            {
                "dataDirectory": "./stub/dual_miniscope_with_config",
                "directoryStructure": [
                    "experiment_name",
                    "experiment_name",
                    "animal_name",
                    "date",
                    "time"
                ],
                "devices": {
                    "miniscopes": {
                        "ACC_miniscope2": {...},
                        "HPC_miniscope1": {...}
                    }
                }
            }

        This produces a folder tree such as::

            stub/dual_miniscope_with_config/
            ├── experiment_name/
            │   └── experiment_name/
            │       └── animal_name/
            │           └── 2025_06_12/
            │               ├── 15_15_04/
            │               │   ├── ACC_miniscope2/
            │               │   └── HPC_miniscope1/
            │               └── 15_26_31/
            │                   ├── ACC_miniscope2/
            │                   └── HPC_miniscope1/

        Example 2 – Single Miniscope per timestamp::

            {
                "directoryStructure": [
                    "researcherName",
                    "experimentName",
                    "animalName",
                    "date",
                    "time"
                ],
                "devices": {
                    "miniscopes": {
                        "Miniscope": {...}
                    }
                }
            }

        Which yields::

            <root>/
            └── Researcher/
                └── Experiment/
                    └── Animal/
                        └── 2024_10_01/
                            └── 12_00_00/
                                └── Miniscope/

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
            "description": "If True, limit each Miniscope segment to 'stub_frames' frames during conversion.",
        }
        schema["properties"]["stub_frames"] = {
            "type": "integer",
            "minimum": 1,
            "default": 100,
            "description": "Number of frames to include when 'stub_test' is enabled.",
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

        for interface_key in imaging_interface_keys:
            interface = self.data_interface_objects[interface_key]
            interface_metadata = interface.get_metadata()

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
                device_name = interface_key.split("/", 1)[-1]

            sanitized_device_label = device_name.replace(" ", "_")
            interface._miniscope_device_label = sanitized_device_label
            interface._device_name_from_metadata = device_name

            segment_label = getattr(interface, "_segment_label", None)

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
        stub_frames: int = 100,
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
            If True, only a subset of the data (up to `stub_frames`) is written for testing purposes,
            by default False.
        stub_frames : int, optional
            The number of frames to include in the subset if `stub_test` is True, by default 100.
        """
        if metadata is None:
            metadata = self.get_metadata()

        self.validate_metadata(metadata=metadata)

        self.temporally_align_data_interfaces()

        with make_or_load_nwbfile(
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            metadata=metadata,
            overwrite=overwrite,
            verbose=self.verbose,
        ) as nwbfile_out:
            self.add_to_nwbfile(nwbfile=nwbfile_out, metadata=metadata, stub_test=stub_test, stub_frames=stub_frames)

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
        """Fetch recording folder paths for each Miniscope device using the User Config description."""

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
        """Discover session directories by walking the filesystem and validating against the User Config."""

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
