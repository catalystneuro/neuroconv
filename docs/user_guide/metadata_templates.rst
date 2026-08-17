.. _metadata_templates:

Metadata Templates
==================

An interface's ``get_metadata()`` returns only what its source file recorded, so it does not tell you
what else the NWB file needs from you. ``get_metadata_template()`` answers that second question: it
returns the same source-derived values wrapped in the full structure the writer expects, with the
cross-references between entries already resolved and every field only you can supply left blank.

The fiber photometry and optical physiology interfaces are the ones that offer it today. Other
modalities will follow, and this page grows a section for each.

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

        .. literalinclude:: metadata_templates/fiber_photometry.yaml
           :language: yaml

    .. tab-item:: JSON

        .. literalinclude:: metadata_templates/fiber_photometry.json
           :language: json


.. _ophys_metadata_template:

Optical Physiology
------------------

An imaging interface and a segmentation interface each get their own block below, and the two overlap:
both describe an imaging plane and the microscope behind it, because a segmentation is ROIs drawn on a
plane that was imaged. In a conversion that has both, keep one copy of the ``Devices`` and
``ImagingPlanes`` entries and point the series and the segmentation at it, rather than writing the
plane twice.

For either block filled in with real values, including that shared-plane case and several segmentation
pipelines on one recording, see :ref:`annotate_ophys_metadata`.

.. _ophys_imaging_metadata_template:

Imaging
~~~~~~~

One imaging plane and one series, cross-referenced by ``imaging_plane_metadata_key``. Rename
``calcium_imaging`` to whatever ``metadata_key`` the interface was constructed with, in both blocks.
A multi-plane or multi-channel acquisition is several interfaces rather than several entries here, so
each one brings its own key; the ``optical_channel`` list is the exception, and holds one entry per
channel the plane was imaged in.

The last three fields of the series are what a two-photon acquisition describes. A one-photon one takes
``exposure_time``, ``binning``, ``power`` and ``intensity`` in their place, which is what
``get_metadata_template()`` returns for an interface built with ``photon_series_type="OnePhotonSeries"``.

.. tab-set::

    .. tab-item:: YAML

        .. literalinclude:: metadata_templates/ophys_imaging.yaml
           :language: yaml

    .. tab-item:: JSON

        .. literalinclude:: metadata_templates/ophys_imaging.json
           :language: json

.. _ophys_segmentation_metadata_template:

Segmentation
~~~~~~~~~~~~

The plane segmentation, its traces and its summary images all sit under one key, because the writer
resolves all three through the interface's ``metadata_key``; rename ``calcium_segmentation`` in all four
blocks together.

The inner keys of ``RoiResponses`` and ``SegmentationImages`` are the exception to the rename-freely
rule above. They are the names roiextractors reads traces and images under, so ``raw``, ``dff``,
``neuropil``, ``deconvolved``, ``denoised``, ``baseline``, ``mean`` and ``correlation`` are fixed, and
what you choose is the ``name`` inside each. Delete the ones your pipeline did not produce;
``get_metadata_template()`` offers only the ones the file actually holds.

.. tab-set::

    .. tab-item:: YAML

        .. literalinclude:: metadata_templates/ophys_segmentation.yaml
           :language: yaml

    .. tab-item:: JSON

        .. literalinclude:: metadata_templates/ophys_segmentation.json
           :language: json
