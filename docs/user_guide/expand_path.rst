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
provide a ``base_directory`` path and a "``file_path``" or "``folder_path``" argument in f-string format. The path
expander will find all matching paths and automatically extract the specified metadata.

.. code-block:: python

    from pathlib import Path

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
dictionaries: ``source_data`` and ``metadata``. The ``source_data`` dictionary contains the resolved path of each
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

Example Usage
----------------

Below are some full examples of how this feature can be used on some organizational patterns taken from real datasets.

Example 1: `Allen Institute Visual Coding Dataset <https://registry.opendata.aws/allen-brain-observatory/>`_
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Allen Institute's Visual Coding dataset contains, among other data, motion-corrected videos of each
experimental session, with the directory structure shown below.

.. code-block:: bash

    allen-brain-observatory/
    ¦   visual-coding-2p/
    ¦   +-- ophys_movies/
    ¦   ¦   +-- ophys_experiment_496908818.h5
    ¦   ¦   +-- ophys_experiment_496934409.h5
    ¦   ¦   +-- ophys_experiment_496935917.h5
    ¦   ¦   +-- ...

The video files are all stored in the directory ``ophys_movies/``, and their file names follow the pattern
``ophys_experiment_`` plus a 9-digit session ID. We can use
:py:class:`~neuroconv.tools.path_expansion.LocalPathExpander` to find all of these ``ophys_movies`` files and extract
their session IDs with the following code block.

.. code-block:: python

    source_data_spec = {
        "allen-visual-coding": {
            "base_directory": "/allen-brain-observatory/visual-coding-2p",
            "file_path": "ophys_movies/ophys_experiment_{session_id}.h5"
        }
    }
    path_expander = LocalPathExpander()
    metadata_list = path_expander.expand_paths(source_data_spec)

The ``metadata_list`` now contains the information extracted for each matching file found by
:py:class:`~neuroconv.tools.path_expansion.LocalPathExpander`. The information for the first file is shown below.

.. code-block:: python

    {
        "source_data": {
            "allen-visual-coding": {
                "file_path": "/allen-brain-observatory/visual-coding-2p/ophys_movies/ophys_experiment_496908818.h5"
            }
        },
        "metadata": {
            "NWBFile": {
                "session_id": "496908818"
            }
        }
    }

Example 2: `Buszaki Lab SenzaiY Dataset <https://app.globus.org/file-manager?origin_id=188a6110-96db-11eb-b7a9-f57b2d55370d&origin_path=%2FSenzaiY%2F>`_
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Buszaki Lab's SenzaiY dataset contains spiking and LFP data from mouse V1 with the directory structure
shown below. Sorted unit spiking data are stored in the ``.res.1`` and ``.clu.1`` files, while the LFP data are
stored in the ``.eeg`` files.

.. code-block:: bash

    SenzaiY/
    ¦   YMV01/
    ¦   +-- YMV01_170818/
    ¦   ¦   +-- YMV01_170818.eeg
    ¦   ¦   +-- YMV01_170818.res.1
    ¦   ¦   +-- YMV01_170818.clu.1
    ¦   ¦   +-- ...
    ¦   YMV02/
    ¦   +-- YMV02_170815/
    ¦   ¦   +-- YMV01_170815.eeg
    ¦   ¦   +-- YMV01_170815.res.1
    ¦   ¦   +-- YMV01_170815.clu.1
    ¦   ¦   +-- ...
    ¦   ...

The data are organized into folders first by subject (``YMV01``, ``YMV02``, etc.) and then by session start times in
the format ``yymmdd`` (``170818``, ``170815``, etc). We can use
:py:class:`~neuroconv.tools.path_expansion.LocalPathExpander` to find both the LFP data files and the sorted unit
spiking and extract their corresponding subject IDs and session start times. For the sorted unit spiking, we'll search
for a matching ``folder_path`` instead of a ``file_path``, as ``neuroconv`` interfaces for such data, like
:py:class:`~neuroconv.datainterfaces.ecephys.neuroscope.neuroscopedatainterface.NeuroScopeSortingInterface`, expect a
``folder_path`` as input.

.. code-block:: python

    source_data_spec = {
        "SenzaiY_LFP": {
            "base_directory": "/SenzaiY/",
            "file_path": "{subject_id}/{subject_id}_{session_start_time:%y%m%d}/{subject_id}_{session_start_time:%y%m%d}.eeg"
        },
        "SenzaiY_Spiking": {
            "base_directory": "/SenzaiY/",
            "folder_path": "{subject_id}/{subject_id}_{session_start_time:%y%m%d}/"
        }
    }
    path_expander = LocalPathExpander()
    metadata_list = path_expander.expand_paths(source_data_spec)

The ``metadata_list`` now contains the information extracted for each matching file and directory found by
:py:class:`~neuroconv.tools.path_expansion.LocalPathExpander`. The information for the first file is shown below.

