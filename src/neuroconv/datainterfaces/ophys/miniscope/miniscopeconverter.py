import json
import warnings
from pathlib import Path

from pydantic import DirectoryPath, FilePath, validate_call
from pynwb import NWBFile

from ._miniscope_readers import (
    _get_device_folder_timestamps,
    _get_starting_frames,
    _raise_if_legacy_user_config_device_list,
    _read_miniscope_config,
)
from .miniscopeimagingdatainterface import (
    MiniscopeImagingInterface,
    _MiniscopeMultiRecordingInterface,
)
from ... import MiniscopeBehaviorInterface, MiniscopeHeadOrientationInterface
from ...behavior.video.externalvideointerface import ExternalVideoInterface
from ....nwbconverter import ConverterPipe
from ....tools import get_package
from ....tools.nwb_helpers import get_default_nwbfile_metadata
from ....utils import (
    DeepDict,
    dict_deep_update,
    get_json_schema_from_method_signature,
)
from ....utils.str_utils import to_camel_case, to_snake_case


class MiniscopeConverter(ConverterPipe):
    """Bundle Miniscope imaging and optional behavior recordings into a single NWB conversion."""

    display_name = "Miniscope Imaging and Video"
    keywords = (
        MiniscopeImagingInterface.keywords
        + MiniscopeBehaviorInterface.keywords
        + MiniscopeHeadOrientationInterface.keywords
    )
    associated_suffixes = (
        MiniscopeImagingInterface.associated_suffixes
        + MiniscopeBehaviorInterface.associated_suffixes
        + MiniscopeHeadOrientationInterface.associated_suffixes
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
            **Root data directory** containing the Miniscope acquisition data. This should be the base directory
            where the configured directory structure sits (e.g. "dataDirectory" in the User Config).

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
        - ``devices[cameras]``: the same mapping for the behavior cameras. Both device names are the
          names of the folders holding the recordings of that device.

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
        preserving their individual timestamps. Behavior video is added for every camera declared under
        ``devices[cameras]``. For devices recorded multiple times, each timestamp folder is instantiated as a
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
        self._user_configuration_file_path = user_configuration_file_path
        # Per-interface bookkeeping for the imaging devices and behavior cameras of the User Config.
        self._imaging_interfaces: dict[str, dict] = {}
        self._behavior_video_interfaces: dict[str, dict] = {}
        self._camera_names: list[str] = []
        self._camera_names_camel_case: dict[str, str] = {}

        data_interfaces = {}
        if self._user_configuration_file_path is not None:
            # Load user configuration
            config_path = Path(self._user_configuration_file_path)
            with config_path.open(encoding="utf-8") as f:
                self._user_config = json.load(f)
            _raise_if_legacy_user_config_device_list(user_config=self._user_config)

            data_directory_path_in_config = self._user_config.get("dataDirectory", "")
            data_directory_name_in_json = data_directory_path_in_config.split("/")[-1]
            if data_directory_name_in_json != self._folder_path.name:
                warnings.warn(
                    f"Ignoring 'dataDirectory' field in User Config ('{data_directory_path_in_config}'). "
                    f"Using provided folder_path: '{self._folder_path}'.",
                    UserWarning,
                    stacklevel=2,
                )

            directory_structure = self._user_config.get("directoryStructure", [])
            config_fields = self._user_config.keys()
            fixed_path_entries = [key for key in directory_structure if key in config_fields]
            fixed_folders = [self._user_config[key] for key in fixed_path_entries]
            fixed_data_path = self._folder_path / "/".join(fixed_folders)

            if not fixed_data_path.exists():
                raise FileNotFoundError(
                    f"Expected directory structure not found: '{fixed_data_path}'\n"
                    f"Base folder: '{self._folder_path}'\n"
                    f"Directory structure from config: {directory_structure}\n"
                    f"Fixed path components: {fixed_folders}\n"
                    f"Please verify that:\n"
                    f"  1. The 'directoryStructure' in your User Config matches your actual folder structure\n"
                    f"  2. The fixed fields ({', '.join(fixed_path_entries)}) are correctly set\n"
                    f"  3. The folder '{fixed_data_path.name}' exists under '{fixed_data_path.parent}'"
                )

            miniscope_devices = self._user_config.get("devices", {}).get("miniscopes", {})
            if not miniscope_devices:
                raise ValueError("'devices[miniscopes]' is missing from the provided User Config file.")
            self._device_names = list(miniscope_devices.keys())
            # Create CamelCase mapping for device names
            self._device_names_camel_case = {name: to_camel_case(name) for name in self._device_names}

            # Sorted so discovery does not depend on the order the filesystem hands back. The imaging
            # plane of a device takes the imaging rate of the first recording found for it, and two
            # recordings of one Miniscope differ slightly in rate, so glob order would otherwise decide
            # which one reaches the file.
            all_paths = sorted(path for path in fixed_data_path.glob("**") if path.is_dir())
            device_folders_dict = {}
            for device_name in self._device_names:
                device_folders_dict[device_name] = [p for p in all_paths if p.name == device_name]
                if not device_folders_dict[device_name]:
                    warnings.warn(
                        f"No folder named '{device_name}' was found under '{fixed_data_path}', so the Miniscope "
                        "the User Config declares under 'devices[miniscopes]' will be omitted from the conversion.",
                        UserWarning,
                        stacklevel=2,
                    )

            self._interface_to_device_mapping = {}
            for device_name in self._device_names:
                # Iterate over all the folders found for this device
                # And create a MiniscopeImagingInterface for each
                for device_folder_path in device_folders_dict[device_name]:
                    # Use as_posix() to ensure forward slashes on all platforms and avoid windows backslashes
                    interface_name = device_folder_path.relative_to(fixed_data_path).as_posix()
                    # Remove slashes and strip the device folder name from the end of the interface
                    # path, e.g. "2025_06_12/15_15_04/ACC_miniscope2" -> "2025_06_1215_15_04"
                    interface_relative_path = interface_name.replace("/", "")
                    if interface_relative_path.endswith(device_name):
                        interface_relative_path = interface_relative_path[: -len(device_name)]

                    # The series is per recording, while the device and its imaging plane are per
                    # device and shared by every recording made with it.
                    series_metadata_key = f"miniscope_imaging_{device_name}_{interface_relative_path}"
                    interface = MiniscopeImagingInterface(
                        folder_path=device_folder_path, metadata_key=series_metadata_key
                    )
                    data_interfaces[interface_name] = interface
                    self._interface_to_device_mapping[interface_name] = device_name
                    self._imaging_interfaces[interface_name] = dict(
                        device_name=device_name,
                        folder_path=device_folder_path,
                        relative_path=interface_relative_path,
                        metadata_key=series_metadata_key,
                        # The interface derives this from the device its config names, so every
                        # recording of one Miniscope lands on the same registry entry.
                        device_metadata_key=interface.device_metadata_key,
                        imaging_plane_metadata_key=f"imaging_plane_{device_name}",
                    )

                    # Check for head orientation data in the same device folder
                    head_orientation_file_path = device_folder_path / "headOrientation.csv"
                    if head_orientation_file_path.exists():
                        head_orientation_interface_name = f"{interface_name}/HeadOrientation"
                        # Use device name in CamelCase for unique metadata key
                        device_name_camel = self._device_names_camel_case[device_name]
                        # Include relative path to distinguish different sessions
                        interface_relative_path = interface_name.replace("/", "")
                        if interface_relative_path.endswith(device_name):
                            interface_relative_path = interface_relative_path[: -len(device_name)]
                        metadata_key = f"TimeSeriesMiniscopeHeadOrientation{device_name_camel}{interface_relative_path}"
                        data_interfaces[head_orientation_interface_name] = MiniscopeHeadOrientationInterface(
                            file_path=head_orientation_file_path,
                            metadata_key=metadata_key,
                        )
                        self._interface_to_device_mapping[head_orientation_interface_name] = device_name

            # Behavior cameras are declared in the same User Config as the miniscopes, under
            # 'devices[cameras]', so their folders are discovered the same way as the imaging device
            # folders rather than by globbing the lab-specific 'BehavCam*' name at a fixed depth.
            natsort = get_package(package_name="natsort", installation_instructions="pip install natsort")
            camera_devices = self._user_config.get("devices", {}).get("cameras", {})
            self._camera_names = list(camera_devices)
            self._camera_names_camel_case = {name: to_camel_case(name) for name in self._camera_names}
            for camera_name in self._camera_names:
                camera_folder_paths = [path for path in all_paths if path.name == camera_name]
                if not camera_folder_paths:
                    warnings.warn(
                        f"No folder named '{camera_name}' was found under '{fixed_data_path}', so the behavior camera "
                        "the User Config declares under 'devices[cameras]' will be omitted from the conversion.",
                        UserWarning,
                        stacklevel=2,
                    )
                for camera_folder_path in camera_folder_paths:
                    interface_name = camera_folder_path.relative_to(fixed_data_path).as_posix()
                    video_file_paths = natsort.natsorted(camera_folder_path.glob("*.avi"))
                    if not video_file_paths:
                        warnings.warn(
                            f"No behavior videos (.avi files) were found in '{camera_folder_path}' for camera "
                            f"'{camera_name}'. This camera folder will be omitted from the conversion.",
                            UserWarning,
                            stacklevel=2,
                        )
                        continue

                    # Same flattening as the imaging series names, e.g.
                    # "2021_07_15/16_18_59/cameraDeviceName" -> "2021_07_1516_18_59"
                    interface_relative_path = interface_name.replace("/", "")
                    if interface_relative_path.endswith(camera_name):
                        interface_relative_path = interface_relative_path[: -len(camera_name)]

                    camera_name_camel = self._camera_names_camel_case[camera_name]
                    metadata_key = f"video_{camera_name}_{interface_relative_path}"
                    image_series_name = f"ImageSeries{camera_name_camel}{interface_relative_path}"

                    interface = ExternalVideoInterface(
                        file_paths=video_file_paths,
                        metadata_key=metadata_key,
                        video_name=image_series_name,
                        verbose=verbose,
                    )

                    # The .avi files of a camera folder share a single timeStamps.csv, so the
                    # timestamps are split back per file to match the ImageSeries segments.
                    starting_frames = _get_starting_frames(
                        folder_path=str(camera_folder_path), video_file_pattern="*.avi"
                    )
                    timestamps = _get_device_folder_timestamps(folder_path=str(camera_folder_path))
                    segment_boundaries = list(starting_frames) + [len(timestamps)]
                    interface.set_aligned_timestamps(
                        aligned_timestamps=[
                            timestamps[segment_start:segment_stop]
                            for segment_start, segment_stop in zip(segment_boundaries[:-1], segment_boundaries[1:])
                        ]
                    )

                    data_interfaces[interface_name] = interface
                    self._behavior_video_interfaces[interface_name] = dict(
                        camera_name=camera_name,
                        session_folder_path=camera_folder_path.parent,
                        starting_frames=starting_frames,
                        metadata_key=metadata_key,
                        # One Device per camera, shared across the recordings of that camera.
                        device_metadata_key=to_snake_case(camera_name),
                        image_series_name=image_series_name,
                        camera_config=_read_miniscope_config(folder_path=str(camera_folder_path)),
                    )
        else:
            # Legacy mode: use _MiniscopeMultiRecordingInterface for backwards compatibility
            warnings.warn(
                "Not passing 'user_configuration_file_path' to MiniscopeConverter is deprecated "
                "and will be removed on or after February 2027. "
                "The legacy folder discovery mode assumes all recordings are back-to-back, "
                "which does not hold in general and can produce silently incorrect results. "
                "Please pass the 'user_configuration_file_path' argument, which points to the "
                "User Config JSON file generated by the Miniscope DAQ software (available since v1.0). "
                "If your data does not include a configuration file, "
                "use MiniscopeImagingInterface directly or build a custom ConverterPipe. "
                "See the 'Combining Multiple Acquisitions' section in the conversion gallery: "
                "https://neuroconv.readthedocs.io/en/main/conversion_examples_gallery/imaging/miniscope.html"
                "#combining-multiple-acquisitions",
                FutureWarning,
                stacklevel=2,
            )
            default_interface = _MiniscopeMultiRecordingInterface(folder_path=folder_path)
            default_metadata = default_interface.get_metadata()
            device_metadata = default_metadata["Ophys"]["Device"][0]
            device_name = device_metadata.get("name", "Miniscope")
            sanitized_device_name = device_name.replace(" ", "_")
            default_interface._miniscope_device_label = sanitized_device_name
            default_interface._device_name_from_metadata = device_name
            default_interface._device_metadata_index = 0
            default_interface._imaging_plane_metadata_index = 0
            interface_name = f"Miniscope"
            data_interfaces[interface_name] = default_interface
            self._interface_to_device_mapping = {interface_name: device_name}
            self._device_names = [device_name]
            # Create CamelCase mapping for device names
            self._device_names_camel_case = {device_name: to_camel_case(device_name)}

        super().__init__(data_interfaces=data_interfaces, verbose=verbose)

        if self._user_configuration_file_path is None:
            # Legacy layout: the behavior videos sit in 'BehavCam*' folders one level below the top
            # folder. Config-driven layouts are handled by the camera discovery above.
            behavior_video_file_paths = list(self._folder_path.glob("*/BehavCam*/*.avi"))
            if behavior_video_file_paths:
                self.data_interface_objects["MiniscopeBehavCam"] = MiniscopeBehaviorInterface(folder_path=folder_path)
            elif self.verbose:
                print(
                    "Miniscope behavior videos were not found under the provided folder and will be omitted from conversion."
                )

        # Align session start times across all imaging interfaces
        self._align_session_start_times()

    def _is_head_orientation_interface(self, interface_name: str) -> bool:
        """Check if an interface name corresponds to a head orientation interface."""
        return interface_name.endswith("/HeadOrientation")

    def _get_ophys_interface_names(self) -> list[str]:
        """Get names of ophys interfaces, excluding behavior and head orientation interfaces."""
        return [
            interface_name
            for interface_name, interface in self.data_interface_objects.items()
            if isinstance(interface, (MiniscopeImagingInterface, _MiniscopeMultiRecordingInterface))
        ]

    def _get_behavior_video_interface_names(self) -> list[str]:
        """Get names of the behavior camera interfaces discovered from the User Config."""
        return [
            interface_name
            for interface_name in self._behavior_video_interfaces
            if interface_name in self.data_interface_objects
        ]

    def _get_behavior_video_conversion_options(self) -> dict[str, dict]:
        """Pass the per-file starting frames that an external-file ImageSeries needs."""
        return {
            interface_name: dict(starting_frames=self._behavior_video_interfaces[interface_name]["starting_frames"])
            for interface_name in self._get_behavior_video_interface_names()
        }

    def _get_head_orientation_interface_names(self) -> list[str]:
        """Get names of head orientation interfaces."""
        return [k for k in self.data_interface_objects if self._is_head_orientation_interface(k)]

    def _align_session_start_times(self):
        """
        Align all Miniscope imaging interfaces to a common session start time.

        For each interface:
        1. Extract its session_start_time from the session-level metaData.json
        2. Find the minimum session_start_time across all interfaces
        3. Shift each interface's timestamps by (session_start_time - min_session_start_time)

        This ensures that sessions recorded at different times maintain their temporal relationship.
        """
        from neuroconv.datainterfaces.ophys.miniscope.miniscopeimagingdatainterface import (
            _MiniscopeMultiRecordingInterface,
        )

        ophys_interface_names = self._get_ophys_interface_names()

        session_start_times = {}
        for interface_name in ophys_interface_names:
            interface = self.data_interface_objects[interface_name]

            # MiniscopeImagingInterface (config file mode) has _device_folder_path
            # _MiniscopeMultiRecordingInterface (legacy mode) has _recording_start_times
            if isinstance(interface, _MiniscopeMultiRecordingInterface):
                session_start_time = interface._recording_start_times[0]
            else:
                device_folder_path = interface._device_folder_path
                session_start_time = interface._get_session_start_time(folder_path=device_folder_path.parent)
            session_start_times[interface_name] = session_start_time

        # Find the minimum session_start_time (this becomes the reference)
        min_session_start_time = min(session_start_times.values())
        self._converter_session_start_time = min_session_start_time

        # Align each ophys interface's timestamps
        for interface_name, session_start_time in session_start_times.items():
            interface = self.data_interface_objects[interface_name]
            time_offset = (session_start_time - min_session_start_time).total_seconds()
            interface.set_aligned_starting_time(aligned_starting_time=time_offset)

        # Align the behavior cameras with the session they were recorded in
        for video_interface_name in self._get_behavior_video_interface_names():
            session_folder_path = self._behavior_video_interfaces[video_interface_name]["session_folder_path"]
            session_start_time = MiniscopeImagingInterface._get_session_start_time(folder_path=session_folder_path)
            if session_start_time is None:
                continue
            time_offset = (session_start_time - min_session_start_time).total_seconds()
            self.data_interface_objects[video_interface_name].set_aligned_starting_time(
                aligned_starting_time=time_offset
            )

        # Align head orientation interfaces with their paired imaging interfaces
        for ho_interface_name in self._get_head_orientation_interface_names():
            # Extract the paired imaging interface name (remove "/HeadOrientation" suffix)
            paired_interface_name = ho_interface_name.rsplit("/HeadOrientation", 1)[0]
            if paired_interface_name in session_start_times:
                ho_interface = self.data_interface_objects[ho_interface_name]
                session_start_time = session_start_times[paired_interface_name]
                time_offset = (session_start_time - min_session_start_time).total_seconds()
                aligned_timestamps = ho_interface.get_timestamps() + time_offset
                ho_interface.set_aligned_timestamps(aligned_timestamps)

    def get_metadata(self) -> DeepDict:
        if self._user_configuration_file_path is None:
            return self._get_legacy_metadata()

        metadata = self._get_ophys_metadata()
        self._add_behavior_video_metadata(metadata=metadata)
        return metadata

    def _add_behavior_video_metadata(self, *, metadata: DeepDict) -> None:
        """Name each behavior video after its camera and session, and share one Device per camera.

        The interface defaults to a camera ``Device`` of its own per video, but a camera recorded over
        several sessions is one camera, so every recording of it is pointed at a single entry, the way
        the imaging interfaces share the Miniscope they were recorded with.
        """
        for video_interface_name in self._get_behavior_video_interface_names():
            video_interface_info = self._behavior_video_interfaces[video_interface_name]
            camera_config = dict(video_interface_info["camera_config"])
            camera_config.pop("name", None)
            device_type = camera_config.pop("deviceType", None)
            region_of_interest = camera_config.pop("ROI", None)
            acquisition_settings = ", ".join(f"{key}: {value}" for key, value in sorted(camera_config.items()))

            device_metadata = dict(
                name=self._camera_names_camel_case[video_interface_info["camera_name"]],
                description=(
                    "Behavior camera recorded by the Miniscope DAQ software. "
                    f"Acquisition settings: {acquisition_settings}."
                ),
            )
            if device_type is not None:
                # 'deviceType' is the camera hardware the config was written against, shared by every
                # camera of that type. The manufacturer it does not record is filled at write time.
                device_model_metadata_key = to_snake_case(device_type)
                metadata["DeviceModels"][device_model_metadata_key] = dict(name=device_type)
                device_metadata["device_model_metadata_key"] = device_model_metadata_key
            metadata["Devices"][video_interface_info["device_metadata_key"]] = device_metadata
            # The interface defaults to a Device of its own; the shared one above replaces it.
            metadata["Devices"].pop(f"{video_interface_info['metadata_key']}_camera", None)

            video_metadata = metadata["Behavior"]["ExternalVideos"][video_interface_info["metadata_key"]]
            video_metadata["name"] = video_interface_info["image_series_name"]
            video_metadata["description"] = (
                f"Video recorded by the '{video_interface_info['camera_name']}' behavior camera."
            )
            video_metadata["device_metadata_key"] = video_interface_info["device_metadata_key"]
            if region_of_interest is not None:
                video_metadata["dimension"] = [region_of_interest["width"], region_of_interest["height"]]

    def _device_metadata_keys(self) -> dict[str, str]:
        """Map each declared Miniscope to the ``metadata["Devices"]`` key its interfaces registered it under."""
        return {
            interface_info["device_name"]: interface_info["device_metadata_key"]
            for interface_info in self._imaging_interfaces.values()
        }

    def _get_ophys_metadata(self) -> DeepDict:
        """Assemble the dict-based metadata of the User Config mode.

        One ``Devices`` entry and one ``Ophys.ImagingPlanes`` entry per Miniscope, shared by all of its
        recordings, and one ``Ophys.MicroscopySeries`` entry per recording pointing at them.
        """
        from ....tools.roiextractors.roiextractors import (
            _get_ophys_metadata_placeholders,
        )

        metadata = get_default_nwbfile_metadata()
        for interface in self.data_interface_objects.values():
            if isinstance(interface, MiniscopeImagingInterface):
                interface_metadata = interface.get_metadata(use_new_metadata_format=True)
            else:
                interface_metadata = interface.get_metadata()
            # Entries are keyed, so a later interface sharing a key carries the same content and should
            # replace it. Appending would also dedupe a device's ``ROI``, and a square sensor's
            # ``[600, 600]`` would reach the file as ``[600]``.
            metadata = dict_deep_update(metadata, interface_metadata, append_list=False)

        metadata["NWBFile"]["session_start_time"] = self._converter_session_start_time

        # The registry entries the interfaces contributed are keyed per device already; only their NWB
        # names are converter business, since a device name is shared across the whole conversion.
        for device_name, device_metadata_key in self._device_metadata_keys().items():
            if device_metadata_key in metadata["Devices"]:
                metadata["Devices"][device_metadata_key]["name"] = self._device_names_camel_case[device_name]

        self._move_per_recording_settings_to_the_series(metadata=metadata)

        # An imaging plane belongs to a device, not to a recording, so the per-interface entries the
        # interfaces contributed are replaced by one entry per device.
        placeholder_imaging_plane = _get_ophys_metadata_placeholders()["Ophys"]["ImagingPlanes"]["default_metadata_key"]
        imaging_rates = {}
        for interface_info in self._imaging_interfaces.values():
            plane_metadata = metadata["Ophys"]["ImagingPlanes"].get(interface_info["metadata_key"], {})
            imaging_rates.setdefault(interface_info["device_name"], plane_metadata.get("imaging_rate"))

        imaging_planes = {}
        for device_name in self._device_names:
            device_name_camel = self._device_names_camel_case[device_name]
            imaging_planes[f"imaging_plane_{device_name}"] = {
                **placeholder_imaging_plane,
                "name": f"ImagingPlane{device_name_camel}",
                "description": f"Imaging plane for {device_name} Miniscope device.",
                "device_metadata_key": self._device_metadata_keys()[device_name],
                "imaging_rate": imaging_rates.get(device_name),
            }
        metadata["Ophys"]["ImagingPlanes"] = imaging_planes

        for interface_info in self._imaging_interfaces.values():
            device_name_camel = self._device_names_camel_case[interface_info["device_name"]]
            metadata["Ophys"]["MicroscopySeries"][interface_info["metadata_key"]].update(
                name=f"OnePhotonSeries{device_name_camel}{interface_info['relative_path']}",
                imaging_plane_metadata_key=interface_info["imaging_plane_metadata_key"],
            )

        return metadata

    def _move_per_recording_settings_to_the_series(self, *, metadata: DeepDict) -> None:
        """Keep on a device only the settings all of its recordings agree on.

        The ndx-miniscope schema declares acquisition settings as attributes of the ``Miniscope``
        device, but the DAQ writes them per recording, and an experimenter who refocuses the lens or
        changes the LED power between two recordings of one Miniscope makes them disagree. A device is
        shared by its recordings and can hold one value, so the settings that vary are reported on each
        ``MicroscopySeries``, which is the recording they are true of, instead of one of them being
        asserted for all.
        """
        from ._miniscope_readers import (
            _config_to_miniscope_device_metadata,
            _read_miniscope_config,
        )

        interfaces_per_device = {device_name: [] for device_name in self._device_names}
        for interface_info in self._imaging_interfaces.values():
            interfaces_per_device[interface_info["device_name"]].append(interface_info)

        for device_name, interface_infos in interfaces_per_device.items():
            configs = {
                interface_info["metadata_key"]: _read_miniscope_config(folder_path=str(interface_info["folder_path"]))
                for interface_info in interface_infos
            }
            # ``repr`` because a setting may be a dict (``ROI``), which is not hashable.
            setting_names = {setting_name for config in configs.values() for setting_name in config}
            varying_setting_names = sorted(
                setting_name
                for setting_name in setting_names
                if len({repr(config.get(setting_name)) for config in configs.values()}) > 1
            )
            if not varying_setting_names:
                continue

            # Rebuilding the entry from the settings they agree on is what drops a varying one from the
            # device's typed fields and from the description that carries the ones the schema has no
            # field for, in one step and by the same mapping the interface used.
            first_config = next(iter(configs.values()))
            shared_config = {
                setting_name: value
                for setting_name, value in first_config.items()
                if setting_name not in varying_setting_names
            }
            device_metadata_key = self._device_metadata_keys()[device_name]
            device_metadata = metadata["Devices"][device_metadata_key]
            shared_device_metadata = _config_to_miniscope_device_metadata(
                miniscope_config={**shared_config, "name": device_name}
            )
            shared_device_metadata["name"] = self._device_names_camel_case[device_name]
            if "device_model_metadata_key" in device_metadata:
                shared_device_metadata["device_model_metadata_key"] = device_metadata["device_model_metadata_key"]
            metadata["Devices"][device_metadata_key] = shared_device_metadata

            for series_metadata_key, config in configs.items():
                varying_settings = ", ".join(
                    f"{setting_name}: {config[setting_name]}"
                    for setting_name in varying_setting_names
                    if setting_name in config
                )
                series_metadata = metadata["Ophys"]["MicroscopySeries"][series_metadata_key]
                series_metadata["description"] = (
                    f"{series_metadata['description']} Settings the Miniscope was recorded with, which "
                    f"differ across the recordings of this device: {varying_settings}."
                )

    def _get_legacy_metadata(self) -> DeepDict:
        """Assemble the old list-based metadata of the deprecated folder-discovery mode."""
        from neuroconv.tools.roiextractors.roiextractors_pending_deprecation import (
            _get_default_ophys_metadata_old_metadata_list,
        )

        default_ophys_metadata = _get_default_ophys_metadata_old_metadata_list()
        metadata = super().get_metadata()

        # Use the minimum session start time if it was calculated during alignment
        metadata["NWBFile"]["session_start_time"] = self._converter_session_start_time

        # Update Device metadata to use CamelCase names
        if "Ophys" in metadata and "Device" in metadata["Ophys"]:
            for device_metadata in metadata["Ophys"]["Device"]:
                original_name = device_metadata["name"]
                if original_name in self._device_names_camel_case:
                    device_metadata["name"] = self._device_names_camel_case[original_name]

        ophys_interface_names = self._get_ophys_interface_names()

        imaging_plane_metadata = []
        # Required by the schema
        default_optical_channel = default_ophys_metadata["Ophys"]["ImagingPlane"][0]["optical_channel"]
        for device_name in self._device_names:
            device_name_camel = self._device_names_camel_case[device_name]
            metadata_entry = {
                "name": f"ImagingPlane{device_name_camel}",
                "description": f"Imaging plane for {device_name} Miniscope device.",
                "optical_channel": default_optical_channel,
                "device": device_name_camel,
            }
            imaging_plane_metadata.append(metadata_entry)

        series_metadata = []
        for interface_name in ophys_interface_names:
            device_name = self._interface_to_device_mapping[interface_name]
            device_name_camel = self._device_names_camel_case[device_name]
            # Remove slashes and strip device folder name from the end of interface path
            # E.g., "2025_06_12/15_15_04/ACC_miniscope2" -> "2025_06_1215_15_04"
            interface_relative_path = interface_name.replace("/", "")
            # Remove the device name from the end if present
            if interface_relative_path.endswith(device_name):
                interface_relative_path = interface_relative_path[: -len(device_name)]
            imaging_plane_name = f"ImagingPlane{device_name_camel}"
            metadata_entry = {
                "name": f"OnePhotonSeries{device_name_camel}{interface_relative_path}",
                "imaging_plane": imaging_plane_name,
            }
            series_metadata.append(metadata_entry)

        metadata["Ophys"]["OnePhotonSeries"] = series_metadata
        metadata["Ophys"]["ImagingPlane"] = imaging_plane_metadata

        return metadata

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

        # Note: Individual interfaces inherit stub_samples from BaseImagingExtractorInterface
        # which automatically infers it from the add_to_nwbfile method signature

        return schema

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata,
        conversion_options: dict | None = None,
        stub_test: bool = False,
        stub_samples: int = 100,
    ):
        """Add Miniscope interfaces to the provided NWBFile."""
        conversion_options = conversion_options.copy() if conversion_options else {}
        stub_test = conversion_options.pop("stub_test", stub_test)
        stub_samples = conversion_options.pop("stub_samples", stub_samples)

        if metadata is None:
            metadata = self.get_metadata()

        ophys_interface_names = self._get_ophys_interface_names()
        conversion_options_base = {interface_name: {} for interface_name in ophys_interface_names}
        for series_index, interface_name in enumerate(ophys_interface_names):
            if self._user_configuration_file_path is None:
                # The dict-based metadata addresses a series by its metadata key, not by position.
                conversion_options_base[interface_name]["photon_series_index"] = series_index
            conversion_options_base[interface_name]["stub_test"] = stub_test
            conversion_options_base[interface_name]["stub_samples"] = stub_samples

        conversion_options_base.update(self._get_behavior_video_conversion_options())
        conversion_options_base.update(conversion_options)

        super().add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata,
            conversion_options=conversion_options_base,
        )

    def run_conversion(
        self,
        nwbfile_path: str | None = None,
        nwbfile: NWBFile | None = None,
        metadata: dict | None = None,
        overwrite: bool = False,
        stub_test: bool = False,
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
        stub_samples : int, optional
            The number of samples (frames) to include in the subset if `stub_test` is True, by default 100.
        **kwargs
            Additional keyword arguments passed to the parent NWBConverter.run_conversion method.
        """
        # Get existing conversion_options or create empty dict
        conversion_options = kwargs.pop("conversion_options", {})
        ophys_interface_names = self._get_ophys_interface_names()
        conversion_options_base = {interface_name: {} for interface_name in ophys_interface_names}
        for series_index, interface_name in enumerate(ophys_interface_names):
            if self._user_configuration_file_path is None:
                # The dict-based metadata addresses a series by its metadata key, not by position.
                conversion_options_base[interface_name]["photon_series_index"] = series_index
            conversion_options_base[interface_name]["stub_test"] = stub_test
            conversion_options_base[interface_name]["stub_samples"] = stub_samples

        conversion_options_base.update(self._get_behavior_video_conversion_options())
        conversion_options_base.update(conversion_options)

        super().run_conversion(
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            metadata=metadata,
            overwrite=overwrite,
            conversion_options=conversion_options_base,
            **kwargs,
        )
