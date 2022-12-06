Using YAML to specify metadata
===============================

While it is possible to specify all metadata programmatically in Python,
it is often more convenient to use YAML files. These files can store data
persistently, can be reused across different conversion projects, and can
be easily inspected and edited without changing any of the conversion software.

Below is the metadata for :py:class:`~pynwb.file.NWBFile` and
:py:class:`~pynwb.file.Subject`, which is applicable to all NWB
conversions

.. code-block:: yaml

    NWBFile:
      session_id:  # required by DANDI
      session_description: # required by NWB
      session_start_time: "1900-01-01T08:15:30-05:00" # required by NWB
      lab:
      institution:
      experimenter:
        - "Last, First"
        - "Last, First M."
      experiment_description:
      keywords:
        - "olfaction"
        - "neuropixels"
      notes:
      pharmacology:
      protocol:
      related_publications:
        - "https://doi.org/10.7554/eLife.78362"
      source_script:
      source_script_file_name:
      data_collection:
      surgery:
      virus:
      stimulus_notes:
    Subject:
      subject_id:  # required by DANDI
      description:
      species:  # Latin binomial, e.g. "Mus musculus" or "Homo sapiens"; required by DANDI
      genotype:
      strain:
      sex:  # required by DANDI
      age:  # required by DANDI
      weight:
      date_of_birth:  # can be used instead of age

See the API documentation for :py:class:`~pynwb.file.NWBFile` and
:py:class:`~pynwb.file.Subject` for the intended use and form of each of these fields.

The fields marked as "required" will be needed later when converting to NWB or uploading to DANDI.
It is sometimes possible to extract these fields from source data files or gather them from other
sources, in which case it would not be necessary to populate them here.

This metadata can easily be added to any conversion pipelines. The content of the YAML file can be loaded as a
dictionary using :py:meth:`~neuroconv.utils.dict.load_dict_from_file`. Then the metadata can be updated using
:py:meth:`~neuroconv.utils.dict.dict_deep_update`.

.. code-block:: python

    from neuroconv.datainterfaces import SpikeGLXRecordingInterface
    from neuroconv.utils.dict import load_dict_from_file, dict_deep_update

    spikeglx_interface = SpikeGLXRecordingInterface(file_path="path/to/towersTask_g0_t0.imec0.ap.bin")

    metadata = spikeglx_interface.get_metadata()
    metadata_path = "my_lab_metadata.yml"
    metadata_from_yaml = load_dict_from_file(file_path=metadata_path)

    metadata = spikeglx_interface.get_metadata()
    metadata = dict_deep_update(metadata, metadata_from_yaml)

    spikeglx_interface.run_conversion(
        save_path="path/to/destination.nwb",
        metadata=metadata
    )

Note that any metadata extracted in by ``spikeglx_interface.get_metadata()`` will be overwritten by the YAML data.

The above YAML is common to all :py:class:`.BaseDataInterface`, :py:class:`~neuroconv.nwbconverter.NWBConverter`,
or :py:class:`~neuroconv.nwbconverter.ConverterPipe`, and an analogous workflow for incorporating this data will work
for each. Specific interfaces and converter will have additional fields, which you can see using the method
:func:`DataInterface.get_metadata_schema() <neuroconv.basedatainterface.BaseDataInterface.get_metadata_schema>` or
:func:`NWBConverter.get_metadata_schema() <neuroconv.nwbconverter.NWBConverter.get_metadata_schema>` or
