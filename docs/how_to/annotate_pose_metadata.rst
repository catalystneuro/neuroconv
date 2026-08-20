.. _annotate_pose_metadata:

How to Annotate Pose Estimation Metadata
========================================

In general, neuroconv fills in as much metadata as it can extract from the source files. A pose
estimation output records where each body part was in each frame and very little else, so a conversion
you run without adding any metadata writes just that: one series per keypoint, a skeleton naming them,
and nothing describing the recording they came from.

.. code-block:: python

    from neuroconv.tools.testing import MockPoseEstimationInterface

    interface = MockPoseEstimationInterface(num_nodes=3)
    nwbfile = interface.create_nwbfile()

.. admonition:: Resulting structure
   :class: tip

   .. code-block:: text

       processing/behavior
       ├── MockPoseEstimation                 PoseEstimation
       │   ├── PoseEstimationSeriesHead       data (1000, 2)
       │   ├── PoseEstimationSeriesNeck       data (1000, 2)
       │   └── PoseEstimationSeriesLeftShou…  data (1000, 2)
       └── Skeletons
           └── SkeletonMockPoseEstimation     nodes ['head', 'neck', 'left_shoulder']

The examples here use :py:class:`~neuroconv.tools.testing.mock_interfaces.MockPoseEstimationInterface`,
which synthesizes keypoints instead of reading a file, so every snippet runs as written with no data to
download. Everything after the constructor is the same for any pose interface: swap in the one for your
tracker, with the arguments its format needs, and annotate the metadata exactly as shown. The
:ref:`pose estimation section of the Conversion Gallery <conversion_gallery_pose_estimation>` shows how
to construct each one.

A **keypoint** is one tracked body part and becomes one ``PoseEstimationSeries``. A **container** is one
camera view of one subject: it holds those series, a ``Skeleton`` naming the keypoints and the edges
between them, and optionally the camera that recorded them. Annotating a recording is filling in what the
tracker could not know.

How to Annotate a Pose Estimation Session
-----------------------------------------

The baseline setup: one camera above the arena, one subject, one tracker run. Everything the other setups
do is a variation on this one, so it is worked in full.

**Annotate the PoseEstimation container**

A ``PoseEstimation`` is one camera view of one subject. It holds one time series per keypoint, and links
out to the skeleton of the subject, where the structure of those keypoints is described.

.. code-block:: python
   :emphasize-lines: 7-12

    from neuroconv.tools.testing import MockPoseEstimationInterface

    interface = MockPoseEstimationInterface(num_nodes=3)
    metadata = interface.get_metadata()
    key = interface.metadata_key

    container = metadata["Pose"]["PoseEstimations"][key]
    container["name"] = "PoseEstimationTopCamera"
    container["description"] = "2D keypoints of a mouse in an open field, from the overhead camera."
    container["source_software"] = "DeepLabCut"
    container["source_software_version"] = "2.3.9"
    container["scorer"] = "DLC_resnet50_openfield"

``name`` is how the container is identified in the file, so give it one that says which camera or which
subject it holds.

``description`` is prose, and the schema calls it the pose estimation procedure and output.

``source_software``, ``source_software_version`` and ``scorer`` say which tracker and which trained model
produced the coordinates, which is what someone needs to reproduce them or to judge them against a later
version of the same tool. An interface fills these in when the format records them, and DeepLabCut and
SLEAP do; set them yourself when yours does not.

**Annotate the PoseEstimationSeries data**

One ``PoseEstimationSeries`` per keypoint holds where that body part was in each frame, an x and a y, or
an x, y and z, with a confidence beside it. Numbers are all it has, and nothing in them says what they
measure. Four fields carry that, and all of them are set per series, so a container whose keypoints were
tracked under different conditions can say so keypoint by keypoint.

