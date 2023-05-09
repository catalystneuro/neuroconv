Path Expansion
===============

:py:mod:`~neuroconv.tools.path_expansion` module provides helpful classes for expanding file or folder paths on a
system given a f-string rule for matching patterns. The module includes an abstract base class
:py:class:`~neuroconv.tools.path_expansion.AbstractPathExpander`, and a concrete subclass
:py:class:`~neuroconv.tools.path_expansion.LocalPathExpander` that inherits from it.
:py:class:`~neuroconv.tools.path_expansion.AbstractPathExpander` provides an interface for extracting metadata from
file paths, while :py:class:`~neuroconv.tools.path_expansion.LocalPathExpander` implements it to expand local file
paths.

Local Path Expander
-------------------

:py:class:`~neuroconv.tools.path_expansion.LocalPathExpander` is a concrete subclass of
:py:class:`~neuroconv.tools.path_expansion.AbstractPathExpander` that expands local file paths. To use it, create an instance of the
:py:class:`~neuroconv.tools.path_expansion.LocalPathExpander` class and call its ``expand_paths`` method with a source
data spec.

.. code-block:: python

    from pathlib import Path
    from typing import Dict

    from neuroconv.tools.path_expansion import LocalPathExpander


    # Instantiate LocalPathExpander
    path_expander = LocalPathExpander()

    # Specify source data
    source_data_spec = {
        "spikeglx": {
            "base_directory": "data",
            "file_path": "sub-{subject_id}/sub-{subject_id}_ses-{session_id}.nwb"
        }
    }

    # Expand paths and extract metadata
    metadata_list = path_expander.expand_paths(source_data_spec)

    # Print the results
    for metadata in metadata_list:
        print(metadata)

In the example above, we first create an instance of :py:class:`~neuroconv.tools.path_expansion.LocalPathExpander`.
We then specify a source data spec in the form of a dictionary. The dictionary specifies the interface, base
directory, and f-string format for the file path. We then call the ``expand_paths`` method with the source data spec,
which returns a list of :py:class:`~neuroconv.utils.dict.DeepDict` objects that contain the metadata extracted from
the file paths that match the f-string format.

The :py:class:`~neuroconv.utils.dict.DeepDict` objects contain two dictionaries: ``source_data`` and ``metadata``. The
``source_data`` dictionary contains the file path and the interface, while the ``metadata`` dictionary contains the
metadata extracted from the file path. Currently, only ``subject_id`` and ``session_id`` are supported, but this
approach could in principle be extended to support extraction of more metadata.

Note that :py:class:`~neuroconv.tools.path_expansion.LocalPathExpander` expands file paths locally, so it can only
expand file paths that are on the same system as the code.

Specifying Metadata Format
--------------------------
You can specify the form of the metadata using the `Format Specification Mini-Language`_. The `parse`_ library uses this
information to constrain the search for metadata. For example, let's say you have a path pattern where the
``subject_id`` and ``session_id`` are next to each other, and they can be disambiguated because the subject_id is
always 4 characters and the session_id is always 5 characters. This can be expressed as
``"{subject_id:4}{session_id:5}"``. Similarly, if the ``subject_id`` is always numeric you could use
``"{subject_id:n}"``.

.. _parse: https://pypi.org/project/parse/
.. _Format Specification Mini-Language: https://docs.python.org/3/library/string.html#formatspec
