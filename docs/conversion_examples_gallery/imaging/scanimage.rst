ScanImage data conversion
-------------------------

Install NeuroConv with the additional dependencies necessary for reading ScanImage data.

.. code-block:: bash

    pip install "neuroconv[scanimage]"

Convert ScanImage imaging data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The `ScanImageImagingInterface` handles both single and multi-file data, as well as multi-channel data.
For multi-channel data, you need to specify the channel name, and you can use `plane_index` if you want to only write a specific plane.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import ScanImageImagingInterface
    >>>
    >>>
    >>> file_path = OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "volumetric_single_channel_single_file_no_flyback" / "vol_no_flyback_00001_00001.tif"
    >>>
    >>> # Specify channel_name for multi-channel data
    >>> # Specify plane_index for selecting a specific plane in multi-plane data or leave undefined  to write volumetric data
    >>> interface = ScanImageImagingInterface(
    ...     file_path=file_path,
    ...     channel_name="Channel 1",  # Required for multi-channel data
    ...     plane_index=None,  # Optional: specify to only write a specific plane
    ... )
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

Align ScanImage data with external sync pulses
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A common setup in two-photon imaging experiments is to have the microscope send a TTL
sync pulse to a DAQ (e.g., National Instruments) each time a frame is acquired. The DAQ
records these pulses alongside behavioral data, providing a shared clock for alignment.

The challenge is that the imaging extractor presents data as a sequence of *samples*
(one per volume in volumetric mode), but the sync pulses correspond to *raw frames*
in the TIFF file. For multi-channel volumetric data, a single sample can span dozens
of raw frames due to channel interleaving, multiple Z-planes, and flyback frames.

The ``get_original_frame_indices`` method on ``ScanImageImagingExtractor`` bridges this
gap by mapping each extractor sample back to its raw frame index in the TIFF.

.. code-block:: python

    from neuroconv.datainterfaces import ScanImageImagingInterface

    # 1. Extract sync pulse timestamps from the DAQ recording
    #    Each rising edge corresponds to one raw imaging frame
    sync_signal = daq_data["two_photon_sync"]
    threshold = 0.5
    rising_edges = (sync_signal[1:] >= threshold) & (sync_signal[:-1] < threshold)
    frame_timestamps = daq_timestamps[1:][rising_edges]

    # 2. Create the imaging interface
    interface = ScanImageImagingInterface(
        file_path="session_00001.tif",
        channel_name="Channel 1",
    )
    extractor = interface.imaging_extractor

    # 3. Map extractor samples to raw frame indices
    frame_indices = extractor.get_original_frame_indices()

    # 4. Adjust for multi-channel data if needed
    #    If the sync pulse fires once per plane (not once per channel per plane),
    #    the raw frame index includes the channel dimension and must be divided out.
    num_channels = 2  # e.g., GCaMP + jRGECO
    sync_pulse_indices = frame_indices // num_channels

    # 5. Handle cases where the DAQ stopped before the microscope
    #    The extractor may have more samples than there are sync pulses.
    valid_mask = sync_pulse_indices < len(frame_timestamps)
    if not valid_mask.all():
        last_valid = valid_mask.nonzero()[0][-1]
        interface.imaging_extractor = extractor.slice_samples(
            start_sample=0,
            end_sample=last_valid + 1,
        )
        sync_pulse_indices = sync_pulse_indices[valid_mask]

    # 6. Look up the aligned timestamps
    aligned_timestamps = frame_timestamps[sync_pulse_indices]
    interface.set_aligned_timestamps(aligned_timestamps=aligned_timestamps)

**Key considerations:**

- **Which plane to reference:** By default, ``get_original_frame_indices`` returns the
  index of the last plane in each volume. This matches setups where the volume timestamp
  is assigned at the end of the scan. Pass ``plane_index=0`` if your system timestamps
  the start of each volume instead.

- **DAQ vs. microscope shutdown order:** If the DAQ is turned off before the microscope
  stops acquiring, some imaging samples will have no corresponding sync pulses. Always
  check for this and slice the extractor accordingly, as shown in step 5 above. This
  check assumes invalid samples are contiguous at the tail, which is the typical case
  when the DAQ shuts down before the microscope.

- **Channel adjustment:** ScanImage writes frames in CZT order (Channel, Z-depth, Time).
  The sync system typically fires once per plane regardless of how many channels are being
  recorded. Dividing the frame index by the number of channels converts from raw-frame-space
  to sync-pulse-space.

.. note::
    For older ScanImage files (v3.8 and earlier), use the :doc:`ScanImageLegacyImagingInterface <scanimage_legacy>` interface instead.
