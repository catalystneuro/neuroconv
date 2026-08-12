.. _bids_output:

BIDS Output
===========

NeuroConv writes NWB files; it does not write a `BIDS <https://bids.neuroimaging.io/>`_
(Brain Imaging Data Structure) directory layout. BIDS organization is a separate step that
operates on finished NWB files, so run your conversion first and reorganize afterwards with
`nwb2bids <https://github.com/con/nwb2bids>`_:

.. code-block:: bash

    pip install nwb2bids
    nwb2bids convert path/to/nwb/files/ --bids-directory path/to/bids/output/

``nwb2bids`` renames the files and directories to BIDS conventions and populates the sidecar
TSV and JSON files from metadata already present in the NWB files, so the more complete your
conversion metadata is, the more complete the BIDS output will be. It targets
`BEP032 <https://bids-specification.readthedocs.io/en/bep032/modality-specific-files/microelectrode-electrophysiology.html>`_,
the microelectrode electrophysiology extension covering extracellular and intracellular
recordings and their associated behavioral events. That extension is still under formal
review and has not been merged into the BIDS specification, so the layout it produces may
still change.
