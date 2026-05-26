Intan Data Conversion
---------------------

This guide covers the conversion of Intan data, including both amplifier data (primary neural recordings) and analog data (auxiliary inputs, ADC inputs, DC amplifiers) from RHD2000 and RHS2000 systems.

Install NeuroConv with the additional dependencies necessary for reading Intan data.

.. code-block:: bash

    pip install "neuroconv[intan]"

File formats and save modes
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Intan RHX software can save a recording in one of three on-disk formats:

.. list-table::
    :header-rows: 1
    :widths: 30 70

    * - Save mode
      - What to pass as ``file_path``
    * - Traditional Intan File Format
      - The single ``.rhd`` or ``.rhs`` file
    * - One File Per Signal Type
      - The ``info.rhd`` or ``info.rhs`` header file in the session directory
    * - One File Per Channel
      - The ``info.rhd`` or ``info.rhs`` header file in the session directory

The interface API is identical across all three modes; the layout is inferred automatically from the header.

Traditional format also offers an option to "create a new save file every N minutes,"
which splits one session across several rotated ``.rhd``/``.rhs`` files in the same
folder. For that case, see :ref:`intan-split-files` below.

Intan Amplifier Data Conversion
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Convert Intan amplifier data to NWB using :py:class:`~neuroconv.datainterfaces.ecephys.intan.intandatainterface.IntanRecordingInterface`.
This interface handles the primary neural recordings from the RHD2000 or RHS2000 amplifier channels.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import IntanRecordingInterface
    >>>
    >>> file_path = f"{ECEPHY_DATA_PATH}/intan/intan_rhd_test_1.rhd" # This can also be .rhs
    >>> interface = IntanRecordingInterface(file_path=file_path, verbose=False)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # session_start_time is required for conversion. If it cannot be inferred
    >>> # automatically from the source files you must supply one.
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "./saved_file.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

Intan Analog Data Conversion
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Convert non-amplifier analog data from Intan systems to NWB using :py:class:`~neuroconv.datainterfaces.ecephys.intan.intananaloginterface.IntanAnalogInterface`.
This includes signals from auxiliary inputs, ADC inputs, and DC amplifiers.

This interface supports analog streams including:

* **USB board ADC input channel**: ADC input channels
* **RHD2000 auxiliary input channel**: Auxiliary input channels (e.g., accelerometer data)
* **DC Amplifier channel**: DC amplifier channels (RHS system only)
* **USB board ADC output channel**: ADC output channels

USB board ADC input channels
""""""""""""""""""""""""""""

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import IntanAnalogInterface
    >>>
    >>> # For this interface we need to pass the location of the .rhd or .rhs file
    >>> file_path = f"{ECEPHY_DATA_PATH}/intan/intan_rhd_test_1.rhd"
    >>>
    >>> # Convert ADC input channels
    >>> interface = IntanAnalogInterface(
    ...     file_path=file_path,
    ...     stream_name="USB board ADC input channel",
    ...     verbose=False
    ... )
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # session_start_time is required but not available on intan
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

RHD2000 auxiliary input
"""""""""""""""""""""""

