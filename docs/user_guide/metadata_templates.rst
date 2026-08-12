.. _metadata_templates:

Metadata Templates
==================

An interface's ``get_metadata()`` returns only what its source file recorded, so it does not tell you
what else the NWB file needs from you. ``get_metadata_template()`` answers that second question: it
returns the same source-derived values wrapped in the full structure the writer expects, with the
cross-references between entries already resolved and every field only you can supply left blank.

The fiber photometry interfaces are the ones that offer it today. Other modalities will follow, and
this page grows a section for each.

Fill in the blanks and pass the result on:

.. code-block:: python

    metadata = interface.get_metadata_template()
    # fill in the blanks it marks, then
    interface.run_conversion(nwbfile_path="my_file.nwb", metadata=metadata)

The blanks are the checklist. What comes back blank is exactly what the source could not tell us, so
nothing here is a default: **fill what applies and delete what does not**. A required field left blank
fails the conversion rather than being guessed at, and an optional entry you do not want is deleted
rather than left empty, since deleting a block is what gives you a file without that object.

The blocks below are the same structures as files, for writing metadata by hand rather than in Python.
``load_dict_from_file`` accepts ``.yaml``, ``.yml`` and ``.json`` alike, so either format works as the
``metadata`` block of a conversion specification, or as a file you load and merge onto
``get_metadata()`` yourself. See :doc:`yaml` for that workflow.

Both tabs hold the same content, so copy whichever suits you, fill in the ``null`` values that apply
and delete the entries that do not. The YAML is annotated and the JSON is not, since JSON has no
comments. Dictionary keys are handles rather than names in the file, so rename them freely. Where a
structure repeats once per something in your recording, two entries are shown rather than one, so that
what changes between them is visible.


.. _fiber_photometry_metadata_template:

Fiber Photometry
----------------

One ``FiberPhotometryTable`` row per trace the interface writes, one optical fiber per row, and a
shared excitation source, photodetector and indicator. The rows are named in the order the series'
columns are written, and ``fiber_photometry_table_region`` has to list them in that same order, so
``trace_0`` and ``trace_1`` below are the first and second column of the series.

Rename ``calcium_signal`` to whatever ``metadata_key`` the interface was constructed with. The dichroic
mirror, the two optical filters and the three device models are optional, and appear so that you know
the writer accepts them at all. A filter is a ``BandOpticalFilter`` or an ``EdgeOpticalFilter``, never a
plain one, and its wavelengths belong to its model rather than to the filter itself.

For the same chain filled in with real values, built one block at a time and explained as it goes, see
:ref:`annotate_fiber_photometry_metadata`. That how-to also covers the layouts this block does not
show: one fiber recorded at a signal and an isosbestic wavelength, and several fibers in different
locations.

