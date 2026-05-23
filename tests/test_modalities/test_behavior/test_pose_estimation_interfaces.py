from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.testing.data_interface_mixins import (
    PoseEstimationInterfaceTestMixin,
)
from neuroconv.tools.testing.mock_interfaces import MockPoseEstimationInterface


class TestMockPoseEstimationInterface(PoseEstimationInterfaceTestMixin):
    data_interface_cls = MockPoseEstimationInterface
    interface_kwargs = dict(num_samples=100, num_nodes=3, seed=42)

    def check_extracted_metadata(self, metadata: dict):
        metadata_key = self.interface.metadata_key
        container_name = metadata_key
        device_name = f"Camera{container_name}"
        skeleton_name = f"Skeleton{container_name}"

        assert metadata["Devices"] == {
            metadata_key: {
                "name": device_name,
                "description": "Mock camera device for pose estimation testing.",
            },
        }

        pose_metadata = metadata["Behavior"]["Pose"]

        skeleton = pose_metadata["Skeletons"][metadata_key]
        assert skeleton["name"] == skeleton_name
        assert skeleton["nodes"] == self.interface.nodes

        container = pose_metadata["PoseEstimations"][metadata_key]
        assert container["name"] == container_name
        assert container["source_software"] == self.interface.source_software
        assert container["device_metadata_key"] == metadata_key
        assert container["skeleton_metadata_key"] == metadata_key
        assert set(container["PoseEstimationSeries"].keys()) == set(self.interface.nodes)


