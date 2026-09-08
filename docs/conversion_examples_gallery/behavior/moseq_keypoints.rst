keypoint-MoSeq data conversion
------------------------------

Install NeuroConv with the additional dependencies necessary for reading keypoint-MoSeq data.

.. code-block:: bash

    pip install "neuroconv[moseq]"

Convert `keypoint-MoSeq <https://github.com/dattalab/keypoint-moseq>`_ output to NWB using
:py:class:`~neuroconv.datainterfaces.behavior.moseq.moseqkeypointsinterface.MoseqKeyPointsInterface`.
keypoint-MoSeq labels every frame of a recording with a syllable, a short recurring unit of movement,
and writes the result to a ``results.h5`` holding one group per recording, each with a ``syllable``,
a ``latent_state``, a ``centroid`` and a ``heading`` array.

The syllable sequence is written as a curated
`ndx-ethogram <https://github.com/catalystneuro/ndx-ethogram>`_ product: an ``EthogramBouts`` table,
the per-frame syllables run-length-encoded into one row per bout, plus its ``Ethogram`` catalogue with
one row per syllable id. The three continuous arrays are written as core NWB objects: the centroid as
a ``SpatialSeries`` in ``Position``, the heading as a ``SpatialSeries`` in ``CompassDirection``, and
the latent trajectory as a ``TimeSeries``.

Recordings in one file have their own frame counts, and an NWB file holds one session, so one
interface writes one recording. Use
:py:meth:`~neuroconv.datainterfaces.behavior.moseq.moseqkeypointsinterface.MoseqKeyPointsInterface.get_available_recordings`
to list the recordings a file holds. Their names come from the input filenames, so a run on DeepLabCut
output carries the scorer suffix DeepLabCut appended to its own file and a run on a plain coordinates
file gives the bare recording name.

keypoint-MoSeq records no time base. Neither ``results.h5`` nor its CSV sibling carries timestamps or
a frame rate, because the rate is a property of the video the keypoints came from, so
``sampling_frequency_hz`` is required.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from neuroconv.datainterfaces import MoseqKeyPointsInterface

    >>> file_path = BEHAVIOR_DATA_PATH / "moseq" / "keypoint_moseq" / "two_dimensional" / "results.h5"

    >>> recordings = MoseqKeyPointsInterface.get_available_recordings(file_path)
    >>> recording_name = recordings[0]

    >>> # keypoint-MoSeq records no frame rate. Take it from the video the keypoints were tracked
    >>> # from, or from the `fps` field of the keypoint-MoSeq project's config.yml.
    >>> interface = MoseqKeyPointsInterface(
    ...     file_path=file_path,
    ...     recording_name=recording_name,
    ...     sampling_frequency_hz=30.0,
    ... )

    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # session_start_time is required for conversion. keypoint-MoSeq records no acquisition date,
    >>> # so you must supply one.
    >>> session_start_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata)


Specifying Metadata
~~~~~~~~~~~~~~~~~~~

The three continuous series live in flat registries under ``metadata["Behavior"]["MoseqKeyPoints"]``,
one per type (``Centroids``, ``Headings``, ``LatentStates``), and the curated ethogram products live in
the shared, producer-agnostic ``metadata["Behavior"]["Ethograms"]`` registry. Every entry is keyed by
``metadata_key``, which defaults to ``"keypoint_moseq"``. Pass a different one to write two recordings
into the same NWB file without their entries colliding.

The centroid is the one place worth editing. Its width follows the input pose, ``(T, 2)`` for 2D
keypoints and ``(T, 3)`` for 3D, and the two are in different coordinate spaces: a 2D run from
DeepLabCut is in image pixels, while a 3D run is in whatever space the triangulation used.
``results.h5`` records neither the unit nor the frame, so both are written as placeholders unless the
metadata supplies them.

.. code-block:: python

    >>> from neuroconv.utils import dict_deep_update

    >>> custom_metadata = {
    ...     "NWBFile": {
    ...         "session_start_time": datetime(2024, 1, 1, 12, 0, 0, tzinfo=ZoneInfo("US/Pacific")),
    ...     },
    ...     "Subject": dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D"),
    ...     "Behavior": {
    ...         "MoseqKeyPoints": {
    ...             "Centroids": {
    ...                 "keypoint_moseq": {
    ...                     "unit": "pixels",
    ...                     "reference_frame": "(0,0) is the top-left pixel of the behavioral video.",
    ...                 },
    ...             },
    ...         },
    ...     },
    ... }
    >>> metadata = dict_deep_update(interface.get_metadata(), custom_metadata)
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata, overwrite=True)


