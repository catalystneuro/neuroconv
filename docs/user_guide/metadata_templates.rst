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

The blocks below are those structures written out as files. ``load_dict_from_file`` accepts ``.yaml``,
``.yml`` and ``.json`` alike, so either format works as the ``metadata`` block of a conversion
specification, or as a file you load and merge onto ``get_metadata()`` yourself. See :doc:`yaml` for
that workflow.

Every block on this page is generated when the documentation is built, so each one is what the method
returns rather than a transcription of it. Dictionary keys are handles rather than names in the file,
so rename them to suit your recording. Where a structure scales with the recording, the block shows two
entries rather than one, so that what repeats is visible in the block itself.


.. _fiber_photometry_metadata_template:

Fiber Photometry
----------------

One ``FiberPhotometryTable`` row per trace the interface writes, one optical fiber per row, and a
shared excitation source, photodetector and indicator. The rows are named in the order the series'
columns are written, and ``fiber_photometry_table_region`` has to list them in that same order.

The dichroic mirror, the two optical filters and the three device models are optional. They appear so
that you know the writer accepts them at all; delete the ones your recording did not use.

.. metadata-template:: MockFiberPhotometryInterface(num_fibers=2, metadata_key="gcamp_dms")
   :exclude: NWBFile
