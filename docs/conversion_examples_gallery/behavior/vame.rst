VAME data conversion
--------------------

Install NeuroConv with the additional dependencies necessary for reading VAME data.

.. code-block:: bash

    pip install "neuroconv[vame]"

Convert `VAME <https://github.com/LINCellularNeuroscience/VAME>`_ behavioral segmentation
outputs to NWB using
:py:class:`~neuroconv.datainterfaces.behavior.vame.vamedatainterface.VameInterface`.
The interface reads per-session ``.npy`` output files—motif labels, optionally latent-space
vectors and community labels—and writes them to NWB using the
`ndx-vame <https://github.com/catalystneuro/ndx-vame>`_ NWB extension.

A typical VAME project has the following output layout for each session::

    <project>/
    ├── config.yaml
    └── results/
        └── <session_name>/
            └── VAME/
                ├── latent_vectors.npy              # (n_frames, zdims) float32
                ├── hmm-15/
                │   ├── 15_hmm_label_<session>.npy
                │   └── community/
                │       └── cohort_community_label_<session>.npy
                └── kmeans-15/
                    ├── 15_kmeans_label_<session>.npy
                    └── community/
                        └── cohort_community_label_<session>.npy


Minimal conversion (motif labels only)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import VameInterface

    >>> motif_labels_file_path = Path(
    ...     "/path/to/project/results/session/VAME/kmeans-15/15_kmeans_label_session.npy"
    ... )

    >>> interface = VameInterface(
    ...     motif_labels_file_path=motif_labels_file_path,
    ...     sampling_frequency_hz=30.0,   # video frame rate in Hz
    ... )

    >>> metadata = interface.get_metadata()
    >>> metadata["NWBFile"].update(
    ...     session_start_time=datetime(2024, 1, 1, 12, 0, 0, tzinfo=ZoneInfo("US/Pacific")),
    ...     session_description="Open-field behavioral recording segmented with VAME.",
    ... )
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P90D")
    >>> interface.run_conversion(nwbfile_path="/path/to/output.nwb", metadata=metadata)


Full conversion (latent vectors + community labels + config)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import VameInterface

    >>> project = Path("/path/to/my_vame_project")
    >>> session = "session_name"
    >>> algorithm = "kmeans"
    >>> n_clusters = 15

    >>> interface = VameInterface(
    ...     motif_labels_file_path=project / "results" / session / "VAME" / f"{algorithm}-{n_clusters}" / f"{n_clusters}_{algorithm}_label_{session}.npy",
    ...     latent_vectors_file_path=project / "results" / session / "VAME" / "latent_vectors.npy",
    ...     community_labels_file_path=project / "results" / session / "VAME" / f"{algorithm}-{n_clusters}" / "community" / f"cohort_community_label_{session}.npy",
    ...     vame_config_file_path=project / "config.yaml",
    ...     sampling_frequency_hz=30.0,
    ...     verbose=False,
    ... )

    >>> metadata = interface.get_metadata()
    >>> metadata["NWBFile"].update(
    ...     session_start_time=datetime(2024, 1, 1, 12, 0, 0, tzinfo=ZoneInfo("US/Pacific")),
    ...     session_description="Open-field behavioral recording segmented with VAME.",
    ... )
    >>> interface.run_conversion(nwbfile_path="/path/to/output.nwb", metadata=metadata)


Specifying Metadata
~~~~~~~~~~~~~~~~~~~

VAME metadata lives under ``metadata["VAME"][vame_project_metadata_key]``, where
``vame_project_metadata_key`` defaults to ``"VAMEProject"`` and matches the name of the
``VAMEProject`` group written to the NWB file.

Call :py:meth:`~neuroconv.datainterfaces.behavior.vame.vamedatainterface.VameInterface.get_metadata`
to retrieve the auto-populated defaults, then edit specific fields before conversion:

.. code-block:: python

    >>> metadata = interface.get_metadata()
    >>> metadata["VAME"]["VAMEProject"]["name"] = "VAMEKmeans15"
    >>> metadata["VAME"]["VAMEProject"]["MotifSeries"]["description"] = (
    ...     "k-means motif labels (15 clusters) for the open-field test session."
    ... )
    >>> interface.run_conversion(nwbfile_path="/path/to/output.nwb", metadata=metadata)

The same information can be provided as a YAML file and loaded with
:py:func:`~neuroconv.utils.load_dict_from_file`:

