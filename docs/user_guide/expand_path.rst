Path Expansion
===============

Source data are often stored in an organizational structure where some of the metadata of the experiment,
such as the subject and session IDs, are included in the folder names and file paths of the data. The
:py:mod:`~neuroconv.tools.path_expansion` module allows a user to specify this path pattern so that NeuroConv can
identify all matching data and automatically extract the relevant metadata.


Local Path Expander
-------------------
Use the :py:class:`~neuroconv.tools.path_expansion.LocalPathExpander` to find matching paths in your local filesystem.
This class requires a source data specification, in which you can list multiple data interfaces by name, and for each
provide a ``base_directory`` path and a ``"file_path"`` or ``"folder_path"`` argument in f-string format. The path
expander will find all matching paths and automatically extract the specified metadata.

.. code-block:: python

    from pathlib import Path
    from typing import Dict

    from neuroconv.tools.path_expansion import LocalPathExpander

    # Specify source data
    source_data_spec = {
        "spikeglx": {
            "base_directory": "/path/to/raw_data",
            "file_path": "{subject_id}/{session_id}/{session_id}_g0_imec0/{session_id}_g0_imec0.ap.bin"
        },
        "phy" : {
            "base_directory": "/path/to/processed_data"
            "folder_path": "{subject_id}/{session_id}/phy"
        }
    }

    # Instantiate LocalPathExpander
    path_expander = LocalPathExpander()

    # Expand paths and extract metadata
    metadata_list = path_expander.expand_paths(source_data_spec)

    # Print the results
    for metadata in metadata_list:
        print(metadata)

The ``expand_paths`` method returns a list of :py:class:`~neuroconv.utils.dict.DeepDict` objects that contain two
dictionaries: ``source_data`` and ``metadata``. The ``source_data`` dictionary contains the resolved filepath of each
interface, while the ``metadata`` dictionary contains the metadata extracted from the filepaths. Currently, only
``subject_id``, ``session_id``, and ``session_start_time`` are supported, but this approach could in principle be
extended to support extraction of more metadata.

Specifying Metadata Format
--------------------------
The f-string format allows you to constrain the search for more precise metadata matching using the
`Format Specification Mini-Language`_ and the `1989 C standard format codes`_ for datetimes. Below are some common
examples.

Length
~~~~~~
For example, you might have a data path where the ``subject_id`` and ``session_id`` are next to each other, and they
can be disambiguated because the ``subject_id`` is always 4 characters and the ``session_id`` is always 5 characters.
This can be expressed as ``"{subject_id:4}{session_id:5}"``.

Character type
~~~~~~~~~~~~~~
If the ``subject_id`` is always numeric, you could use ``n``, e.g. ``"{subject_id:n}"``, which will match only digits.

Datetimes
~~~~~~~~~
If your session start time is present in your data path, you can indicate this following the
`1989 C standard format codes`_ for datetimes. For example, ``"{session_start_time:%Y-%m-%d}"`` will match
``"2021-01-02"`` and evaluate it to ``datetime.datetime(2021, 1, 2)``.


Non-local Path Expansion
------------------------
Note that :py:class:`~neuroconv.tools.path_expansion.LocalPathExpander` expands file paths locally, so it can only
expand file paths that are on the same system as the code. Other types of path expanders could be implemented to
support different platforms, such as Google Drive, Dropbox, or S3. These tools have not yet been developed, but would
extend from the :py:class:`~neuroconv.tools.path_expansion.AbstractPathExpander`

.. _Format Specification Mini-Language: https://docs.python.org/3/library/string.html#formatspec
.. _`1989 C standard format codes`:
  https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes
