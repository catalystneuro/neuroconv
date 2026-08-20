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

**Name what appears in the file**

Every object the conversion writes gets a name, and the writer falls back to generic ones:
``PoseEstimation``, ``SkeletonPoseEstimation``, ``PoseEstimationSeriesHead``. Those names are what
someone browsing your file sees first, and in a session holding several recordings they are the
only thing telling one apart from another, so a name that says which camera or which subject this is
saves a reader from opening every container to find out. Names are set through the registries under the
top-level ``metadata["Pose"]``, addressed by the interface's ``metadata_key``.

.. code-block:: python
   :emphasize-lines: 7-9

    from neuroconv.tools.testing import MockPoseEstimationInterface

    interface = MockPoseEstimationInterface(num_nodes=3)
    metadata = interface.get_metadata()
    key = interface.metadata_key

    container = metadata["Pose"]["PoseEstimations"][key]
    container["name"] = "PoseEstimationTopCamera"
    metadata["Pose"]["Skeletons"][key]["name"] = "SkeletonMouse"

**Say what the numbers mean**

A pose file records numbers: an x, a y and a confidence per keypoint per frame, and nothing saying
what any of them measure. neuroconv writes none of that unless
you do, because any value it chose would be invented rather than read. Three fields carry it.

``unit`` is what the coordinates are measured in, pixels for a raw tracker output and millimetres or
centimetres once they have been calibrated against something of known size. It is what lets a reader
turn a distance into a physical one, compare a speed against another study, or pool sessions filmed at
different resolutions or camera heights, none of which is possible while the numbers are in units nobody
has named.

``reference_frame`` says where (0,0) sits and which way the axes run. It is what relates the coordinates
to the apparatus rather than to the image, so a reader can say an animal was in the left arm of the maze
or three centimetres from the wall, and it is what lets pose be combined with anything else spatial in
the file. ``ndx-pose`` requires it, so a value is written whether you supply one or not, and what the
writer supplies is "(0,0) is unknown.".

``confidence_definition`` says what the confidence number is. DeepLabCut's likelihood, SLEAP's instance
score and Lightning Pose's confidence are computed differently, so the number alone does not tell a
reader whether 0.6 is good, where to put a threshold when filtering, or whether a value from your file
means what the same value means in another. Stating it is what makes filtering reproducible by someone
who was not there.

All three are set per series, and the container's ``description`` is where the recording itself is
described.

.. code-block:: python
   :emphasize-lines: 11-26

    from neuroconv.tools.testing import MockPoseEstimationInterface

    interface = MockPoseEstimationInterface(num_nodes=3)
    metadata = interface.get_metadata()
    key = interface.metadata_key

    container = metadata["Pose"]["PoseEstimations"][key]
    container["name"] = "PoseEstimationTopCamera"
    metadata["Pose"]["Skeletons"][key]["name"] = "SkeletonMouse"

    unit = "pixels"
    reference_frame = "(0,0) is the top left corner of the video."
    confidence_definition = "Softmax output of the deep neural network."

    series = container["PoseEstimationSeries"]
    series["head"].update(
        unit=unit, reference_frame=reference_frame, confidence_definition=confidence_definition
    )
    series["neck"].update(
        unit=unit, reference_frame=reference_frame, confidence_definition=confidence_definition
    )
    series["left_shoulder"].update(
        unit=unit, reference_frame=reference_frame, confidence_definition=confidence_definition
    )

    container["description"] = "2D keypoints of a mouse in an open field, from the overhead camera."

**Describe the skeleton**

A ``Skeleton`` is the body plan behind the keypoints, and it has three fields.

``nodes`` are the body parts, in the order their series are written. The interface fills them from the
keypoints it read, so this is the one field you usually leave alone; the order matters because it is what
the edges index into, and reordering it silently changes what they mean.