Linking to pose estimation
~~~~~~~~~~~~~~~~~~~~~~~~~~

A recording name carries no mapping to a session or a subject, so nothing is derived from it. To
record the upstream pose keypoints the syllables were fitted on, add a ``Recordings`` entry naming the
``PoseEstimation`` registry key. The container it names must already be in the NWB file when
``add_to_nwbfile`` is called, so the pose interface has to run first.

.. code-block:: python

    >>> from neuroconv import ConverterPipe
    >>> from neuroconv.datainterfaces import DeepLabCutInterface

    >>> pose_interface = DeepLabCutInterface(file_path="/path/to/dlc_output.h5")  # doctest: +SKIP
    >>> converter = ConverterPipe(  # doctest: +SKIP
    ...     data_interfaces=dict(DLC=pose_interface, Moseq=interface)
    ... )
    >>> metadata = converter.get_metadata()  # doctest: +SKIP
    >>> metadata["Behavior"]["MoseqKeyPoints"]["Recordings"] = {  # doctest: +SKIP
    ...     "keypoint_moseq": {"pose_estimation_metadata_key": "PoseEstimationDeepLabCut"},
    ... }
    >>> converter.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata)  # doctest: +SKIP


Two recordings in one file
~~~~~~~~~~~~~~~~~~~~~~~~~~

Recordings in one ``results.h5`` are usually separate sessions and belong in separate NWB files. Where
two do belong together, give each interface its own ``metadata_key``:

.. code-block:: python

    >>> first_interface = MoseqKeyPointsInterface(
    ...     file_path=file_path,
    ...     recording_name=recordings[0],
    ...     sampling_frequency_hz=30.0,
    ...     metadata_key="first_recording",
    ... )
    >>> second_interface = MoseqKeyPointsInterface(
    ...     file_path=file_path,
    ...     recording_name=recordings[1],
    ...     sampling_frequency_hz=30.0,
    ...     metadata_key="second_recording",
    ... )
    >>> converter = ConverterPipe(
    ...     data_interfaces=dict(MoseqFirst=first_interface, MoseqSecond=second_interface)
    ... )

The default object names collide when two instances share a file, so rename them alongside the keys:

.. code-block:: python

    >>> custom_metadata = {
    ...     "NWBFile": {
    ...         "session_start_time": datetime(2024, 1, 1, 12, 0, 0, tzinfo=ZoneInfo("US/Pacific")),
    ...     },
    ...     "Subject": dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D"),
    ...     "Behavior": {
    ...         "MoseqKeyPoints": {
    ...             "Centroids": {
    ...                 "first_recording": {"name": "CentroidFirst", "container_name": "PositionFirst"},
    ...                 "second_recording": {"name": "CentroidSecond", "container_name": "PositionSecond"},
    ...             },
    ...             "Headings": {
    ...                 "first_recording": {"name": "HeadingFirst", "container_name": "CompassDirectionFirst"},
    ...                 "second_recording": {"name": "HeadingSecond", "container_name": "CompassDirectionSecond"},
    ...             },
    ...             "LatentStates": {
    ...                 "first_recording": {"name": "LatentStateFirst"},
    ...                 "second_recording": {"name": "LatentStateSecond"},
    ...             },
    ...         },
    ...         "Ethograms": {
    ...             "first_recording": {
    ...                 "EthogramBouts": {"name": "EthogramBoutsFirst"},
    ...                 "Ethogram": {"name": "EthogramFirst"},
    ...             },
    ...             "second_recording": {
    ...                 "EthogramBouts": {"name": "EthogramBoutsSecond"},
    ...                 "Ethogram": {"name": "EthogramSecond"},
    ...             },
    ...         },
    ...     },
    ... }
    >>> metadata = dict_deep_update(converter.get_metadata(), custom_metadata)
    >>> converter.run_conversion(
    ...     nwbfile_path=path_to_save_nwbfile,
    ...     metadata=metadata,
    ...     overwrite=True,
    ... )
