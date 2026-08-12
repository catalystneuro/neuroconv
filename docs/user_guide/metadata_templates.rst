.. _metadata_templates:

Metadata Templates
==================

An interface's ``get_metadata()`` returns only what its source file recorded, so it does not tell you
what else the NWB file needs from you. ``get_metadata_template()`` answers that second question: it
returns the same source-derived values wrapped in the full structure the writer expects, with the
cross-references between entries already resolved and every field only you can supply left blank.

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

Both formats hold the same content, so copy whichever suits you, fill in the ``null`` values that apply
and delete the entries that do not. Dictionary keys are handles rather than names in the file, so
rename them freely. Where a structure repeats once per something in your recording, two entries are
shown rather than one, so that what changes between them is visible.


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
plain one, and its wavelengths belong to its model rather than to the filter itself. Rows also accept
``coordinates`` and ``notes``, left out here for brevity.

.. tab-set::

    .. tab-item:: YAML

        .. code-block:: yaml

            DeviceModels:
              optical_fiber_model:
                type: OpticalFiberModel
                name: optical_fiber_model
                numerical_aperture: null
              excitation_source_model:
                type: ExcitationSourceModel
                name: excitation_source_model
                source_type: null
                excitation_mode: null
              photodetector_model:
                type: PhotodetectorModel
                name: photodetector_model
                detector_type: null
            Devices:
              optical_fiber_0:
                type: OpticalFiber
                name: optical_fiber_0
                device_model_metadata_key: optical_fiber_model
                fiber_insertion:
                  insertion_position_ap_in_mm: null
                  insertion_position_ml_in_mm: null
                  insertion_position_dv_in_mm: null
                  depth_in_mm: null
              optical_fiber_1:
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
              dichroic_mirror:
                type: DichroicMirror
                name: dichroic_mirror
              excitation_filter:
                type: BandOpticalFilter
                name: excitation_filter
              emission_filter:
                type: BandOpticalFilter
                name: emission_filter
            FiberPhotometry:
              FiberPhotometryIndicators:
                indicator:
                  name: indicator
                  label: null
              FiberPhotometryTable:
                name: fiber_photometry_table
                description: 'Each row describes one trace: the fiber, hardware and indicator that produced it.'
                rows:
                  trace_0:
                    location: null
                    excitation_wavelength_in_nm: null
                    emission_wavelength_in_nm: null
                    indicator_metadata_key: indicator
                    optical_fiber_metadata_key: optical_fiber_0
                    excitation_source_metadata_key: excitation_source
                    photodetector_metadata_key: photodetector
                    dichroic_mirror_metadata_key: dichroic_mirror
                    excitation_filter_metadata_key: excitation_filter
                    emission_filter_metadata_key: emission_filter
                  trace_1:
                    location: null
                    excitation_wavelength_in_nm: null
                    emission_wavelength_in_nm: null
                    indicator_metadata_key: indicator
                    optical_fiber_metadata_key: optical_fiber_1
                    excitation_source_metadata_key: excitation_source
                    photodetector_metadata_key: photodetector
                    dichroic_mirror_metadata_key: dichroic_mirror
                    excitation_filter_metadata_key: excitation_filter
                    emission_filter_metadata_key: emission_filter
              calcium_signal:
                name: FiberPhotometryResponseSeries
                description: null
                fiber_photometry_table_region:
                  - trace_0
                  - trace_1

    .. tab-item:: JSON

        .. code-block:: json

            {
                "DeviceModels": {
                    "optical_fiber_model": {
                        "type": "OpticalFiberModel",
                        "name": "optical_fiber_model",
                        "numerical_aperture": null
                    },
                    "excitation_source_model": {
                        "type": "ExcitationSourceModel",
                        "name": "excitation_source_model",
                        "source_type": null,
                        "excitation_mode": null
                    },
                    "photodetector_model": {
                        "type": "PhotodetectorModel",
                        "name": "photodetector_model",
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
                                "emission_filter_metadata_key": "emission_filter"
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
                                "emission_filter_metadata_key": "emission_filter"
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
