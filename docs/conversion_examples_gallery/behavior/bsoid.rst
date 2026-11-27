B-SOiD data conversion
----------------------

Install NeuroConv with the additional dependencies necessary for reading B-SOiD data.

.. code-block:: bash

    pip install "neuroconv[bsoid]"

Convert `B-SOiD <https://github.com/YttriLab/B-SOID>`_ output to NWB using
:py:class:`~neuroconv.datainterfaces.behavior.bsoid.bsoidinterface.BSOiDInterface`.
B-SOiD (Behavioral Segmentation of Open-field In DeepLabCut) clusters pose features into behavior groups and
assigns one group to every frame of a pose file. The interface reads the labels file B-SOiD writes for each
predicted pose file: ``labels_pose`` from the app, which it writes into a ``BSOID`` folder next to the pose file,
or ``bsoid_labels`` from the ``bsoid_umap`` command-line pipeline.

The ``.mat`` output of B-SOiD's MATLAB code (versions 1.0 to 1.2) is not supported, and the interface raises an
error when given one. That code does not save its labels itself. A ``.mat`` holds whatever variables the user
decided to save, under names they chose, and nothing in it says which recording or frame rate the labels belong to.

The groups are written as an `ndx-ethogram <https://github.com/catalystneuro/ndx-ethogram>`_ ``EthogramBouts``
table, the per-frame labels run-length-encoded into one row per bout, plus its ``Ethogram`` catalogue with one row
per group. The times are the pose frame index the file carries divided by the frame rate, which B-SOiD writes into
the file name. Pass ``sampling_frequency_hz`` when the file was renamed.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from neuroconv.datainterfaces import BSOiDInterface

    >>> folder_path = BEHAVIOR_DATA_PATH / "bsoid" / "app" / "version_1_5" / "pose_input_format" / "deeplabcut_csv"
    >>> pose_file_stem = "2019-04-22_12-00-37cut0_30minDeepCut_resnet50_OpenFieldHighResApr8shuffle1_1030000"
    >>> file_path = folder_path / "BSOID" / f"Jan-01-2024labels_pose_60Hz{pose_file_stem}.csv"
    >>> interface = BSOiDInterface(file_path=file_path)

    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # session_start_time is required for conversion. B-SOiD records no acquisition date, so you must supply one.
    >>> session_start_time = datetime(2019, 4, 22, 12, 0, 37, tzinfo=ZoneInfo("US/Eastern"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata)


Linking to pose estimation
~~~~~~~~~~~~~~~~~~~~~~~~~~

The labels file holds a copy of the pose, which the interface does not write. To add the pose and link the bouts
to it, convert the pose file with its own interface and name the metadata key of its ``PoseEstimation`` in the
``source_pose_metadata_key`` of the bouts entry. The pose interface has to run first, so that the container is in
the NWB file when ``add_to_nwbfile`` is called.

.. code-block:: python

    >>> from neuroconv import ConverterPipe
    >>> from neuroconv.datainterfaces import DeepLabCutInterface

    >>> pose_interface = DeepLabCutInterface(file_path="/path/to/dlc_output.csv", sampling_frequency=60.0)  # doctest: +SKIP
    >>> converter = ConverterPipe(data_interfaces=dict(DLC=pose_interface, BSOiD=interface))  # doctest: +SKIP
    >>> metadata = converter.get_metadata()  # doctest: +SKIP
    >>> metadata["Behavior"]["EthogramBouts"]["bsoid"]["source_pose_metadata_key"] = "deep_lab_cut_metadata_key"  # doctest: +SKIP
    >>> converter.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata)  # doctest: +SKIP
