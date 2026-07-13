CSV Fiber Photometry data conversion
------------------------------------

Install NeuroConv with the additional dependencies necessary for reading CSV Fiber Photometry data.

.. code-block:: bash

    pip install "neuroconv[csv_fp]"

This CSV format is a raw acquisition format for fiber photometry recordings, with one CSV per stream
(e.g. a signal channel and an isosbestic control channel). Each data CSV has ``timestamps`` and
``data`` columns and is named after its stream (``<stream_name>.csv``).

Each interface writes a single ``FiberPhotometryResponseSeries``, assembled from one or more input
streams; combine multiple interfaces (with distinct ``metadata_key`` values) in a converter to write
several series sharing one ``FiberPhotometryTable``.

Convert CSV Fiber Photometry data to NWB
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert CSV Fiber Photometry data to NWB using
:py:class:`~neuroconv.datainterfaces.fiber_photometry.csv.csvfiberphotometrydatainterface.CSVFiberPhotometryInterface`.

CSV recordings carry no embedded recording-start timestamp, so ``session_start_time`` must be
supplied explicitly in the metadata.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo

    >>> import numpy as np
    >>> import pandas as pd

    >>> from neuroconv.datainterfaces import CSVFiberPhotometryInterface

    >>> # This format is just per-stream CSVs; here we write a small example signal and control channel
    >>> # with ``timestamps`` and ``data`` columns.
    >>> folder_path = output_folder
    >>> sampling_rate = 100.0
    >>> num_samples = 150
    >>> timestamps = np.arange(num_samples) / sampling_rate
    >>> signal = pd.DataFrame({"timestamps": timestamps, "data": np.linspace(0.1, 1.0, num_samples)})
    >>> signal.to_csv(folder_path / "Sample_Signal_Channel.csv", index=False)
    >>> control = pd.DataFrame({"timestamps": timestamps, "data": np.linspace(0.5, 1.4, num_samples)})
    >>> control.to_csv(folder_path / "Sample_Control_Channel.csv", index=False)

    >>> # Discover the data streams available in the folder (callable before construction)
    >>> available_streams = CSVFiberPhotometryInterface.get_available_streams(folder_path=folder_path)

    >>> interface = CSVFiberPhotometryInterface(folder_path=folder_path, stream_names="Sample_Signal_Channel", metadata_key="calcium_signal", verbose=False)
    >>> metadata = interface.get_metadata()
    >>> # CSV recordings have no embedded start time, so it must be set explicitly.
    >>> metadata["NWBFile"]["session_start_time"] = datetime.now(tz=ZoneInfo("US/Pacific"))
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>> # get_metadata() returns an editable scaffold; the required fiber photometry fields (excitation/
    >>> # emission wavelengths, indicator, location, ...) are pre-filled with placeholder values that
    >>> # should be replaced before archiving. add_to_nwbfile warns about any that remain unset.

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path =  f"{path_to_save_nwbfile}"
    >>> # stub_test writes only the first stub_samples samples, which is useful for quick tests
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, stub_test=True, overwrite=True)

The full metadata format (device models, devices, indicators, the ``FiberPhotometryTable``, and the
per-interface response series) is shared across the fiber photometry interfaces and documented at
:ref:`fiber_photometry_metadata_structure`.
