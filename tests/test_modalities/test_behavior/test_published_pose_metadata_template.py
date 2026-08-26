"""The pose metadata template published in the user guide, checked against the method it documents.

``docs/user_guide/metadata_templates/pose_estimation.yaml`` is written by hand rather than generated,
because the published block shows a fixed set of everything while the method sizes itself to the
recording. These tests are what keeps the two from drifting apart, and what backs the claim the page
makes: that you can copy the block, fill it in and convert with it.
"""

import json
from pathlib import Path

import yaml
from pynwb import read_nwb

from neuroconv.tools.testing.mock_interfaces import MockPoseEstimationInterface

PUBLISHED_TEMPLATES = Path(__file__).parents[3] / "docs" / "user_guide" / "metadata_templates"


def _key_paths(metadata: dict, prefix: tuple = ()) -> set:
    """Every path through a nested dictionary, so two structures compare by shape rather than value."""
    paths = set()
    for key, value in metadata.items():
        paths.add(prefix + (key,))
        if isinstance(value, dict):
            paths |= _key_paths(value, prefix + (key,))
    return paths


def test_published_pose_template_matches_the_method():
    # The page promises the two tabs are the same content, and that what it prints is what the method
    # returns. Compared by key path rather than by value, since the published block leaves blank what
    # the mock records, so the structure must match while the values do not.
    published_yaml = yaml.safe_load((PUBLISHED_TEMPLATES / "pose_estimation.yaml").read_text())
    published_json = json.loads((PUBLISHED_TEMPLATES / "pose_estimation.json").read_text())
    assert published_yaml == published_json

    # Two keypoints, since the published block shows the series entry twice: that is where the
    # structure repeats, once per body part the tracker named.
    interface = MockPoseEstimationInterface(num_nodes=2, metadata_key="pose_estimation")
    template = interface.get_metadata_template()
    template.pop("NWBFile")  # Session-level, and not what this block illustrates.

    assert _key_paths(published_yaml) == _key_paths(template)


def test_published_pose_template_converts_once_filled(tmp_path):
    # The page's actual promise: copy this, fill in the blanks that apply, delete what does not,
    # convert. The camera stands for the delete: a recording whose video is not in the file records it
    # here, and the two video links go instead.
    metadata = yaml.safe_load((PUBLISHED_TEMPLATES / "pose_estimation.yaml").read_text())
    interface = MockPoseEstimationInterface(num_nodes=2, metadata_key="pose_estimation")
    metadata["NWBFile"] = interface.get_metadata()["NWBFile"]

    metadata["DeviceModels"]["camera_model"].update(
        name="CameraModel", manufacturer="Basler", model_number="acA1300-60gm", description="Machine vision camera."
    )
    metadata["Devices"]["camera"].update(name="TopCamera", description="Overhead camera, 30 fps.", serial_number="1234")

    skeleton_metadata = metadata["Pose"]["Skeletons"]["pose_estimation"]
    skeleton_metadata.update(name="SkeletonMouse", subject="mouse_001")

    container_metadata = metadata["Pose"]["PoseEstimations"]["pose_estimation"]
    container_metadata.update(
        name="PoseEstimationTopCamera",
        description="2D keypoints of a mouse in an open field.",
        source_software="DeepLabCut",
        source_software_version="2.3.9",
        scorer="DLC_resnet50_openfield",
    )
    for unrecorded_field in ("source_video_metadata_key", "labeled_video_metadata_key"):
        del container_metadata[unrecorded_field]

    for keypoint_name, series_metadata in container_metadata["PoseEstimationSeries"].items():
        series_metadata.update(
            name=f"PoseEstimationSeries{keypoint_name.capitalize()}",
            description=f"Position of the {keypoint_name}.",
            unit="pixels",
            reference_frame="(0,0) is the top left corner of the video.",
            confidence_definition="Softmax output of the deep neural network.",
        )

    nwbfile_path = tmp_path / "published_pose_template.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

    read_nwbfile = read_nwb(nwbfile_path)
    pose_estimation = read_nwbfile.processing["behavior"]["PoseEstimationTopCamera"]
    assert pose_estimation.scorer == "DLC_resnet50_openfield"
    camera = pose_estimation.devices[0]
    assert camera.name == "TopCamera"
    assert camera.model.manufacturer == "Basler"
    assert pose_estimation.skeleton.name == "SkeletonMouse"
    assert list(pose_estimation.skeleton.nodes) == ["head", "neck"]
    series = pose_estimation.pose_estimation_series["PoseEstimationSeriesHead"]
    assert series.unit == "pixels"
    assert series.reference_frame == "(0,0) is the top left corner of the video."