.. code-block:: python
   :emphasize-lines: 14-36

    from neuroconv.tools.testing import MockPoseEstimationInterface

    interface = MockPoseEstimationInterface(num_nodes=3)
    metadata = interface.get_metadata()
    key = interface.metadata_key

    container = metadata["Pose"]["PoseEstimations"][key]
    container["name"] = "PoseEstimationTopCamera"
    container["description"] = "2D keypoints of a mouse in an open field, from the overhead camera."
    container["source_software"] = "DeepLabCut"
    container["source_software_version"] = "2.3.9"
    container["scorer"] = "DLC_resnet50_openfield"

    unit = "pixels"
    reference_frame = "(0,0) is the top left corner of the video."
    confidence_definition = "Softmax output of the deep neural network."

    series = container["PoseEstimationSeries"]
    series["head"].update(
        unit=unit,
        reference_frame=reference_frame,
        confidence_definition=confidence_definition,
        description="Tip of the snout.",
    )
    series["neck"].update(
        unit=unit,
        reference_frame=reference_frame,
        confidence_definition=confidence_definition,
        description="Base of the skull.",
    )
    series["left_shoulder"].update(
        unit=unit,
        reference_frame=reference_frame,
        confidence_definition=confidence_definition,
        description="Left shoulder joint.",
    )

``unit`` is what the coordinates are measured in, pixels for a raw tracker output and millimetres or
centimetres once they have been calibrated against something of known size. It is what lets a reader
turn a distance into a physical one, compare a speed against another study, or pool sessions filmed at
different resolutions or camera heights, none of which is possible while the numbers are in units nobody
has named.

``reference_frame`` says where (0,0) sits and which way the axes run. It is what relates the coordinates
to the apparatus rather than to the image, so a reader can say a subject was in the left arm of the maze
or three centimetres from the wall, and it is what lets pose be combined with anything else spatial in
the file. ``ndx-pose`` requires it, so a value is written whether you supply one or not, and what the
writer supplies is "(0,0) is unknown.".

``confidence_definition`` says what the confidence number is. DeepLabCut's likelihood, SLEAP's instance
score and Lightning Pose's confidence are computed differently, so the number alone does not tell a
reader whether 0.6 is good, where to put a threshold when filtering, or whether a value from your file
means what the same value means in another. Stating it is what makes filtering reproducible by someone
who was not there.

``description`` says which body part the series is, in whatever detail the keypoint name leaves out. A
name like ``paw1LH`` is a label the tracker's author chose, and the description is where it becomes left
hind paw.

**Annotate the subject skeleton**

A ``Skeleton`` describes the subject rather than the recording: which body parts the tracker was trained
to find, how they connect, and whose body they belong to. It is the one object on this page that would
still be true if you filmed the same subject again tomorrow with a different camera, which is why several
containers can share one, and why it lives beside the containers in the file rather than inside any of
them. It carries a ``name`` and three fields.

.. code-block:: python
   :emphasize-lines: 38-42

    from neuroconv.tools.testing import MockPoseEstimationInterface

    interface = MockPoseEstimationInterface(num_nodes=3)
    metadata = interface.get_metadata()
    key = interface.metadata_key

    container = metadata["Pose"]["PoseEstimations"][key]
    container["name"] = "PoseEstimationTopCamera"
    container["description"] = "2D keypoints of a mouse in an open field, from the overhead camera."
    container["source_software"] = "DeepLabCut"
    container["source_software_version"] = "2.3.9"
    container["scorer"] = "DLC_resnet50_openfield"

    unit = "pixels"
    reference_frame = "(0,0) is the top left corner of the video."
    confidence_definition = "Softmax output of the deep neural network."

    series = container["PoseEstimationSeries"]
    series["head"].update(
        description="Tip of the snout.",
        unit=unit,
        reference_frame=reference_frame,
        confidence_definition=confidence_definition,
    )
    series["neck"].update(
        description="Base of the skull.",
        unit=unit,
        reference_frame=reference_frame,
        confidence_definition=confidence_definition,
    )
    series["left_shoulder"].update(
        description="Left shoulder joint.",
        unit=unit,
        reference_frame=reference_frame,
        confidence_definition=confidence_definition,
    )

    skeleton = metadata["Pose"]["Skeletons"][key]
    skeleton["name"] = "SkeletonMouse"
    skeleton["nodes"] = ["head", "neck", "left_shoulder"]
    skeleton["edges"] = [[0, 1], [1, 2]]  # head-neck, neck-left shoulder
    skeleton["subject"] = "mouse_001"

