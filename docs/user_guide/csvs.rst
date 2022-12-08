Specifying metadata using tables
================================

If your metadata is in Excel files or some other tabular format, it may be easiest
to get the data directly from comma-separated value (CSV) files. These
files can have the same metadata as the YAML files stored in a table.
Here is an example:

sessions.csv:

.. code-block:: csv

    session_id,session_description,session_start_time,lab,institution,experimenter,subject_id,spikeglx_filepath,dlc_filepath
    001,tentrode recordings with open exploration,1900-01-01T08:15:30-05:00,Name of lab,Name of institution,"Last1, First1;Last2, First2, M2.;Last3, First3",001,/path/to/ap.bin,/path/to/dlc
    002,tentrode recordings with open exploration,1900-01-02T08:15:30-05:00,Name of lab,Name of institution,"Last1, First1;Last2, First2, M2.;Last3, First3",001,/path/to/ap.bin,/path/to/dlc
    003,tentrode recordings with open exploration,1900-01-03T08:15:30-05:00,Name of lab,Name of institution,"Last1, First1;Last2, First2, M2.;Last3, First3",002,/path/to/ap.bin,/path/to/dlc
    004,tentrode recordings with open exploration,1900-01-04T08:15:30-05:00,Name of lab,Name of institution,"Last1, First1;Last2, First2, M2.;Last3, First3",002,/path/to/ap.bin,/path/to/dlc


subjects.csv:

.. code-block:: csv

    subject_id,sex,age,species
    001,M,P90D,Mus musculus
    002,F,P34D,Mus musculus

The available column names are the same as the attributes in the previous section. It is recommended to create these
files in Excel or Google Sheets and export the data as .csv.

.. code-block:: python

    import pandas as pd

    from neuroconv import ConverterPipe
    from neuroconv.datainterfaces import SpikeGLXRecordingInterface, DeepLabCutInterface
    from neuroconv.utils.dict import dict_deep_update


    df_subjects = pd.read_csv("subjects.csv")
    df_sessions = pd.read_csv("sessions.csv")

    # separate experimenters and keywords using semicolons
    for col in ("experimenter", "keywords"):
        if col in df_sessions:
            df_sessions[col] = df_sessions[col].apply(lambda x: x.split(";"))

    for i, row in df_sessions.iterrows():
        session_metadata = row.to_dict()
        spikeglx_filepath = session_metadata.pop("spikeglx_filepath")
        dlc_filepath = session_metadata.pop("dlc_filepath")
        subject_id = row.pop("subject_id")
        df_subjects.query("subject_id == @subject_id").iloc[0].to_dict()

        spikeglx_interface = SpikeGLXRecordingInterface(spikeglx_filepath)
        dlc_interface = DeepLabCutInterface(dlc_filepath)

        converter = ConverterPipe([spikeglx_interface, dlc_interface])

        metadata = converter.get_metadata()
        metadata = dict_deep_update(
            metadata,
            dict(
                NWBFile=session_metadata,
                Subject=subject_metadata,
            )
        )

        converter.run_conversion(f"nwb_out{i}.nwb", metadata=metadata)
