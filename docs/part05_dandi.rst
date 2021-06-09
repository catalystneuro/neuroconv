Part 5, Publishing NWB on DANDI Archive
=======================================

Once you you have completed the conversion of all the data in your dataset,
we encourage you to publish this data. We recommend the `DANDI archive <https://dandiarchive.org>`_.
DANDI can handle large volumes (TBs) of data and host them for free, and provides a command-line interface
(CLI) that is built to handle this volume of data. DANDI also automatically parses NWB
files to extract metadata that makes these datasets easier for others to find.

Refer to the `DANDI documentation <https://www.dandiarchive.org/handbook/10_using_dandi/#uploading-a-dandiset>`_ for how to upload your dataset.

.. note::
    DANDI requires each NWB file to have a `Subject` field with `subject_id` defined. It is possible to create a
    valid NWB file without this field, but it will not be accepted by DANDI.

If you experience any problems or questions, the `DANDI helpdesk <https://github.com/dandi/helpdesk/discussions>`_ is the best place to ask for help. 