You can also convert auxiliary input channels (e.g., accelerometer data):

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import IntanAnalogInterface
    >>>
    >>> # For this interface we need to pass the location of the .rhd or .rhs file
    >>> file_path_aux = f"{ECEPHY_DATA_PATH}/intan/intan_fpc_test_231117_052630/info.rhd"
    >>>
    >>> # Convert auxiliary input channels (e.g., accelerometer data)
    >>> interface_aux = IntanAnalogInterface(
    ...     file_path=file_path_aux,
    ...     stream_name="RHD2000 auxiliary input channel",
    ...     verbose=False
    ... )
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata_aux = interface_aux.get_metadata()
    >>> # session_start_time is required but not available on intan
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata_aux["NWBFile"].update(session_start_time=session_start_time)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata_aux["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path_aux = output_folder / "intan_auxiliary_conversion.nwb"
    >>> interface_aux.run_conversion(nwbfile_path=nwbfile_path_aux, metadata=metadata_aux, overwrite=True)

DC Amplifier channels (RHS systems)
"""""""""""""""""""""""""""""""""""

For RHS systems, you can also convert DC amplifier channels:

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import IntanAnalogInterface
    >>>
    >>> # For this interface we need to pass the location of the .rhs file
    >>> file_path_dc = f"{ECEPHY_DATA_PATH}/intan/test_fcs_dc_250327_154333/info.rhs"
    >>>
    >>> # Convert DC amplifier channels (RHS system)
    >>> interface_dc = IntanAnalogInterface(
    ...     file_path=file_path_dc,
    ...     stream_name="DC Amplifier channel",
    ...     verbose=False
    ... )
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata_dc = interface_dc.get_metadata()
    >>> # session_start_time is required but not available on intan
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata_dc["NWBFile"].update(session_start_time=session_start_time)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata_dc["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path_dc = output_folder / "intan_dc_amplifier_conversion.nwb"
    >>> interface_dc.run_conversion(nwbfile_path=nwbfile_path_dc, metadata=metadata_dc, overwrite=True)

USB board ADC output channels (RHS systems)
"""""""""""""""""""""""""""""""""""""""""""

For RHS systems, you can also convert ADC output channels:

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import IntanAnalogInterface
    >>>
    >>> # For this interface we need to pass the location of the .rhs file
    >>> file_path_output = f"{ECEPHY_DATA_PATH}/intan/rhs_stim_data_single_file_format/intanTestFile.rhs"
    >>>
    >>> # Convert ADC output channels (RHS system)
    >>> interface_output = IntanAnalogInterface(
    ...     file_path=file_path_output,
    ...     stream_name="USB board ADC output channel",
    ...     verbose=False
    ... )
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata_output = interface_output.get_metadata()
    >>> # session_start_time is required for conversion. If it cannot be inferred
    >>> # automatically from the source files you must supply one.
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata_output["NWBFile"].update(session_start_time=session_start_time)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata_output["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path_output = output_folder / "intan_adc_output_conversion.nwb"
    >>> interface_output.run_conversion(nwbfile_path=nwbfile_path_output, metadata=metadata_output, overwrite=True)

Intan Stimulation Data Conversion (RHS systems)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Convert electrical stimulation current data from RHS2000 systems to NWB using
:py:class:`~neuroconv.datainterfaces.ecephys.intan.intanstiminterface.IntanStimInterface`.

The RHS Stim/Recording System records stimulation current alongside neural data. Each
amplifier channel has a corresponding stimulation channel named ``{channel}_STIM``
(e.g., ``A-000_STIM``). Data are stored as a ``TimeSeries`` with ``unit="A"`` (Amperes),
with the conversion factor derived automatically from the ``stim_step_size`` in the file header.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import IntanStimInterface
    >>>
    >>> # For this interface we need to pass the location of the .rhs file
    >>> file_path_stim = f"{ECEPHY_DATA_PATH}/intan/rhs_stim_data_single_file_format/intanTestFile.rhs"
    >>>
    >>> # Convert stimulation channels (RHS system only)
    >>> interface_stim = IntanStimInterface(file_path=file_path_stim, verbose=False)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata_stim = interface_stim.get_metadata()
    >>> # session_start_time is required but not available on intan
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata_stim["NWBFile"].update(session_start_time=session_start_time)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata_stim["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path_stim = output_folder / "intan_stim_conversion.nwb"
    >>> interface_stim.run_conversion(nwbfile_path=nwbfile_path_stim, metadata=metadata_stim, overwrite=True)

.. _intan-split-files:

Converting a session saved as multiple files
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When a Traditional-format recording is saved with the "create a new save file
every N minutes" option, Intan RHX writes one file per N-minute chunk into a
single session folder, each named with a ``{prefix}_YYMMDD_HHMMSS`` timestamp.
Set ``saved_files_are_split=True`` on any Intan interface to concatenate all
sibling ``.rhd``/``.rhs`` files in the folder in filename order (fixed-width
timestamps make lexicographic order match chronological order):

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import IntanRecordingInterface
    >>>
    >>> # Any single file in the session folder; its parent directory is scanned
    >>> file_path_split = f"{ECEPHY_DATA_PATH}/intan/test_tetrode_240502_162925/test_tetrode_240502_162925.rhd"
    >>>
    >>> interface_split = IntanRecordingInterface(
    ...     file_path=file_path_split,
    ...     saved_files_are_split=True,
    ...     verbose=False,
    ... )
    >>>
    >>> metadata_split = interface_split.get_metadata()
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata_split["NWBFile"].update(session_start_time=session_start_time)
    >>> metadata_split["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> nwbfile_path_split = output_folder / "intan_split_conversion.nwb"
    >>> interface_split.run_conversion(nwbfile_path=nwbfile_path_split, metadata=metadata_split, overwrite=True)

The same ``saved_files_are_split=True`` flag is accepted by
:py:class:`~neuroconv.datainterfaces.ecephys.intan.intananaloginterface.IntanAnalogInterface`
and
:py:class:`~neuroconv.datainterfaces.ecephys.intan.intanstiminterface.IntanStimInterface`,
since all streams rotate together in Intan's Traditional format.

If ``saved_files_are_split=False`` (the default) and the interface detects
sibling ``.rhd``/``.rhs`` files next to the one you passed, it will emit a
warning suggesting the flag; you can safely ignore it when the neighbors are
from an unrelated session.