``nodes`` are the body parts, in the order their series are written. The interface fills them from the
keypoints it read, so this is the one field you usually leave alone; the order matters because it is what
the edges index into, and reordering it silently changes what they mean.

``edges`` say which body parts are joined, and they are what a skeleton is really for, since the nodes
repeat what the series already say. Which parts you join is a modelling decision rather than an
anatomical fact: it records what whoever built the project decided was worth relating, and two labs
tracking the same animal can draw different skeletons. The file records that decision nowhere else. A
reader who has it can compute a limb length or a joint angle, which are only meaningful along a segment
you declared, and can draw the subject rather than a cloud of points; a reader without it has to guess
your intent or ask you. Most trackers already know the edges, since connectivity is drawn when the
project is set up rather than estimated per frame, and a bottom-up multi-animal model uses it to group
keypoints into individuals. Lightning Pose is the exception, predicting each keypoint independently and
recording no connectivity at all.

``subject`` names the individual within the source. The skeleton is linked to the file's ``Subject`` when
the two ids match, which is what ties a body plan to a subject for anyone reading the file. A file
without a ``Subject``, or one whose id differs, gets a skeleton linked to nothing, which is how you say
these keypoints belong to somebody other than the file's subject. That case is
:ref:`several subjects in one recording <annotate_pose_several_subjects>` below.

**Link the source video**

Keypoints are a claim about a video, and a file that does not say which video cannot be checked. If you
have the original video, put it in the same file with
:doc:`ExternalVideoInterface <../conversion_examples_gallery/behavior/video>`, which stores it as an
``ImageSeries`` pointing at the file on disk and gives it an entry in
``metadata["Behavior"]["ExternalVideos"]``, then name that entry from the container.

.. code-block:: python
   :emphasize-lines: 44-56

    from neuroconv.tools.testing import MockPoseEstimationInterface

    interface = MockPoseEstimationInterface(num_nodes=3)
    metadata = interface.get_metadata()
    key = interface.metadata_key

    container = metadata["Pose"]["PoseEstimations"][key]
    container["name"] = "PoseEstimationTopCamera"
    container["description"] = "2D keypoints of a mouse in an open field, from the overhead camera."
    container["source_software"] = "DeepLabCut"
    container["source_software_version"] = "2.3.9"
    container["scorer"] = "DLC_resnet50_openfield"

    unit = "pixels"
    reference_frame = "(0,0) is the top left corner of the video."
    confidence_definition = "Softmax output of the deep neural network."

    series = container["PoseEstimationSeries"]
    series["head"].update(
        description="Tip of the snout.",
        unit=unit,
        reference_frame=reference_frame,
        confidence_definition=confidence_definition,
    )
    series["neck"].update(
        description="Base of the skull.",
        unit=unit,
        reference_frame=reference_frame,
        confidence_definition=confidence_definition,
    )
    series["left_shoulder"].update(
        description="Left shoulder joint.",
        unit=unit,
        reference_frame=reference_frame,
        confidence_definition=confidence_definition,
    )

    skeleton = metadata["Pose"]["Skeletons"][key]
    skeleton["name"] = "SkeletonMouse"
    skeleton["nodes"] = ["head", "neck", "left_shoulder"]
    skeleton["edges"] = [[0, 1], [1, 2]]  # head-neck, neck-left shoulder
    skeleton["subject"] = "mouse_001"

    video_metadata_key = "source_video_key"      # the metadata_key the video interface was built with
    camera_metadata_key = "top_camera_key"

    metadata["Behavior"]["ExternalVideos"][video_metadata_key] = dict(
        name="OverheadVideo",
        description="Raw video the tracker ran on.",
        device_metadata_key=camera_metadata_key,
    )
    metadata["Devices"][camera_metadata_key] = dict(
        name="TopCamera", description="Overhead camera, 30 fps."
    )

    container["source_video_metadata_key"] = video_metadata_key

