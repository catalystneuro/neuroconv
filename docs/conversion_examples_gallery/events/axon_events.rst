Axon tags
---------

Use :py:class:`~neuroconv.datainterfaces.AxonEventsInterface` once per file to write the tags
recorded during acquisition, including tags between sweeps. Each tag type present in the file
gets its own events table. Each row carries the event ``timestamp`` in seconds and the
``tag_type`` as text. An annotation tag can have both a short ``comment`` and a separate
``annotation`` text. For a voice tag, ``voice_series_name`` identifies the acquisition time
series containing its audio.

Install the dependency for compressed voice tags:

.. code-block:: bash

    pip install "neuroconv[axon_events]"

.. code-block:: python

    >>> from neuroconv.datainterfaces import AxonEventsInterface
    >>> file_path = f"{ECEPHY_DATA_PATH}/axon/intracellular_data/tags/time_and_comment.abf"
    >>> interface = AxonEventsInterface(file_path=file_path)
    >>> interface.get_event_type_source_ids()
    ['tags_time', 'tags_comment']
    >>> interface.run_conversion(nwbfile_path=f"{path_to_save_nwbfile}")

To select only comment tags, specify the type by name. An explicitly requested type with no
matching tags produces an empty table.

.. code-block:: python

    >>> configuration = {"markers": {"separation": {"by_payload_fields": ["tag_type"], "select": ["comment"]}}}
    >>> interface = AxonEventsInterface(file_path=file_path, event_extraction_configuration=configuration)
    >>> interface.get_event_type_source_ids()
    ['markers_comment']