``edges`` say which body parts are joined, and they are what a skeleton is really for, since the nodes
repeat what the series already say. Which parts you join is a modelling decision rather than an
anatomical fact: it records what whoever built the project decided was worth relating, and two labs
tracking the same animal can draw different skeletons. The file records that decision nowhere else. A
reader who has it can compute a limb length or a joint angle, which are only meaningful along a segment
you declared, and can draw the subject rather than a cloud of points; a reader without it has to guess
your intent or ask you. Most trackers already
know the edges, since connectivity is drawn when the project is set up rather than estimated per frame,
and a bottom-up multi-animal model uses it to group keypoints into individuals. Lightning Pose is the
exception, predicting each keypoint independently and recording no connectivity at all.

``subject`` names the individual within the source. The skeleton is linked to the file's ``Subject`` when
the two ids match, which is what ties a body plan to a subject for anyone reading the file. A file without
a ``Subject``, or one whose id differs, gets a skeleton linked to nothing, which is how you say these
keypoints belong to somebody other than the file's subject.

.. code-block:: python
   :emphasize-lines: 28-31

    from neuroconv.tools.testing import MockPoseEstimationInterface

    interface = MockPoseEstimationInterface(num_nodes=3)
    metadata = interface.get_metadata()
    key = interface.metadata_key

    container = metadata["Pose"]["PoseEstimations"][key]
    container["name"] = "PoseEstimationTopCamera"
    metadata["Pose"]["Skeletons"][key]["name"] = "SkeletonMouse"

    unit = "pixels"
    reference_frame = "(0,0) is the top left corner of the video."
    confidence_definition = "Softmax output of the deep neural network."

    series = container["PoseEstimationSeries"]
    series["head"].update(
        unit=unit, reference_frame=reference_frame, confidence_definition=confidence_definition
    )
    series["neck"].update(
        unit=unit, reference_frame=reference_frame, confidence_definition=confidence_definition
    )
    series["left_shoulder"].update(
        unit=unit, reference_frame=reference_frame, confidence_definition=confidence_definition
    )

    container["description"] = "2D keypoints of a mouse in an open field, from the overhead camera."

    skeleton = metadata["Pose"]["Skeletons"][key]
    skeleton["nodes"] = ["head", "neck", "left_shoulder"]
    skeleton["edges"] = [[0, 1], [1, 2]]  # head-neck, neck-left shoulder
    skeleton["subject"] = "mouse_001"

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

How to Link a Pose Estimation to its Source Video
-------------------------------------------------

Keypoints are a claim about a video, and a file that does not say which video cannot be checked. A
reader who wants to know whether a low-confidence stretch is an occlusion or a tracking failure has to
watch the frames, and a reader assembling a dataset needs to know that two sessions came from different
cameras.

If you have the original video, it should go into the same file. That is what
:doc:`ExternalVideoInterface <../conversion_examples_gallery/behavior/video>` is for: it stores the video
as an ``ImageSeries`` pointing at the file on disk, and gives it an entry in
``metadata["Behavior"]["ExternalVideos"]``.

On top of storing it, the pose container can formally link to it. The link is a reference to the object
rather than a path, so it cannot rot, and it makes the pairing explicit rather than something a reader
infers from names. That matters most when a file holds more than one of either: two trackers run over the
same recording, or one tracker run over several camera recordings, and nothing but the link says which
output came from which video. It also brings the camera along, since the ``ImageSeries`` carries its own
``Device``, so the pose container needs none of its own.

.. code-block:: python

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

    # The pose container names that entry, and the writer resolves it to the ImageSeries.
    container["source_video_metadata_key"] = video_metadata_key

The video interface has to run before the pose one in the same conversion, since the writer resolves the
link against an object that must already be in the file. Use ``labeled_video_metadata_key`` the same way
for a tracker's annotated output video, when you have one.

If the video cannot go into the file, there is nothing to link, so add the camera to the pose container
yourself: with no ``ImageSeries`` to carry it, nothing else in the file records that a camera existed.

.. code-block:: python

    camera_metadata_key = "top_camera_key"

    metadata["Devices"][camera_metadata_key] = dict(
        name="TopCamera", description="Overhead camera, 30 fps."
    )
    container["device_metadata_key"] = camera_metadata_key

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