class TestPoseEstimationMetadata:
    """How the dict-based pose-estimation metadata schema links components via ``metadata_key``.

    These tests exercise the linking patterns the schema enables: shared devices across
    containers, shared skeletons across containers, fully decoupled references, and a mixed
    scenario. The pose sub-modality lives under ``metadata["Behavior"]["Pose"]`` and holds the
    ``Skeletons`` and ``PoseEstimation`` registries. Each test constructs its full ``metadata``
    dict inline, with the same ``metadata_key`` variables passed to the interface and used in
    the metadata dict, so the cross-references between interfaces and entries are visible at a
    glance.
    """

    def test_two_containers_share_a_single_device(self):
        """Two containers reference one shared camera via the same ``device_metadata_key``.

        Mirrors the "multi-shank probe" pattern from the ecephys docs: multiple electrode groups
        reference the same ``device_metadata_key``. Here, two pose-estimation containers share
        one camera device. The shared device is created once and reused by both containers.
        """
        metadata_key_top = "view_top"
        metadata_key_side = "view_side"
        shared_device_key = "shared_camera"
        bodyparts = ["head", "neck", "left_shoulder"]

        interface_top = MockPoseEstimationInterface(num_samples=50, num_nodes=3, metadata_key=metadata_key_top)
        interface_side = MockPoseEstimationInterface(num_samples=50, num_nodes=3, metadata_key=metadata_key_side)

        metadata = {
            "Devices": {
                shared_device_key: {"name": "SharedCamera", "description": "Shared multi-view camera."},
            },
            "Behavior": {
                "Pose": {
                    "Skeletons": {
                        metadata_key_top: {"name": "SkeletonViewTop", "nodes": bodyparts},
                        metadata_key_side: {"name": "SkeletonViewSide", "nodes": bodyparts},
                    },
                    "PoseEstimations": {
                        metadata_key_top: {
                            "name": "ViewTop",
                            "description": "Top-view pose estimation container.",
                            "source_software": "MockSourceSoftware",
                            "scorer": "MockScorer",
                            "dimensions": [[640, 480]],
                            "original_videos": ["mock_video_top.mp4"],
                            "device_metadata_key": shared_device_key,
                            "skeleton_metadata_key": metadata_key_top,
                            "PoseEstimationSeries": {
                                bodypart: {
                                    "name": f"PoseEstimationSeries{bodypart.capitalize()}",
                                    "description": f"Mock pose estimation series for {bodypart}.",
                                    "unit": "pixels",
                                    "reference_frame": "(0,0) corresponds to the bottom left corner of the video.",
                                    "confidence_definition": "Softmax output of the deep neural network.",
                                }
                                for bodypart in bodyparts
                            },
                        },
                        metadata_key_side: {
                            "name": "ViewSide",
                            "description": "Side-view pose estimation container.",
                            "source_software": "MockSourceSoftware",
                            "scorer": "MockScorer",
                            "dimensions": [[640, 480]],
                            "original_videos": ["mock_video_side.mp4"],
                            "device_metadata_key": shared_device_key,
                            "skeleton_metadata_key": metadata_key_side,
                            "PoseEstimationSeries": {
                                bodypart: {
                                    "name": f"PoseEstimationSeries{bodypart.capitalize()}",
                                    "description": f"Mock pose estimation series for {bodypart}.",
                                    "unit": "pixels",
                                    "reference_frame": "(0,0) corresponds to the bottom left corner of the video.",
                                    "confidence_definition": "Softmax output of the deep neural network.",
                                }
                                for bodypart in bodyparts
                            },
                        },
                    },
                },
            },
        }

        nwbfile = mock_NWBFile()
        interface_top.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
        interface_side.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        # Exactly one device was created; both pose-estimation containers reference it.
        assert list(nwbfile.devices.keys()) == ["SharedCamera"]
        behavior_module = nwbfile.processing["behavior"]
        assert "ViewTop" in behavior_module.data_interfaces
        assert "ViewSide" in behavior_module.data_interfaces
        for container_name in ("ViewTop", "ViewSide"):
            container = behavior_module[container_name]
            assert len(container.devices) == 1
            assert container.devices[0].name == "SharedCamera"

    def test_two_containers_share_a_single_skeleton(self):
        """Two containers reference one shared skeleton via the same ``skeleton_metadata_key``.

        The shared skeleton is added to the behavior module's ``Skeletons`` collection once and
        reused by both pose-estimation containers.
        """
        metadata_key_a = "dlc_run_a"
        metadata_key_b = "dlc_run_b"
        device_key_a = "camera_a"
        device_key_b = "camera_b"
        shared_skeleton_key = "shared_skeleton"
        bodyparts = ["head", "neck", "left_shoulder"]

        interface_a = MockPoseEstimationInterface(num_samples=50, num_nodes=3, metadata_key=metadata_key_a)
        interface_b = MockPoseEstimationInterface(num_samples=50, num_nodes=3, metadata_key=metadata_key_b)

        metadata = {
            "Devices": {
                device_key_a: {"name": "CameraA", "description": "Camera for run A."},
                device_key_b: {"name": "CameraB", "description": "Camera for run B."},
            },
            "Behavior": {
                "Pose": {
                    "Skeletons": {
                        shared_skeleton_key: {"name": "SharedSkeleton", "nodes": bodyparts},
                    },
                    "PoseEstimations": {
                        metadata_key_a: {
                            "name": "DlcRunA",
                            "description": "Pose estimation container for DLC run A.",
                            "source_software": "MockSourceSoftware",
                            "scorer": "MockScorer",
                            "dimensions": [[640, 480]],
                            "original_videos": ["mock_video_a.mp4"],
                            "device_metadata_key": device_key_a,
                            "skeleton_metadata_key": shared_skeleton_key,
                            "PoseEstimationSeries": {
                                bodypart: {
                                    "name": f"PoseEstimationSeries{bodypart.capitalize()}",
                                    "description": f"Mock pose estimation series for {bodypart}.",
                                    "unit": "pixels",
                                    "reference_frame": "(0,0) corresponds to the bottom left corner of the video.",
                                    "confidence_definition": "Softmax output of the deep neural network.",
                                }
                                for bodypart in bodyparts
                            },
                        },
                        metadata_key_b: {
                            "name": "DlcRunB",
                            "description": "Pose estimation container for DLC run B.",
                            "source_software": "MockSourceSoftware",
                            "scorer": "MockScorer",
                            "dimensions": [[640, 480]],
                            "original_videos": ["mock_video_b.mp4"],
                            "device_metadata_key": device_key_b,
                            "skeleton_metadata_key": shared_skeleton_key,
                            "PoseEstimationSeries": {
                                bodypart: {
                                    "name": f"PoseEstimationSeries{bodypart.capitalize()}",
                                    "description": f"Mock pose estimation series for {bodypart}.",
                                    "unit": "pixels",
                                    "reference_frame": "(0,0) corresponds to the bottom left corner of the video.",
                                    "confidence_definition": "Softmax output of the deep neural network.",
                                }
                                for bodypart in bodyparts
                            },
                        },
                    },
                },
            },
        }

        nwbfile = mock_NWBFile()
        interface_a.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
        interface_b.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        skeletons = nwbfile.processing["behavior"]["Skeletons"]
        assert list(skeletons.skeletons.keys()) == ["SharedSkeleton"]
        for container_name in ("DlcRunA", "DlcRunB"):
            container = nwbfile.processing["behavior"][container_name]
            assert container.skeleton.name == "SharedSkeleton"

    def test_two_containers_with_independent_devices_and_skeletons(self):
        """Two containers point at distinct ``device_metadata_key`` and ``skeleton_metadata_key`` entries.

        Mirrors the "multiple probes" pattern from the ecephys docs: each container has its own
        device and its own skeleton, and nothing is shared between them.
        """
        metadata_key_a = "session_a"
        metadata_key_b = "session_b"
        device_key_a = "camera_a"
        device_key_b = "camera_b"
        skeleton_key_a = "skeleton_a"
        skeleton_key_b = "skeleton_b"
        bodyparts = ["head", "neck", "left_shoulder"]

        interface_a = MockPoseEstimationInterface(num_samples=50, num_nodes=3, metadata_key=metadata_key_a)
        interface_b = MockPoseEstimationInterface(num_samples=50, num_nodes=3, metadata_key=metadata_key_b)

        metadata = {
            "Devices": {
                device_key_a: {"name": "CameraA", "description": "Camera for session A."},
                device_key_b: {"name": "CameraB", "description": "Camera for session B."},
            },
            "Behavior": {
                "Pose": {
                    "Skeletons": {
                        skeleton_key_a: {"name": "SkeletonA", "nodes": bodyparts},
                        skeleton_key_b: {"name": "SkeletonB", "nodes": bodyparts},
                    },
                    "PoseEstimations": {
                        metadata_key_a: {
                            "name": "SessionA",
                            "description": "Pose estimation for session A.",
                            "source_software": "MockSourceSoftware",
                            "scorer": "MockScorer",
                            "dimensions": [[640, 480]],
                            "original_videos": ["mock_video_a.mp4"],
                            "device_metadata_key": device_key_a,
                            "skeleton_metadata_key": skeleton_key_a,
                            "PoseEstimationSeries": {
                                bodypart: {
                                    "name": f"PoseEstimationSeries{bodypart.capitalize()}",
                                    "description": f"Mock pose estimation series for {bodypart}.",
                                    "unit": "pixels",
                                    "reference_frame": "(0,0) corresponds to the bottom left corner of the video.",
                                    "confidence_definition": "Softmax output of the deep neural network.",
                                }
                                for bodypart in bodyparts
                            },
                        },
                        metadata_key_b: {
                            "name": "SessionB",
                            "description": "Pose estimation for session B.",
                            "source_software": "MockSourceSoftware",
                            "scorer": "MockScorer",
                            "dimensions": [[640, 480]],
                            "original_videos": ["mock_video_b.mp4"],
                            "device_metadata_key": device_key_b,
                            "skeleton_metadata_key": skeleton_key_b,
                            "PoseEstimationSeries": {
                                bodypart: {
                                    "name": f"PoseEstimationSeries{bodypart.capitalize()}",
                                    "description": f"Mock pose estimation series for {bodypart}.",
                                    "unit": "pixels",
                                    "reference_frame": "(0,0) corresponds to the bottom left corner of the video.",
                                    "confidence_definition": "Softmax output of the deep neural network.",
                                }
                                for bodypart in bodyparts
                            },
                        },
                    },
                },
            },
        }

        nwbfile = mock_NWBFile()
        interface_a.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
        interface_b.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        assert set(nwbfile.devices.keys()) == {"CameraA", "CameraB"}
        behavior_module = nwbfile.processing["behavior"]
        assert {"SessionA", "SessionB"} <= set(behavior_module.data_interfaces.keys())
        assert set(behavior_module["Skeletons"].skeletons.keys()) == {"SkeletonA", "SkeletonB"}

        container_a = behavior_module["SessionA"]
        container_b = behavior_module["SessionB"]
        assert container_a.devices[0].name == "CameraA"
        assert container_b.devices[0].name == "CameraB"
        assert container_a.skeleton.name == "SkeletonA"
        assert container_b.skeleton.name == "SkeletonB"

    def test_container_can_reference_a_renamed_device_key(self):
        """A container's ``device_metadata_key`` is a pure reference, not tied to the container key.

        The container is keyed by ``metadata_key_session`` but its device entry is keyed by
        ``device_key``; nothing requires the two keys to match. The same is true for
        ``skeleton_metadata_key``. This is the indirection that lets devices and skeletons be
        defined once and shared.
        """
        metadata_key_session = "session_a"
        device_key = "studio_camera"
        skeleton_key = "standard_rat_skeleton"
        bodyparts = ["head", "neck", "left_shoulder"]

        interface = MockPoseEstimationInterface(num_samples=50, num_nodes=3, metadata_key=metadata_key_session)

        metadata = {
            "Devices": {
                device_key: {"name": "StudioCamera", "description": "Overhead studio camera."},
            },
            "Behavior": {
                "Pose": {
                    "Skeletons": {
                        skeleton_key: {"name": "StandardRatSkeleton", "nodes": bodyparts},
                    },
                    "PoseEstimations": {
                        metadata_key_session: {
                            "name": "SessionA",
                            "description": "Pose estimation for session A.",
                            "source_software": "MockSourceSoftware",
                            "scorer": "MockScorer",
                            "dimensions": [[640, 480]],
                            "original_videos": ["mock_video.mp4"],
                            "device_metadata_key": device_key,
                            "skeleton_metadata_key": skeleton_key,
                            "PoseEstimationSeries": {
                                bodypart: {
                                    "name": f"PoseEstimationSeries{bodypart.capitalize()}",
                                    "description": f"Mock pose estimation series for {bodypart}.",
                                    "unit": "pixels",
                                    "reference_frame": "(0,0) corresponds to the bottom left corner of the video.",
                                    "confidence_definition": "Softmax output of the deep neural network.",
                                }
                                for bodypart in bodyparts
                            },
                        },
                    },
                },
            },
        }

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        assert "StudioCamera" in nwbfile.devices
        container = nwbfile.processing["behavior"]["SessionA"]
        assert container.devices[0].name == "StudioCamera"
        assert container.skeleton.name == "StandardRatSkeleton"

    def test_three_containers_with_mixed_device_sharing_and_a_shared_skeleton(self):
        """Three containers, two devices, one shared skeleton — driven entirely through key references.

        Containers ``metadata_key_top`` and ``metadata_key_bottom`` share the
        ``shared_device_key`` device. Container ``metadata_key_side`` uses its own
        ``solo_device_key`` device. All three containers reference a single
        ``shared_skeleton_key`` entry.
        """
        metadata_key_top = "top_view"
        metadata_key_bottom = "bottom_view"
        metadata_key_side = "side_view"
        shared_device_key = "overhead_camera"
        solo_device_key = "side_camera"
        shared_skeleton_key = "rat_skeleton"
        bodyparts = ["head", "neck", "left_shoulder"]

        interface_top = MockPoseEstimationInterface(num_samples=50, num_nodes=3, metadata_key=metadata_key_top)
        interface_bottom = MockPoseEstimationInterface(num_samples=50, num_nodes=3, metadata_key=metadata_key_bottom)
        interface_side = MockPoseEstimationInterface(num_samples=50, num_nodes=3, metadata_key=metadata_key_side)

        metadata = {
            "Devices": {
                shared_device_key: {"name": "OverheadCamera", "description": "Ceiling-mounted camera."},
                solo_device_key: {"name": "SideCamera", "description": "Side-view camera."},
            },
            "Behavior": {
                "Pose": {
                    "Skeletons": {
                        shared_skeleton_key: {"name": "RatSkeleton", "nodes": bodyparts},
                    },
                    "PoseEstimations": {
                        metadata_key_top: {
                            "name": "TopView",
                            "description": "Top-view pose estimation container.",
                            "source_software": "MockSourceSoftware",
                            "scorer": "MockScorer",
                            "dimensions": [[640, 480]],
                            "original_videos": ["mock_video_top.mp4"],
                            "device_metadata_key": shared_device_key,
                            "skeleton_metadata_key": shared_skeleton_key,
                            "PoseEstimationSeries": {
                                bodypart: {
                                    "name": f"PoseEstimationSeries{bodypart.capitalize()}",
                                    "description": f"Mock pose estimation series for {bodypart}.",
                                    "unit": "pixels",
                                    "reference_frame": "(0,0) corresponds to the bottom left corner of the video.",
                                    "confidence_definition": "Softmax output of the deep neural network.",
                                }
                                for bodypart in bodyparts
                            },
                        },
                        metadata_key_bottom: {
                            "name": "BottomView",
                            "description": "Bottom-view pose estimation container.",
                            "source_software": "MockSourceSoftware",
                            "scorer": "MockScorer",
                            "dimensions": [[640, 480]],
                            "original_videos": ["mock_video_bottom.mp4"],
                            "device_metadata_key": shared_device_key,
                            "skeleton_metadata_key": shared_skeleton_key,
                            "PoseEstimationSeries": {
                                bodypart: {
                                    "name": f"PoseEstimationSeries{bodypart.capitalize()}",
                                    "description": f"Mock pose estimation series for {bodypart}.",
                                    "unit": "pixels",
                                    "reference_frame": "(0,0) corresponds to the bottom left corner of the video.",
                                    "confidence_definition": "Softmax output of the deep neural network.",
                                }
                                for bodypart in bodyparts
                            },
                        },
                        metadata_key_side: {
                            "name": "SideView",
                            "description": "Side-view pose estimation container.",
                            "source_software": "MockSourceSoftware",
                            "scorer": "MockScorer",
                            "dimensions": [[640, 480]],
                            "original_videos": ["mock_video_side.mp4"],
                            "device_metadata_key": solo_device_key,
                            "skeleton_metadata_key": shared_skeleton_key,
                            "PoseEstimationSeries": {
                                bodypart: {
                                    "name": f"PoseEstimationSeries{bodypart.capitalize()}",
                                    "description": f"Mock pose estimation series for {bodypart}.",
                                    "unit": "pixels",
                                    "reference_frame": "(0,0) corresponds to the bottom left corner of the video.",
                                    "confidence_definition": "Softmax output of the deep neural network.",
                                }
                                for bodypart in bodyparts
                            },
                        },
                    },
                },
            },
        }

        nwbfile = mock_NWBFile()
        for interface in (interface_top, interface_bottom, interface_side):
            interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        # Exactly two devices were created (the shared one and the solo one).
        assert set(nwbfile.devices.keys()) == {"OverheadCamera", "SideCamera"}

        behavior_module = nwbfile.processing["behavior"]
        assert {"TopView", "BottomView", "SideView"} <= set(behavior_module.data_interfaces.keys())

        # The two top/bottom views share the overhead camera; the side-view has the side camera.
        assert behavior_module["TopView"].devices[0].name == "OverheadCamera"
        assert behavior_module["BottomView"].devices[0].name == "OverheadCamera"
        assert behavior_module["SideView"].devices[0].name == "SideCamera"

        # All three containers reference the same shared skeleton.
        for container_name in ("TopView", "BottomView", "SideView"):
            assert behavior_module[container_name].skeleton.name == "RatSkeleton"

        # Exactly one skeleton instance was registered in the behavior module.
        assert list(behavior_module["Skeletons"].skeletons.keys()) == ["RatSkeleton"]

    def test_user_overrides_propagate_to_nwbfile(self):
        """Names supplied in the metadata dict flow through ``add_to_nwbfile`` into the NWB containers.

        Confirms the writer reads names from the metadata instead of any hardcoded defaults.
        """
        metadata_key = "my_session"
        bodyparts = ["head", "neck", "left_shoulder"]

        interface = MockPoseEstimationInterface(num_samples=50, num_nodes=3, metadata_key=metadata_key)

        metadata = {
            "Devices": {
                metadata_key: {"name": "CustomDeviceName", "description": "Custom camera."},
            },
            "Behavior": {
                "Pose": {
                    "Skeletons": {
                        metadata_key: {"name": "CustomSkeletonName", "nodes": bodyparts},
                    },
                    "PoseEstimations": {
                        metadata_key: {
                            "name": "CustomContainerName",
                            "description": "Custom pose-estimation container.",
                            "source_software": "MockSourceSoftware",
                            "scorer": "MockScorer",
                            "dimensions": [[640, 480]],
                            "original_videos": ["mock_video.mp4"],
                            "device_metadata_key": metadata_key,
                            "skeleton_metadata_key": metadata_key,
                            "PoseEstimationSeries": {
                                bodypart: {
                                    "name": f"PoseEstimationSeries{bodypart.capitalize()}",
                                    "description": f"Mock pose estimation series for {bodypart}.",
                                    "unit": "pixels",
                                    "reference_frame": "(0,0) corresponds to the bottom left corner of the video.",
                                    "confidence_definition": "Softmax output of the deep neural network.",
                                }
                                for bodypart in bodyparts
                            },
                        },
                    },
                },
            },
        }

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        assert "CustomContainerName" in nwbfile.processing["behavior"].data_interfaces
        assert "CustomDeviceName" in nwbfile.devices
        skeletons = nwbfile.processing["behavior"]["Skeletons"]
        assert "CustomSkeletonName" in skeletons.skeletons
