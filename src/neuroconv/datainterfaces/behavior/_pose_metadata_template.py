"""The blank structures the pose estimation metadata template is built from.

Every field only the experimenter can supply is ``None``. A pose file records where each body part was
in each frame and almost nothing else, so nearly the whole structure is blank: what the coordinates are
measured from, what unit they are in, what the confidence value means, and which body parts are joined.
"""


def _get_skeleton_template_entry(*, keypoint_names: list[str]) -> dict:
    """A blank skeleton, with the nodes the tracker named already in place.

    ``nodes`` is the one field a pose file does answer, and its order is what ``edges`` indexes into.
    ``subject`` names an individual within the source; leave it blank and the skeleton links to the
    file's own subject.
    """
    return dict(name=None, nodes=list(keypoint_names), edges=None, subject=None)


def _get_pose_estimation_template_entry(
    *, keypoint_names: list[str], skeleton_metadata_key: str, device_metadata_key: str
) -> dict:
    """A blank container, already linked to its skeleton and its camera, with one blank series per keypoint.

    ``reference_frame`` is the field to fill above all others: ``ndx-pose`` requires it, so a container
    written without one carries "(0,0) is unknown." into the file. The two ``*_video_metadata_key``
    fields address ``metadata["Behavior"]["ExternalVideos"]``, so they are answerable only when a video
    interface writes the recording into the same file.
    """
    return dict(
        name=None,
        description=None,
        source_software=None,
        source_software_version=None,
        scorer=None,
        skeleton_metadata_key=skeleton_metadata_key,
        device_metadata_key=device_metadata_key,
        source_video_metadata_key=None,
        labeled_video_metadata_key=None,
        original_videos=None,
        labeled_videos=None,
        dimensions=None,
        PoseEstimationSeries={
            keypoint_name: dict(
                name=None, description=None, unit=None, reference_frame=None, confidence_definition=None
            )
            for keypoint_name in keypoint_names
        },
    )