.. tab-set::

    .. tab-item:: YAML

        .. code-block:: yaml

            # Every `null` is yours to fill. Delete any entry your recording did not use.
            # Every key here is a handle you may rename, not a name in the file; `name` is the name in the file.

            # The equipment models: the make and catalogue specification, shared by every recording on that rig.
            # All three are optional. To drop one, delete it here and the `device_model_metadata_key` pointing at it.
            DeviceModels:
              optical_fiber_model:
                type: OpticalFiberModel
                name: optical_fiber_model
                manufacturer: null
                numerical_aperture: null
              excitation_source_model:
                type: ExcitationSourceModel
                name: excitation_source_model
                manufacturer: null
                source_type: null        # LED, laser
                excitation_mode: null    # one-photon, two-photon
              photodetector_model:
                type: PhotodetectorModel
                name: photodetector_model
                manufacturer: null
                detector_type: null      # photodiode, PMT

            # The equipment itself. One optical fiber per fiber you recorded from; the source and detector are
            # shared by all of them, since one interface writes one series through one light path.
            Devices:
              optical_fiber_0:
                type: OpticalFiber
                name: optical_fiber_0
                device_model_metadata_key: optical_fiber_model   # a key in DeviceModels above
                fiber_insertion:                                 # where this fiber sat, stereotaxic
                  insertion_position_ap_in_mm: null
                  insertion_position_ml_in_mm: null
                  insertion_position_dv_in_mm: null
                  depth_in_mm: null
              optical_fiber_1:                                   # one entry like this per fiber
                type: OpticalFiber
                name: optical_fiber_1
                device_model_metadata_key: optical_fiber_model
                fiber_insertion:
                  insertion_position_ap_in_mm: null
                  insertion_position_ml_in_mm: null
                  insertion_position_dv_in_mm: null
                  depth_in_mm: null
              excitation_source:
                type: ExcitationSource
                name: excitation_source
                device_model_metadata_key: excitation_source_model
              photodetector:
                type: Photodetector
                name: photodetector
                device_model_metadata_key: photodetector_model
              # Optional optics. Delete the entry and every row reference to it if the rig had none.
              dichroic_mirror:
                type: DichroicMirror
                name: dichroic_mirror
              excitation_filter:
                type: BandOpticalFilter    # or EdgeOpticalFilter; there is no plain OpticalFilter
                name: excitation_filter
              emission_filter:
                type: BandOpticalFilter
                name: emission_filter

            FiberPhotometry:
              # What was expressed in the tissue, and what it fluoresces as.
              FiberPhotometryIndicators:
                indicator:
                  name: indicator
                  label: null              # GCaMP6s, dLight1.1, tdTomato
              # One row per column of the response series, in the order the columns are written.
              FiberPhotometryTable:
                name: fiber_photometry_table
                description: 'Each row describes one trace: the fiber, hardware and indicator that produced it.'
                rows:
                  trace_0:
                    location: null                           # the brain region this fiber sat in
                    excitation_wavelength_in_nm: null
                    emission_wavelength_in_nm: null
                    # Each of these names a key above, wiring this trace to the hardware that produced it.
                    indicator_metadata_key: indicator
                    optical_fiber_metadata_key: optical_fiber_0
                    excitation_source_metadata_key: excitation_source
                    photodetector_metadata_key: photodetector
                    dichroic_mirror_metadata_key: dichroic_mirror        # optional, delete if unused
                    excitation_filter_metadata_key: excitation_filter    # optional, delete if unused
                    emission_filter_metadata_key: emission_filter
                    coordinates: null                        # (ap, ml, dv) of the recorded volume, in mm
                    notes: null        # optional, delete if unused
                  trace_1:                                   # one entry like this per trace
                    location: null
                    excitation_wavelength_in_nm: null
                    emission_wavelength_in_nm: null
                    indicator_metadata_key: indicator
                    optical_fiber_metadata_key: optical_fiber_1          # the only line that differs
                    excitation_source_metadata_key: excitation_source
                    photodetector_metadata_key: photodetector
                    dichroic_mirror_metadata_key: dichroic_mirror
                    excitation_filter_metadata_key: excitation_filter
                    emission_filter_metadata_key: emission_filter
                    coordinates: null                        # (ap, ml, dv) of the recorded volume, in mm
                    notes: null
              # Rename this key to the `metadata_key` the interface was constructed with.
              calcium_signal:
                name: FiberPhotometryResponseSeries
                description: null
                fiber_photometry_table_region:   # the rows above, in the order the series' columns are written
                  - trace_0
                  - trace_1

    .. tab-item:: JSON

        .. code-block:: json

            {
                "DeviceModels": {
                    "optical_fiber_model": {
                        "type": "OpticalFiberModel",
                        "name": "optical_fiber_model",
                        "manufacturer": null,
                        "numerical_aperture": null
                    },
                    "excitation_source_model": {
                        "type": "ExcitationSourceModel",
                        "name": "excitation_source_model",
                        "manufacturer": null,
                        "source_type": null,
                        "excitation_mode": null
                    },
                    "photodetector_model": {
                        "type": "PhotodetectorModel",
                        "name": "photodetector_model",
                        "manufacturer": null,
                        "detector_type": null
                    }
                },
                "Devices": {
                    "optical_fiber_0": {
                        "type": "OpticalFiber",
                        "name": "optical_fiber_0",
                        "device_model_metadata_key": "optical_fiber_model",
                        "fiber_insertion": {
                            "insertion_position_ap_in_mm": null,
                            "insertion_position_ml_in_mm": null,
                            "insertion_position_dv_in_mm": null,
                            "depth_in_mm": null
                        }
                    },
                    "optical_fiber_1": {
                        "type": "OpticalFiber",
                        "name": "optical_fiber_1",
                        "device_model_metadata_key": "optical_fiber_model",
                        "fiber_insertion": {
                            "insertion_position_ap_in_mm": null,
                            "insertion_position_ml_in_mm": null,
                            "insertion_position_dv_in_mm": null,
                            "depth_in_mm": null
                        }
                    },
                    "excitation_source": {
                        "type": "ExcitationSource",
                        "name": "excitation_source",
                        "device_model_metadata_key": "excitation_source_model"
                    },
                    "photodetector": {
                        "type": "Photodetector",
                        "name": "photodetector",
                        "device_model_metadata_key": "photodetector_model"
                    },
                    "dichroic_mirror": {
                        "type": "DichroicMirror",
                        "name": "dichroic_mirror"
                    },
                    "excitation_filter": {
                        "type": "BandOpticalFilter",
                        "name": "excitation_filter"
                    },
                    "emission_filter": {
                        "type": "BandOpticalFilter",
                        "name": "emission_filter"
                    }
                },
                "FiberPhotometry": {
                    "FiberPhotometryIndicators": {
                        "indicator": {
                            "name": "indicator",
                            "label": null
                        }
                    },
                    "FiberPhotometryTable": {
                        "name": "fiber_photometry_table",
                        "description": "Each row describes one trace: the fiber, hardware and indicator that produced it.",
                        "rows": {
                            "trace_0": {
                                "location": null,
                                "excitation_wavelength_in_nm": null,
                                "emission_wavelength_in_nm": null,
                                "indicator_metadata_key": "indicator",
                                "optical_fiber_metadata_key": "optical_fiber_0",
                                "excitation_source_metadata_key": "excitation_source",
                                "photodetector_metadata_key": "photodetector",
                                "dichroic_mirror_metadata_key": "dichroic_mirror",
                                "excitation_filter_metadata_key": "excitation_filter",
                                "emission_filter_metadata_key": "emission_filter",
                                "coordinates": null,
                                "notes": null
                            },
                            "trace_1": {
                                "location": null,
                                "excitation_wavelength_in_nm": null,
                                "emission_wavelength_in_nm": null,
                                "indicator_metadata_key": "indicator",
                                "optical_fiber_metadata_key": "optical_fiber_1",
                                "excitation_source_metadata_key": "excitation_source",
                                "photodetector_metadata_key": "photodetector",
                                "dichroic_mirror_metadata_key": "dichroic_mirror",
                                "excitation_filter_metadata_key": "excitation_filter",
                                "emission_filter_metadata_key": "emission_filter",
                                "coordinates": null,
                                "notes": null
                            }
                        }
                    },
                    "calcium_signal": {
                        "name": "FiberPhotometryResponseSeries",
                        "description": null,
                        "fiber_photometry_table_region": [
                            "trace_0",
                            "trace_1"
                        ]
                    }
                }
            }
