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
download. Everything after the constructor is the same for any pose interface: swap in
:py:class:`~neuroconv.datainterfaces.behavior.deeplabcut.deeplabcutdatainterface.DeepLabCutInterface`,
:py:class:`~neuroconv.datainterfaces.behavior.lightningpose.lightningposedatainterface.LightningPoseDataInterface`
or :py:class:`~neuroconv.datainterfaces.behavior.sleap.sleapdatainterface.SLEAPInterface` with the
arguments its format needs, and annotate the metadata exactly as shown. See the
:ref:`Conversion Gallery <conversion_gallery>` for how to construct each one.

A **keypoint** is one tracked body part and becomes one ``PoseEstimationSeries``. A **container** is one
camera view of one subject: it holds those series, a ``Skeleton`` naming the keypoints and the edges
between them, and optionally the camera that recorded them. Annotating a recording is filling in what the
tracker could not know.

.. note::

    Every entry below is addressed by a *registry key*, such as ``"lightning_pose"``. That key is an
    internal handle and never appears in the NWB file. What appears is the entry's ``name`` field.
    Renaming an object means editing ``name``, not the key.

How to Annotate a Single Camera and a Single Animal
---------------------------------------------------

The baseline setup: one camera above the arena, one animal, one tracker run. Everything the other setups
do is a variation on this one, so it is worked in full.

**Name the objects.** The container, the skeleton and each series are named through the registries under
the top-level ``metadata["Pose"]``.

.. code-block:: python

    metadata = interface.get_metadata()
    key = interface.metadata_key

    container = metadata["Pose"]["PoseEstimations"][key]
    container["name"] = "PoseEstimationTopCamera"
    metadata["Pose"]["Skeletons"][key]["name"] = "SkeletonMouse"

**Describe what the coordinates mean.** Nothing in a pose file says where the origin is, what the units
are, or what the confidence value represents. neuroconv writes none of these unless you do, because any
value it chose would be invented rather than read. The one exception is ``reference_frame``, which
``ndx-pose`` requires, so the writer supplies "(0,0) is unknown." when you leave it out. That is a
statement of ignorance sitting in your file, and replacing it is the most valuable line on this page.

.. code-block:: python

    for series in container["PoseEstimationSeries"].values():
        series["unit"] = "pixels"
        series["reference_frame"] = "(0,0) is the top left corner of the video."
        series["confidence_definition"] = "Softmax output of the deep neural network."

    container["description"] = "2D keypoints of a mouse in an open field, from the overhead camera."

**Describe the skeleton.** Edges are pairs of node indices. The ``subject`` field names the individual
within the source, and the skeleton is linked to the file's ``Subject`` when the two ids match. A file
without a ``Subject``, or one whose id differs, gets a skeleton linked to nothing.

.. code-block:: python

    skeleton = metadata["Pose"]["Skeletons"][key]
    skeleton["edges"] = [[0, 1], [1, 2]]  # head-neck, neck-left shoulder
    skeleton["subject"] = "mouse_001"

    metadata["Subject"] = dict(subject_id="mouse_001", species="Mus musculus", sex="M", age="P30D")

**Record where the frames came from.** Two things can carry that, and which you want depends on whether
the video itself is in the file.

If a video interface wrote the recording into the file as an ``ImageSeries``, link that object. The
``ImageSeries`` already carries its own camera ``Device``, so this one link records both the recording and
the instrument, and the camera is reachable from the container through it. Adding a camera to the
container as well is a second link to the same object.

.. code-block:: python

    container["source_video_metadata_key"] = "original_video"  # -> metadata["Behavior"]["ExternalVideos"]

If the video is not in the file, because it stays on disk or you have only the tracker output, then give
its path and add the camera to the container, since nothing else in the file records that one existed.
This is the usual DeepLabCut case. Prefer a path relative to the NWB file over an absolute one: the schema
notes that these strings are fragile, and an absolute path from the machine that ran the tracker almost
never resolves on the machine that reads the file.

.. code-block:: python

    container["original_videos"] = ["videos/top_camera.mp4"]  # relative to the NWB file

    metadata["Devices"]["top_camera"] = dict(name="TopCamera", description="Overhead camera, 30 fps.")
    container["device_metadata_key"] = "top_camera"

.. note::

    Calibrated multi-camera setups are the exception. There the camera is not just provenance, it is what
    makes a 3D reconstruction possible, so the intrinsics and extrinsics belong on the container's own
    device rather than on the recording.

.. admonition:: The file so far
   :class: tip

   .. code-block:: text

       processing/behavior
       ├── PoseEstimationTopCamera            PoseEstimation   description, unit, reference frame
       │   ├── PoseEstimationSeriesHead       data (1000, 2)
       │   ├── PoseEstimationSeriesNeck       data (1000, 2)
       │   └── PoseEstimationSeriesLeftShou…  data (1000, 2)
       └── Skeletons
           └── SkeletonMouse                  nodes, edges, subject -> mouse_001

       devices
       └── TopCamera

How to Annotate Several Camera Views of One Animal
---------------------------------------------------

Two cameras filming the same mouse, each tracked separately. One animal means one file, and each view is
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

How to Annotate Several Animals in One Recording
-------------------------------------------------

Two mice in the same arena, tracked as two identities by SLEAP or as two individuals by DeepLabCut. An
NWB file has a single root-level ``Subject`` and ``ndx-pose`` is built on that, so in most cases you
want **one file per animal**: each interface reads one individual, each file gets its own ``Subject``,
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

If you would rather keep both animals in one file, because the video, the trials and often the
electrophysiology are shared and separate files duplicate all of it, the skeleton's ``subject`` field is
what lets you: only one animal can be the file's ``Subject``, and ``subject`` is where the others say who
they are. Each animal brings its own interface and ``metadata_key``, its own container and skeleton
names, and its own ``subject``. Whether they also bring their own camera is the one thing that varies
with the setup: two animals filmed by one overhead camera share a device, two filmed separately do not.

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
its skeleton is written unlinked rather than pointed at the wrong animal. That is what you are trading:
the second animal is identified by the names you chose and by ``subject``, not by anything NWB models.