``source_video_metadata_key`` names an entry in ``metadata["Behavior"]["ExternalVideos"]``, which the
writer resolves to the ``ImageSeries`` that interface wrote. The link is a reference to the object rather
than a path, so it cannot rot, and it makes the pairing explicit rather than something a reader infers
from names, which matters as soon as a file holds two trackers over one recording or one tracker over
several recordings. It also brings the camera along, since the ``ImageSeries`` carries its own
``Device``. The video interface has to run before the pose one in the same conversion, since the writer
resolves the link against an object that must already be in the file.

``labeled_video_metadata_key`` does the same for a tracker's annotated output video, when you have one.

``device_metadata_key`` names an entry in ``metadata["Devices"]``, and is only needed when there is no
linked video: with no ``ImageSeries`` to carry it, nothing else in the file records that a camera
existed.

.. admonition:: The file so far
   :class: tip

   .. code-block:: text

       processing/behavior
       ├── PoseEstimationTopCamera            PoseEstimation   description, unit, reference frame
       │   ├── PoseEstimationSeriesHead       data (1000, 2)
       │   ├── PoseEstimationSeriesNeck       data (1000, 2)
       │   └── PoseEstimationSeriesLeftShou…  data (1000, 2)
       └── Skeletons
           └── SkeletonMouse                  nodes, edges, subject

       acquisition
       └── OverheadVideo                      ImageSeries      linked as the container's source_video

       devices
       └── TopCamera                          carried by the ImageSeries

How to Annotate Several Camera Views of One Subject
----------------------------------------------------

Two cameras filming the same mouse, each tracked separately. One subject means one file, and each view is
its own ``PoseEstimation`` with its own camera. Use a converter so both interfaces write into the same
file, and give each a distinct registry key.

Both views normally share one ``Skeleton``. A skeleton carries no coordinates: it is the body plan, which
parts exist and which are connected, plus the link to the subject. The per-view difference is in the
``PoseEstimationSeries`` data, where the coordinates are. Two cameras looking at one mouse see the same
body, so writing two skeletons would assert two anatomies. The exception is when the trackers were trained
on different keypoint sets, for instance a side view that labels a paw the overhead view never sees; then
the node lists genuinely differ and each view wants its own skeleton.

.. code-block:: python
   :emphasize-lines: 17-36

    from neuroconv import NWBConverter
    from neuroconv.tools.testing import MockPoseEstimationInterface


    class TwoViewConverter(NWBConverter):
        data_interface_classes = dict(Top=MockPoseEstimationInterface, Side=MockPoseEstimationInterface)


    converter = TwoViewConverter(
        source_data=dict(
            Top=dict(num_nodes=3, metadata_key="pose_top"),
            Side=dict(num_nodes=3, metadata_key="pose_side"),
        )
    )
    metadata = converter.get_metadata()

    top_camera_key = "top_camera"
    side_camera_key = "side_camera"
    skeleton_key = "shared_skeleton"

    metadata["Devices"][top_camera_key] = dict(name="TopCamera")
    metadata["Devices"][side_camera_key] = dict(name="SideCamera")

    metadata["Pose"]["Skeletons"][skeleton_key] = dict(
        name="SkeletonMouse", nodes=["head", "neck", "left_shoulder"], edges=[[0, 1], [1, 2]]
    )

    top_view = metadata["Pose"]["PoseEstimations"]["pose_top"]
    top_view["name"] = "PoseEstimationTop"
    top_view["device_metadata_key"] = top_camera_key
    top_view["skeleton_metadata_key"] = skeleton_key       # same body plan, written once

    side_view = metadata["Pose"]["PoseEstimations"]["pose_side"]
    side_view["name"] = "PoseEstimationSide"
    side_view["device_metadata_key"] = side_camera_key
    side_view["skeleton_metadata_key"] = skeleton_key

Two containers pointing at one ``skeleton_metadata_key`` produce one ``Skeleton`` in the file, which both
link to.