.. code-block:: python

    {
        "source_data": {
            "SenzaiY_LFP": {
                "file_path": "/SenzaiY/YMV01/YMV01_170818/YMV01_170818.eeg"
            }
        },
        "metadata": {
            "NWBFile": {
                "session_start_time": datetime.datetime(2017, 8, 18, 0, 0)
            },
            "Subject": {
                "subject_id": "YMV01"
            }
        }
    }

The information found for the first matching directory is similar.

.. code-block:: python

    {
        "source_data": {
            "SenzaiY_Spiking": {
                "folder_path": "/SenzaiY/YMV01/YMV01_170818/"
            }
        },
        "metadata": {
            "NWBFile": {
                "session_start_time": datetime.datetime(2017, 8, 18, 0, 0)
            },
            "Subject": {
                "subject_id": "YMV01"
            }
        }
    }

Example 3: `IBL Brain Wide Map Data <https://ibl.flatironinstitute.org/public>`_
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The IBL's Brain Wide Map features data from several labs of mice performing a visual decision-making task. Some
experimental sessions, such as those from the Steinmetz Lab, include video recordings of the experiments from three
cameras, stored in the following directory structure.

.. code-block:: bash

    steinmetzlab/
    ¦   Subjects/
    ¦   +-- NR_0017/
    ¦   ¦   +-- 2022-03-22/
    ¦   ¦   ¦   +-- 001/
    ¦   ¦   ¦   ¦   +-- raw_video_data/
    ¦   ¦   ¦   ¦   ¦   +-- _iblrig_leftCamera.raw.6252a2f0-c10f-4e49-b085-75749ba29c35.mp4
    ¦   ¦   ¦   ¦   ¦   +-- ...
    ¦   ¦   ¦   ¦   +-- ...
    ¦   +-- NR_0019/
    ¦   ¦   +-- 2022-04-29/
    ¦   ¦   ¦   +-- 001/
    ¦   ¦   ¦   ¦   +-- raw_video_data/
    ¦   ¦   ¦   ¦   ¦   +-- _iblrig_leftCamera.raw.9041b63e-02e2-480e-aaa7-4f6b776a647f.mp4
    ¦   ¦   ¦   ¦   ¦   +-- ...
    ¦   ¦   ¦   ¦   +-- ...
    ¦   ...

We can use :py:class:`~neuroconv.tools.path_expansion.LocalPathExpander` to find these left camera video files and
extract the subject ID, the session start time (formatted as ``yyyy-mm-dd``), and a session number (``001`` for
both files shown).

.. code-block:: python

    source_data_spec = {
        "IBL_video": {
            "base_directory": "/steinmetzlab/",
            "file_path": "Subjects/{subject_id}/{session_start_time:%Y-%m-%d}/{session_id}/raw_video_data/_iblrig_leftCamera.raw.{}.mp4"
        }
    }
    path_expander = LocalPathExpander()
    metadata_list = path_expander.expand_paths(source_data_spec)

The ``metadata_list`` now contains the information extracted for each matching file found by
:py:class:`~neuroconv.tools.path_expansion.LocalPathExpander`. The information for the first file is shown below.

.. code-block:: python

    {
        "source_data": {
            "IBL_video": {
                "file_path": "/steinmetzlab/Subjects/NR_0017/2022-03-22/001/raw_video_data/_iblrig_leftCamera.raw.6252a2f0-c10f-4e49-b085-75749ba29c35.mp4"
            }
        },
        "metadata": {
            "NWBFile": {
                "session_id": "001",
                "session_start_time": datetime.datetime(2022, 3, 22, 0, 0)
            },
            "Subject": {
                "subject_id": "NR_0017"
            }
        }
    }

If you would like to experiment locally with :py:class:`~neuroconv.tools.path_expansion.LocalPathExpander`, we
provide a helper method in :py:mod:`neuroconv.tools.testing <neuroconv.tools.testing.mock_files>` that partially
replicates the directory structure of the IBL data with dummy files on your machine.

.. code-block:: python

    from neuroconv.tools.testing import generate_path_expander_demo_ibl

    generate_path_expander_demo_ibl(folder_path="path/to/generate/dummy/files")

Non-local Path Expansion
------------------------
Note that :py:class:`~neuroconv.tools.path_expansion.LocalPathExpander` expands file paths locally, so it can only
expand file paths that are on the same system as the code. Other types of path expanders could be implemented to
support different platforms, such as Google Drive, Dropbox, or S3. These tools have not yet been developed, but would
extend from the :py:class:`~neuroconv.tools.path_expansion.AbstractPathExpander`

.. _Format Specification Mini-Language: https://docs.python.org/3/library/string.html#formatspec
.. _`1989 C standard format codes`:
  https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes
