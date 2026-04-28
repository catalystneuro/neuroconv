Doric Fiber Photometry data conversion
---------------------------------------

Install NeuroConv with the additional dependencies necessary for reading Doric Fiber Photometry data.

.. code-block:: bash

    pip install "neuroconv[doric_fp]"

Discover available signal streams
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The interface auto-discovers streams from the ``.doric`` HDF5 file by walking ``DataAcquisition``
for groups that contain a ``Time`` sibling dataset.  Each non-``Time`` 1-D dataset becomes a stream
whose name is built from its HDF5 path (relative to ``DataAcquisition``) with ``/`` replaced by ``_``.

.. code-block:: python

    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import DoricFiberPhotometryInterface

    >>> file_path = Path("path/to/your_recording.doric")
    >>> interface = DoricFiberPhotometryInterface(file_path=file_path, verbose=False)
    >>> stream_names = interface.get_stream_names()
    >>> print(stream_names)  # e.g. ['BBC300_ROISignals_Series0001_CAM1EXC1_ROI01', ...]

Specify the metadata required for the conversion
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

All hardware metadata must be supplied by the user. The ``stream_name`` field in each
``FiberPhotometryResponseSeries`` entry must match one of the names returned by
:py:meth:`~neuroconv.datainterfaces.DoricFiberPhotometryInterface.get_stream_names`.

.. code-block:: python

    >>> fiber_photometry_metadata = {
    ...     "Ophys": {
    ...         "FiberPhotometry": {
    ...             "OpticalFiberModels": [
    ...                 {
    ...                     "name": "optical_fiber_model",
    ...                     "manufacturer": "Doric Lenses",
    ...                     "numerical_aperture": 0.48,
    ...                     "core_diameter_in_um": 400.0,
    ...                 }
    ...             ],
    ...             "OpticalFibers": [
    ...                 {
    ...                     "name": "optical_fiber",
    ...                     "model": "optical_fiber_model",
    ...                     "fiber_insertion": {"depth_in_mm": 2.8},
    ...                 }
    ...             ],
    ...             "ExcitationSourceModels": [
    ...                 {
    ...                     "name": "excitation_source_model",
    ...                     "manufacturer": "Doric Lenses",
    ...                     "source_type": "LED",
    ...                     "excitation_mode": "one-photon",
    ...                 }
    ...             ],
    ...             "ExcitationSources": [
    ...                 {
    ...                     "name": "excitation_source_465nm",
    ...                     "model": "excitation_source_model",
    ...                 }
    ...             ],
    ...             "PhotodetectorModels": [
    ...                 {
    ...                     "name": "photodetector_model",
    ...                     "manufacturer": "Doric Lenses",
    ...                     "detector_type": "photodiode",
    ...                 }
    ...             ],
    ...             "Photodetectors": [
    ...                 {
    ...                     "name": "photodetector",
    ...                     "model": "photodetector_model",
    ...                 }
    ...             ],
    ...             "FiberPhotometryIndicators": [
    ...                 {
    ...                     "name": "green_fluorophore",
    ...                     "description": "GCaMP7b calcium indicator.",
    ...                     "label": "GCaMP7b",
    ...                 }
    ...             ],
    ...             "FiberPhotometryTable": {
    ...                 "name": "fiber_photometry_table",
    ...                 "description": "Fiber photometry system metadata.",
    ...                 "rows": [
    ...                     {
    ...                         "location": "DMS",
    ...                         "excitation_wavelength_in_nm": 465.0,
    ...                         "emission_wavelength_in_nm": 525.0,
    ...                         "indicator": "green_fluorophore",
    ...                         "optical_fiber": "optical_fiber",
    ...                         "excitation_source": "excitation_source_465nm",
    ...                         "photodetector": "photodetector",
    ...                     }
    ...                 ],
    ...             },
    ...             "FiberPhotometryResponseSeries": [
    ...                 {
    ...                     "name": "calcium_signal_dms",
    ...                     "description": "GCaMP7b fluorescence from DMS.",
    ...                     "stream_name": "BBC300_ROISignals_Series0001_CAM1EXC1_ROI01",
    ...                     "unit": "a.u.",
    ...                     "fiber_photometry_table_region": [0],
    ...                     "fiber_photometry_table_region_description": "DMS fiber photometry row.",
    ...                 }
    ...             ],
    ...         }
    ...     }
    ... }


Convert Doric Fiber Photometry data to NWB
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert Doric Fiber Photometry data to NWB using
:py:class:`~neuroconv.datainterfaces.ophys.doric.doricfiberphotometrydatainterface.DoricFiberPhotometryInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from pathlib import Path
    >>> from zoneinfo import ZoneInfo

    >>> from neuroconv.datainterfaces import DoricFiberPhotometryInterface
    >>> from neuroconv.utils import dict_deep_update

    >>> file_path = Path("path/to/your_recording.doric")

    >>> interface = DoricFiberPhotometryInterface(file_path=file_path, verbose=False)

    >>> metadata = interface.get_metadata()
    >>> metadata["NWBFile"].update(
    ...     session_description="A fiber photometry session.",
    ...     session_start_time=datetime(2024, 1, 1, tzinfo=ZoneInfo("US/Eastern")),
    ... )

    >>> metadata = dict_deep_update(metadata, fiber_photometry_metadata)

    >>> nwbfile_path = Path("doric_fiber_photometry.nwb")
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)