.. _annotate_pose_several_subjects:

How to Annotate Several Subjects in One Recording
--------------------------------------------------

Two mice in the same arena, tracked as two identities by SLEAP or as two individuals by DeepLabCut. An
NWB file has a single root-level ``Subject`` and ``ndx-pose`` is built on that, so which of the two
arrangements below you want turns on what the second subject is to your experiment.

One file per subject
~~~~~~~~~~~~~~~~~~~~

The usual answer. Each interface reads one individual, each file gets its own ``Subject``, and nothing
extra has to be said in the pose metadata, since the skeleton links to the file's own subject.

An NWB file's ``Subject`` carries ``sex``, ``genotype``, ``strain`` and ``age``, and in a social
recording those usually differ between the subjects and are often the experiment itself, a mutant male
with a wild-type female. One file per subject is what lets each of them carry its own.

.. code-block:: python
   :emphasize-lines: 6-7

    from neuroconv.tools.testing import MockPoseEstimationInterface

    for subject_id in ["mouse_001", "mouse_002"]:
        interface = MockPoseEstimationInterface(num_nodes=3)
        metadata = interface.get_metadata()
        metadata["Subject"] = dict(subject_id=subject_id, species="Mus musculus")
        interface.run_conversion(nwbfile_path=f"session_001_{subject_id}.nwb", metadata=metadata)

Which individual an interface reads is what its own arguments select:
:py:meth:`~neuroconv.datainterfaces.behavior.sleap.sleapdatainterface.SLEAPInterface.get_available_tracks`
lists the identities in a ``.slp`` and ``track_name`` picks one, and ``subject_name`` picks one of the
individuals in a multi-animal DeepLabCut project. Neither is a name you chose: ``track_0`` and ``ind1``
are the tracker's labels for a trajectory, so map them to your own ``subject_id`` as above.

Both subjects in one file
~~~~~~~~~~~~~~~~~~~~~~~~~

Worth it when the video, the trials and often the electrophysiology are shared and separate files
duplicate all of it. Each subject brings its own interface and ``metadata_key``, its own container and
skeleton names, and its own ``subject``. Whether they also bring their own camera is the one thing that
varies with the setup: two subjects filmed by one overhead camera share a device, two filmed separately
do not.

.. code-block:: python
   :emphasize-lines: 17-30

    from neuroconv import NWBConverter
    from neuroconv.tools.testing import MockPoseEstimationInterface


    class SocialConverter(NWBConverter):
        data_interface_classes = dict(Mouse1=MockPoseEstimationInterface, Mouse2=MockPoseEstimationInterface)


    converter = SocialConverter(
        source_data=dict(
            Mouse1=dict(num_nodes=3, metadata_key="pose_mouse_001"),
            Mouse2=dict(num_nodes=3, metadata_key="pose_mouse_002"),
        )
    )
    metadata = converter.get_metadata()

    metadata["Subject"] = dict(subject_id="mouse_001", species="Mus musculus")

    camera_key = "arena_camera"
    metadata["Devices"][camera_key] = dict(name="ArenaCamera")

    first = metadata["Pose"]["PoseEstimations"]["pose_mouse_001"]
    first["name"] = "PoseEstimationMouse001"
    first["device_metadata_key"] = camera_key
    metadata["Pose"]["Skeletons"]["pose_mouse_001"].update(name="SkeletonMouse001", subject="mouse_001")

    second = metadata["Pose"]["PoseEstimations"]["pose_mouse_002"]
    second["name"] = "PoseEstimationMouse002"
    second["device_metadata_key"] = camera_key
    metadata["Pose"]["Skeletons"]["pose_mouse_002"].update(name="SkeletonMouse002", subject="mouse_002")

``mouse_001`` matches the file's ``Subject`` and its skeleton is linked to it. ``mouse_002`` does not, so
its skeleton is written unlinked rather than pointed at the wrong subject. That is what you are trading:
the second subject is identified by the names you chose and by ``subject``, not by anything NWB models.