.. code-block:: yaml

    VAME:
      VAMEProject:
        name: VAMEKmeans15
        MotifSeries:
          name: MotifSeries
          description: "k-means motif labels (15 clusters) for the open-field test session."
          algorithm: kmeans
        LatentSpaceSeries:
          name: LatentSpaceSeries
          description: "VAME latent-space embeddings (30 dimensions per frame)."
        CommunitySeries:
          name: CommunitySeries
          description: "Community labels grouping kmeans motifs into higher-level behavioral states."
          algorithm: kmeans

.. code-block:: python

    >>> from neuroconv.utils import load_dict_from_file, dict_deep_update
    >>> file_metadata = load_dict_from_file("/path/to/metadata.yaml")
    >>> metadata = dict_deep_update(interface.get_metadata(), file_metadata)
    >>> interface.run_conversion(nwbfile_path="/path/to/output.nwb", metadata=metadata)


Temporal alignment
~~~~~~~~~~~~~~~~~~

When the VAME outputs need to be aligned to another data stream, use
:py:meth:`~neuroconv.datainterfaces.behavior.vame.vamedatainterface.VameInterface.set_aligned_timestamps`
instead of ``sampling_frequency_hz``:

.. code-block:: python

    >>> interface = VameInterface(motif_labels_file_path=motif_labels_file_path)
    >>> interface.set_aligned_timestamps(aligned_timestamps)  # seconds, aligned to session start
    >>> interface.run_conversion(nwbfile_path="/path/to/output.nwb", metadata=metadata)


Linking to pose estimation
~~~~~~~~~~~~~~~~~~~~~~~~~~

To record the upstream pose data used by VAME, pass the name of an existing
``PoseEstimation`` container to ``pose_estimation_name``. The container must already be
present in the NWB file when ``add_to_nwbfile`` is called—typically written by a preceding
:py:class:`~neuroconv.datainterfaces.behavior.deeplabcut.deeplabcutdatainterface.DeepLabCutInterface`
or :py:class:`~neuroconv.datainterfaces.behavior.sleap.sleapdatainterface.SLEAPInterface`.

.. code-block:: python

    >>> from neuroconv import NWBConverter
    >>> from neuroconv.datainterfaces import DeepLabCutInterface

    >>> class PoseAndVameConverter(NWBConverter):
    ...     data_interface_classes = dict(
    ...         DLC=DeepLabCutInterface,
    ...         VAME=VameInterface,
    ...     )

    >>> converter = PoseAndVameConverter(
    ...     source_data=dict(
    ...         DLC=dict(file_path="/path/to/dlc_output.h5"),
    ...         VAME=dict(
    ...             motif_labels_file_path=str(motif_labels_file_path),
    ...             sampling_frequency_hz=30.0,
    ...             pose_estimation_name="PoseEstimationDeepLabCut",
    ...         ),
    ...     )
    ... )
    >>> converter.run_conversion(nwbfile_path="/path/to/output.nwb", metadata=converter.get_metadata())


Multiple VAME runs in one file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use ``vame_project_metadata_key`` to store results from multiple algorithms or parameter
sets in the same NWB file. Each instance gets its own metadata entry and its own
``VAMEProject`` group:

.. code-block:: python

    >>> from neuroconv import NWBConverter

    >>> class MyConverter(NWBConverter):
    ...     data_interface_classes = dict(
    ...         VameKmeans=VameInterface,
    ...         VameHmm=VameInterface,
    ...     )

    >>> converter = MyConverter(
    ...     source_data=dict(
    ...         VameKmeans=dict(
    ...             motif_labels_file_path=str(kmeans_motif_path),
    ...             sampling_frequency_hz=30.0,
    ...             vame_project_metadata_key="VAMEKmeans15",
    ...         ),
    ...         VameHmm=dict(
    ...             motif_labels_file_path=str(hmm_motif_path),
    ...             sampling_frequency_hz=30.0,
    ...             vame_project_metadata_key="VAMEHmm15",
    ...         ),
    ...     )
    ... )

The metadata YAML for this multi-run converter looks like:

.. code-block:: yaml

    VAME:
      VAMEKmeans15:
        name: VAMEKmeans15
        MotifSeries:
          name: MotifSeries
          description: "k-means motif labels (15 clusters)."
          algorithm: kmeans
      VAMEHmm15:
        name: VAMEHmm15
        MotifSeries:
          name: MotifSeries
          description: "HMM motif labels (15 states)."
          algorithm: hmm

.. code-block:: python

    >>> metadata = converter.get_metadata()
    >>> converter.run_conversion(
    ...     nwbfile_path="/path/to/output.nwb",
    ...     metadata=metadata,
    ... )
