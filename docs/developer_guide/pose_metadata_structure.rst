.. _pose_metadata_structure:

Pose Estimation Metadata Structure
==================================

This document describes the pose estimation metadata shape and the decisions that produced it. It is
intended for developers who are contributing new interfaces or modifying existing ones, and the
decisions below are the ones a new pose interface has to follow.

For user-facing documentation on how to annotate pose estimation data, see :ref:`annotate_pose_metadata`.
For the rules that hold across every modality, see :ref:`metadata_principles`.


The Structure
-------------

The pose-specific metadata lives under ``metadata["Pose"]``. The objects it links out to live in the
registries that own them, shared with the other modalities:

.. code-block:: python

    metadata["Devices"] = {
        "top_camera": {  # keyed by metadata_key; "name" is the NWB object's name
            "name": "CameraTop",
            "description": "Camera mounted above the arena.",
        },
    }

    metadata["Behavior"]["ExternalVideos"] = {
        "top_camera_video": {"name": "VideoTopCamera"},
    }

    metadata["Pose"] = {
        "Skeletons": {
            "deep_lab_cut": {
                "name": "SkeletonPoseEstimation",
                "nodes": ["snout", "left_ear", "right_ear"],   # the keypoints, in series order
                "edges": [[0, 1], [0, 2]],                     # optional, indices into "nodes"
                "subject": "mouse_1",                          # optional, an individual in the source,
                                                               #   not the NWB Subject's name
            },
        },
        "PoseEstimations": {
            "deep_lab_cut": {
                "name": "PoseEstimation",
                "description": "Tracking of a mouse in an open field.",
                "skeleton_metadata_key": "deep_lab_cut",       # -> Pose.Skeletons
                "device_metadata_key": "top_camera",           # -> Devices
                "source_video_metadata_key": "top_camera_video",   # -> Behavior.ExternalVideos
                "source_software": "DeepLabCut",
                "source_software_version": "2.3.8",
                "scorer": "DLC_resnet50_openfieldJan1shuffle1",
                "dimensions": [[640, 480]],                    # frame size, one row per video
                "PoseEstimationSeries": {
                    "snout": {                                 # keyed by keypoint name
                        "name": "PoseEstimationSeriesSnout",
                        "description": "Position of the snout.",
                        "reference_frame": "(0,0) is the top-left corner of the frame.",
                        "unit": "pixels",
                        "confidence_definition": "Softmax output of the deep neural network.",
                    },
                },
            },
        },
    }

A skeleton entry requires ``name`` and ``nodes``. Everything in a container entry is optional and is
written only when present, including the entry's own ``name`` and its ``PoseEstimationSeries``. Those
fall back one field at a time to placeholders that name the objects, so partial metadata is enough and
the keypoint arrays alone are sufficient to write a valid file. The container entry itself is not
optional: a ``metadata_key`` naming no entry raises, because that is a caller mistake and not absent
metadata.

The cross-references resolve as follows. ``skeleton_metadata_key`` goes into
``metadata["Pose"]["Skeletons"]``, ``device_metadata_key`` into the shared top-level
``metadata["Devices"]``, and ``source_video_metadata_key`` and ``labeled_video_metadata_key`` into
``metadata["Behavior"]["ExternalVideos"]``. A key naming no entry raises in all four cases.

A pose interface's ``metadata_key`` addresses its container entry and, by default, its skeleton entry as
well. The defaults are fixed snake_case constants: ``"lightning_pose"``,
``"deep_lab_cut_metadata_key"``. ``SLEAPInterface`` is the one derived case and uses
``f"sleap_{track_name}"``, because a multi-animal session instantiates it once per track. See
:ref:`metadata_key_naming` for the cross-modality rule.


Design Decisions
----------------

One container per camera view per subject
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A ``PoseEstimation`` holds the keypoints of one subject as seen from one camera, and an interface writes
one of them. The alternative was writing everything the source file holds. That is what
``SLEAPInterface`` did until `#1965 <https://github.com/catalystneuro/neuroconv/pull/1965>`_: it handed
the whole ``.slp`` to ``sleap_io``, and a multi-animal file came out holding several subjects in
per-video processing modules.

The reason is the NWB data model and not a preference. An NWB file holds one ``Subject``, and
``ndx-pose`` stores one subject per file, so a container holding two animals has nowhere to say which
keypoints belong to whom. A format that carries several tracks or several views therefore names one of
each. That is what ``SLEAPInterface``'s ``track_name`` and ``video_name`` arguments are for, with
``get_available_tracks`` and ``get_available_videos`` to list them. The old behaviour still runs behind
a ``FutureWarning`` until August 2027, delegating to the interface kept verbatim in ``_sleap_legacy.py``.

A consequence worth knowing when writing a new interface: skeletons are reused by NWB name, so two
containers pointing at entries with the same ``name`` link one ``Skeleton`` object. That is how two
camera views of one subject share a skeleton instead of writing two copies of it.


The series are keyed by keypoint name and not by ``metadata_key``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``Skeletons`` and ``PoseEstimations`` are addressed by ``metadata_key``, one entry each per interface.
The ``PoseEstimationSeries`` are not a third registry of that kind. They sit inside their container entry
and their keys are the keypoint names read from the source, so a series is addressed as
``metadata["Pose"]["PoseEstimations"][metadata_key]["PoseEstimationSeries"][keypoint_name]``.

The interface chooses the first key and the tracker chooses the second. A keypoint name is already
unique inside its container and it is what a user editing the metadata will look for, so a
``metadata_key`` layer there would be a handle nobody needs. Note that this is an exception to the
plural-registry convention in :ref:`metadata_principles`: ``PoseEstimationSeries`` reads like a keyed
registry and is not one.


No placeholder camera and no placeholder skeleton
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A container entry naming no device is written without one, and the same holds for the skeleton. Neither
gets the fabricated object that a missing required link gets elsewhere, such as ``PlaceholderMicroscope``
in ophys.

This follows the rule in :ref:`metadata_principles` and lands on its optional branch, because
``ndx-pose`` declares both links optional. The pose-specific half is that the device is not a link users
will usually fill either. No pose format records the camera it was filmed with, so
``device_metadata_key`` and the ``metadata["Devices"]`` entry behind it are always the user's to supply.


The video is linked as an object, not written as a path
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``source_video_metadata_key`` and ``labeled_video_metadata_key`` resolve through
``metadata["Behavior"]["ExternalVideos"]`` to the ``ImageSeries`` a video interface wrote, and the
container links that object. ``ndx-pose`` also accepts ``original_videos`` and ``labeled_videos``, the
file paths the trackers themselves record, and those fields are kept for the formats that carry them.

The link is preferred because it is a reference into the file while a path is a string that may not
travel with it, and because `rly/ndx-pose#57 <https://github.com/rly/ndx-pose/pull/57>`_ deprecates the
path and dimension fields in favour of the link. The cost is an ordering constraint. The pose writer
cannot create the ``ImageSeries``. It belongs to a video interface, and that interface also decides
whether it lands in ``acquisition`` or in the behavior processing module. Both are searched, and a key
naming no object in the file raises and says the video interface has to be part of the same conversion
and has to run first.
