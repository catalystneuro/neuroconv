Facemap data conversion
-----------------------

Install NeuroConv with the additional dependencies necessary for reading Facemap data.

.. code-block:: bash

    pip install "neuroconv[facemap]"

Convert the output of the `Facemap <https://github.com/MouseLand/facemap>`_ MATLAB GUI to NWB using
:py:class:`~neuroconv.datainterfaces.behavior.facemap.facemapdatainterface.FacemapInterface`.
The interface reads the ``_proc.mat`` file the GUI saves, in either container MATLAB writes it in, together with
the video it was computed from, whose frame times become the times of every series.

The pupil area and its unsmoothed version are written as :py:class:`~pynwb.base.TimeSeries` in a
:py:class:`~pynwb.behavior.PupilTracking`, and the pupil center of mass as a :py:class:`~pynwb.behavior.SpatialSeries`
in an :py:class:`~pynwb.behavior.EyeTracking`. The motion SVD of the whole frame and of each small ROI is written with
the `ndx-facemap-motionsvd <https://github.com/catalystneuro/ndx-facemap-motionsvd>`_ extension, as a
``MotionSVDSeries`` for the temporal components and a ``MotionSVDMasks`` table for the spatial masks. Outputs the
operator did not draw an ROI for are skipped.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from neuroconv.datainterfaces import FacemapInterface

    >>> folder_path = BEHAVIOR_DATA_PATH / "facemap" / "motion_svd" / "matlab_gui" / "whole_frame_and_one_roi" / "single_video_hdf5"
    >>> file_path = folder_path / "11222019_grabAM05_spont_proc.mat"
    >>> video_file_path = folder_path / "11222019_grabAM05_spont.avi"
    >>> interface = FacemapInterface(file_path=file_path, video_file_path=video_file_path, verbose=False)

    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # session_start_time is required for conversion. Facemap records no acquisition date, so you must supply one.
    >>> session_start_time = datetime(2019, 11, 22, 12, 0, 0, tzinfo=ZoneInfo("US/Eastern"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>> # Keep only the first motion SVD components of each region to save space
    >>> interface.run_conversion(
    ...     nwbfile_path=path_to_save_nwbfile, metadata=metadata, overwrite=True, first_n_components=50
    ... )


Linking to the video
~~~~~~~~~~~~~~~~~~~~

To add the video and link the motion masks to it, convert the video with its own interface and name its metadata
key in the ``source_video_metadata_key`` of each ``MotionSVDMasks`` entry. The video interface has to run first, so
that its ``ImageSeries`` is in the NWB file when the masks are written.

.. code-block:: python

    >>> from neuroconv import ConverterPipe
    >>> from neuroconv.datainterfaces import ExternalVideoInterface

    >>> video_interface = ExternalVideoInterface(file_paths=[video_file_path], metadata_key="face_camera")
    >>> converter = ConverterPipe(data_interfaces=dict(video=video_interface, facemap=interface))

    >>> metadata = converter.get_metadata()
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>> for masks_entry in metadata["Behavior"]["Facemap"]["MotionSVDMasks"].values():
    ...     masks_entry["source_video_metadata_key"] = "face_camera"
    >>> converter.run_conversion(
    ...     nwbfile_path=path_to_save_nwbfile,
    ...     metadata=metadata,
    ...     overwrite=True,
    ...     conversion_options=dict(facemap=dict(first_n_components=50)),
    ... )
