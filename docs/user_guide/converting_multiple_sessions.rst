.. _converting_multiple_sessions:

Converting Multiple Sessions into a Dataset
===========================================

The :doc:`nwbconverter` page covers combining several streams into one NWB file, which is one
session. An experiment is usually many sessions, and converting all of them means running that
same conversion once per session and then organizing the collection of files that comes out.

Whatever that loop looks like, it should write a flat collection of uniquely named NWB files
into one output folder. The organization steps at the end of this page all take that folder as
their input.

Finding and Converting the Sessions
-----------------------------------

:py:class:`~neuroconv.tools.path_expansion.LocalPathExpander` finds the sessions and reads
``subject_id``, ``session_id`` and ``session_start_time`` out of the paths, as described in
:doc:`expand_path`. Each entry it returns carries a ``source_data`` dictionary shaped for the
converter and a ``metadata`` dictionary holding what the path names.

.. code-block:: python

    from pathlib import Path

    from neuroconv import NWBConverter
    from neuroconv.datainterfaces import SpikeGLXRecordingInterface, PhySortingInterface
    from neuroconv.tools.path_expansion import LocalPathExpander
    from neuroconv.utils.dict import load_dict_from_file, dict_deep_update

    class ExampleNWBConverter(NWBConverter):
        data_interface_classes = dict(
            SpikeGLXRecording=SpikeGLXRecordingInterface,
            PhySorting=PhySortingInterface
        )

    source_data_spec = {
        "SpikeGLXRecording": {
            "base_directory": "/path/to/raw_data",
            "file_path": "{subject_id}/{session_id}/{session_id}_g0_imec0/{session_id}_g0_imec0.ap.bin"
        },
        "PhySorting": {
            "base_directory": "/path/to/processed_data",
            "folder_path": "{subject_id}/{session_id}/phy"
        }
    }

    output_folder_path = Path("/path/to/output")
    output_folder_path.mkdir(exist_ok=True)

    lab_metadata = load_dict_from_file(file_path="my_lab_metadata.yml")

    sessions = LocalPathExpander().expand_paths(source_data_spec)
    for session in sessions:
        converter = ExampleNWBConverter(source_data=session["source_data"])

        metadata = converter.get_metadata()
        metadata = dict_deep_update(metadata, lab_metadata)
        metadata = dict_deep_update(metadata, session["metadata"])

        subject_id = metadata["Subject"]["subject_id"]
        session_id = metadata["NWBFile"]["session_id"]
        converter.run_conversion(
            nwbfile_path=output_folder_path / f"sub-{subject_id}_ses-{session_id}.nwb",
            metadata=metadata
        )

The metadata is merged in three passes so that the more specific source wins: what the
interfaces read from the data files, then the fields shared by every session in the dataset
(see :doc:`yaml`), then what the path expander recovered for this particular session.

Organizing the Converted Files
------------------------------

The output folder is now a flat collection of NWB files, which is the input format the tools
below expect. NeuroConv stops here: the layouts these produce are maintained elsewhere, and
which one you want depends on where the data is going.

Uploading to DANDI
~~~~~~~~~~~~~~~~~~

Upload to DANDI when the dataset is going to be published, so that the archive stores it, gives
it a citable identifier and serves it for streaming.

:py:func:`~neuroconv.tools.data_transfers.automatic_dandi_upload` organizes the folder into the
`DANDI <https://dandiarchive.org/>`_ layout and uploads it to a Dandiset you have already
created. It needs your API token in the ``DANDI_API_KEY`` environment variable, and the
``dandi`` extra installed.

.. code-block:: python

    from neuroconv.tools.data_transfers import automatic_dandi_upload

    automatic_dandi_upload(dandiset_id="123456", nwb_folder_path="/path/to/output")

Every file needs a ``session_id`` in its metadata, since DANDI requires one.

Reorganizing into BIDS
~~~~~~~~~~~~~~~~~~~~~~

Reorganize into BIDS when the dataset feeds tooling that expects that layout, or has to sit
beside other modalities of the same study in a single dataset.

NeuroConv does not write a `BIDS <https://bids.neuroimaging.io/>`_ (Brain Imaging Data
Structure) directory layout. BIDS organization is a separate step over finished NWB files, so
convert first and reorganize afterwards with `nwb2bids <https://github.com/con/nwb2bids>`_:

.. code-block:: bash

    pip install nwb2bids
    nwb2bids convert /path/to/output --bids-directory /path/to/bids

``nwb2bids`` renames the files and directories to BIDS conventions and fills the sidecar TSV and
JSON files from metadata already in the NWB files, so the more complete your conversion metadata
is, the more complete the BIDS output will be. Its ``participants.tsv`` and ``sessions.tsv`` are
tables across the dataset, which is why this step belongs to a collection of files rather than
to a single conversion. It targets
`BEP032 <https://bids-specification.readthedocs.io/en/bep032/modality-specific-files/microelectrode-electrophysiology.html>`_,
the microelectrode electrophysiology extension covering extracellular and intracellular
recordings and their associated behavioral events. That extension is still under formal review
and has not been merged into the BIDS specification, so the layout it produces may still change.
