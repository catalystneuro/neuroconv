.. _converting_a_dataset:

Converting a Dataset
====================

The :doc:`nwbconverter` page covers combining several streams into one NWB file, which is one
session. An experiment is usually many sessions, and converting all of them means running that
same conversion once per session and then organizing the collection of files that comes out.

There are two routes for the conversion itself. Writing the loop in Python gives you the whole
API at every step, and it is the better fit when the sessions differ from one another or when
the metadata lives somewhere that needs code to read. A YAML specification describes the
dataset declaratively in a single file, which is easier to review, to keep under version
control and to hand to someone else, and it is what the Docker and AWS deployments run.

Either way, write a flat collection of uniquely named NWB files into one output folder. The
organization steps at the end of this page all take that folder as their input.

Converting in Python
--------------------

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

Converting from a YAML specification
------------------------------------

The same dataset can be described in a single YAML file. The ``metadata`` blocks are the ones
from :doc:`yaml`, and they may appear at three levels: at the top of the file for fields shared
by the whole dataset, on an experiment for fields shared by its sessions, and on a session for
fields belonging to it alone. They are merged in that order, so a session overrides its
experiment and an experiment overrides the file.

.. code-block:: yaml

    metadata:
      NWBFile:
        lab: My Lab
        institution: My Institution

    data_interfaces:
      ap: SpikeGLXRecordingInterface
      phy: PhySortingInterface

    experiments:
      my_experiment:
        metadata:
          NWBFile:
            session_description: My session.

        sessions:
          - nwbfile_name: sub-001_ses-20201010.nwb
            source_data:
              ap:
                file_path: spikeglx/Noise4Sam_g0/Noise4Sam_g0_imec0/Noise4Sam_g0_t0.imec0.ap.bin
            metadata:
              NWBFile:
                session_start_time: "2020-10-10T21:19:09+00:00"
              Subject:
                subject_id: "001"
                sex: F
                age: P35D
                species: Mus musculus

``data_interfaces`` maps a name to the interface class that reads that stream, and each session
addresses those same names in its ``source_data``. ``experiments`` is the only required key.
``conversion_options`` may be given at the top of the file or on a session.

Run the file from the command line:

.. code-block:: bash

    neuroconv /path/to/dataset.yml --data-folder-path /path/to/source --output-folder-path /path/to/output

``--data-folder-path`` is the root that every relative ``file_path`` and ``folder_path`` in the
specification is resolved against, and both options default to the folder holding the YAML file.
The same thing is available from Python as
:py:func:`~neuroconv.tools.yaml_conversion_specification.run_conversion_from_yaml`.

Running a specification requires the ``dandi`` extra, ``pip install neuroconv[dandi]``, which is
also what names the file of any session stating no ``nwbfile_name``: those are named from their
metadata once the whole dataset has been written.

Organizing the Converted Files
------------------------------

The output folder is now a flat collection of NWB files, which is the input format the tools
below expect. NeuroConv stops here: the layouts these produce are maintained elsewhere, and
which one you want depends on where the data is going.

Uploading to DANDI
~~~~~~~~~~~~~~~~~~

:py:func:`~neuroconv.tools.data_transfers.automatic_dandi_upload` organizes the folder into the
`DANDI <https://dandiarchive.org/>`_ layout and uploads it to a Dandiset you have already
created. It needs your API token in the ``DANDI_API_KEY`` environment variable, and the
``dandi`` extra installed.

.. code-block:: python

    from neuroconv.tools.data_transfers import automatic_dandi_upload

    automatic_dandi_upload(dandiset_id="123456", nwb_folder_path="/path/to/output")

A YAML specification can do this as the last step of the conversion instead, by adding the
Dandiset ID at the top of the file:

.. code-block:: yaml

    upload_to_dandiset: "123456"

Every session then needs a ``session_id`` in its metadata, since DANDI requires one.

Reorganizing into BIDS
~~~~~~~~~~~~~~~~~~~~~~

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

Running the Conversion Elsewhere
--------------------------------

A YAML specification is also what the two deployment guides run, without the dataset having to
be on your machine: :doc:`docker_demo` runs it in a container, and :doc:`aws_demo` transfers the
source data to AWS, converts it there and uploads the result straight to a Dandiset.
