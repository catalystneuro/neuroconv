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

       devices                                (empty: no pose format records a camera)

   Every series carries ``reference_frame`` "(0,0) is unknown." and no ``confidence_definition``,
   because nothing in the source said what the origin is or how the confidence was computed.

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

**Name the objects.** Every object the conversion writes gets a name, and the writer falls back to
generic ones: ``PoseEstimation``, ``SkeletonPoseEstimation``, ``PoseEstimationSeriesHead``. Those names
are what someone browsing your file sees first, and in a session holding several recordings they are the
only thing telling one apart from another, so a name that says which camera or which subject this is
saves a reader from opening every container to find out. Names are set through the registries under the
top-level ``metadata["Pose"]``, addressed by the interface's ``metadata_key``.

.. code-block:: python

    metadata = interface.get_metadata()
    key = interface.metadata_key

    container = metadata["Pose"]["PoseEstimations"][key]
    container["name"] = "PoseEstimationTopCamera"
    metadata["Pose"]["Skeletons"][key]["name"] = "SkeletonMouse"

**Describe what the coordinates mean.** A pose file records numbers: an x, a y and a confidence per
keypoint per frame. What those numbers are measured in, where their origin sits, and what the confidence
value represents are not in it. Without them a reader cannot convert your coordinates to millimetres,
cannot compare them to another session filmed from a different angle, and cannot tell whether a
confidence of 0.6 is good. neuroconv writes none of them unless you do, because any value it chose would
be invented rather than read. The one exception is ``reference_frame``, which ``ndx-pose`` requires, so
the writer supplies "(0,0) is unknown." when you leave it out; that is a statement of ignorance sitting
in your file, and replacing it is the most valuable line on this page. They are set per series, and the
container's ``description`` is where the recording itself is described.

.. code-block:: python

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

**Describe the skeleton.** A ``Skeleton`` is the body plan behind the keypoints, and it has three fields.

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

    skeleton = metadata["Pose"]["Skeletons"][key]
    skeleton["nodes"] = ["head", "neck", "left_shoulder"]
    skeleton["edges"] = [[0, 1], [1, 2]]  # head-neck, neck-left shoulder
    skeleton["subject"] = "mouse_001"

**Record where the frames came from.** Keypoints are a claim about a video, and a file that does not say
which video cannot be checked. A reader who wants to see whether a low-confidence stretch is an occlusion
or a tracking failure has to watch the frames, and a reader assembling a dataset needs to know that two
sessions came from different cameras. Two things can carry it, and which you want depends on whether the
video itself is in the file.

If a video interface wrote the recording into the file as an ``ImageSeries``, link that object. The link
is a reference rather than a path, so it cannot rot, and the ``ImageSeries`` already carries its own
camera ``Device``, so this one link records both the recording and the instrument. Adding a camera to the
container as well is a second link to the same object.

.. code-block:: python

    container["source_video_metadata_key"] = "original_video"  # -> metadata["Behavior"]["ExternalVideos"]

If the video is not in the file, because it stays on disk or you have only the tracker output, then give
its path and add the camera to the container, since nothing else in the file records that one existed.
Prefer a path relative to the NWB file over an absolute one: the schema notes that these strings are
fragile, and an absolute path from the machine that ran the tracker almost never resolves on the machine
that reads the file.

.. code-block:: python

    container["original_videos"] = ["videos/top_camera.mp4"]  # relative to the NWB file

    metadata["Devices"]["top_camera"] = dict(name="TopCamera", description="Overhead camera, 30 fps.")
    container["device_metadata_key"] = "top_camera"

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

       devices
       └── TopCamera

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

    metadata["Devices"]["top_camera"] = dict(name="TopCamera")
    metadata["Devices"]["side_camera"] = dict(name="SideCamera")

    metadata["Pose"]["Skeletons"]["shared_skeleton"] = dict(
        name="SkeletonMouse", nodes=["head", "neck", "left_shoulder"], edges=[[0, 1], [1, 2]]
    )

    for view, device_key in [("top", "top_camera"), ("side", "side_camera")]:
        entry = metadata["Pose"]["PoseEstimations"][f"pose_{view}"]
        entry["name"] = f"PoseEstimation{view.capitalize()}"
        entry["device_metadata_key"] = device_key
        entry["skeleton_metadata_key"] = "shared_skeleton"  # same body plan, written once

Two containers pointing at one ``skeleton_metadata_key`` produce one ``Skeleton`` in the file, which both
link to.

How to Annotate Several Subjects in One Recording
--------------------------------------------------

Two mice in the same arena, tracked as two identities by SLEAP or as two individuals by DeepLabCut. An
NWB file has a single root-level ``Subject`` and ``ndx-pose`` is built on that, so in most cases you
want **one file per subject**: each interface reads one individual, each file gets its own ``Subject``,
and nothing extra has to be said in the pose metadata.

.. code-block:: python

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

An NWB file's ``Subject`` carries ``sex``, ``genotype``, ``strain`` and ``age``, and in a social
recording those usually differ between the subjects and are often the experiment itself, a mutant male
with a wild-type female. One file per subject is what lets each of them carry its own.

If you would rather keep both subjects in one file, because the video, the trials and often the
electrophysiology are shared and separate files duplicate all of it, the skeleton's ``subject`` field is
what lets you: only one of them can be the file's ``Subject``, and ``subject`` is where the others say who
they are. Each subject brings its own interface and ``metadata_key``, its own container and skeleton
names, and its own ``subject``. Whether they also bring their own camera is the one thing that varies
with the setup: two subjects filmed by one overhead camera share a device, two filmed separately do not.

.. code-block:: python

    metadata["Subject"] = dict(subject_id="mouse_001", species="Mus musculus")
    metadata["Devices"]["arena_camera"] = dict(name="ArenaCamera")

    for subject_id in ["mouse_001", "mouse_002"]:
        entry = metadata["Pose"]["PoseEstimations"][f"pose_{subject_id}"]
        entry["name"] = f"PoseEstimation_{subject_id}"
        entry["device_metadata_key"] = "arena_camera"  # one camera filmed both; one each if it did not

        skeleton = metadata["Pose"]["Skeletons"][f"pose_{subject_id}"]
        skeleton["name"] = f"Skeleton_{subject_id}"
        skeleton["subject"] = subject_id

``mouse_001`` matches the file's ``Subject`` and its skeleton is linked to it. ``mouse_002`` does not, so
its skeleton is written unlinked rather than pointed at the wrong subject. That is what you are trading:
the second subject is identified by the names you chose and by ``subject``, not by anything NWB models.
