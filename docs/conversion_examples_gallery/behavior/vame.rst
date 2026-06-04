VAME data conversion
--------------------

Install NeuroConv with the additional dependencies necessary for reading VAME data.

.. code-block:: bash

    pip install "neuroconv[vame]"

Convert `VAME <https://github.com/LINCellularNeuroscience/VAME>`_ behavioral segmentation
outputs to NWB using
:py:class:`~neuroconv.datainterfaces.behavior.vame.vamedatainterface.VameInterface`.
The interface reads per-session ``.npy`` output files—motif labels, latent-space
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



Full conversion (multiple algorithm runs in one VAMEProject)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Both ``kmeans`` and ``hmm`` runs belong to the same VAME project and share the same latent
vectors. Pass all runs together in a single ``VameInterface`` so they end up in one
``VAMEProject`` group in the NWB file.

When a key in ``community_labels_file_paths`` matches a key in ``motif_labels_file_paths``,
``get_metadata`` automatically sets ``motif_series_key`` so each ``CommunitySeries`` is
linked to its corresponding ``MotifSeries``. No extra metadata wiring is needed.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import VameInterface

    >>> project = Path("/path/to/my_vame_project")
    >>> session = "session_name"
    >>> n_clusters = 15
    >>> vame_dir = project / "results" / session / "VAME"

    >>> interface = VameInterface(
    ...     file_path=project / "config.yaml",
    ...     motif_labels_file_paths={
    ...         "kmeans": vame_dir / f"kmeans-{n_clusters}" / f"{n_clusters}_kmeans_label_{session}.npy",
    ...         "hmm": vame_dir / f"hmm-{n_clusters}" / f"{n_clusters}_hmm_label_{session}.npy",
    ...     },
    ...     latent_vectors_file_path=vame_dir / "latent_vectors.npy",
    ...     community_labels_file_paths={
    ...         "kmeans": vame_dir / f"kmeans-{n_clusters}" / "community" / f"cohort_community_label_{session}.npy",
    ...         "hmm": vame_dir / f"hmm-{n_clusters}" / "community" / f"cohort_community_label_{session}.npy",
    ...     },
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

VAME metadata lives under ``metadata["Behavior"]["VAMEProjects"][metadata_key]``, where
``metadata_key`` defaults to ``"VAMEProject"`` and matches the name of the
``VAMEProject`` group written to the NWB file.

``MotifSeries`` and ``CommunitySeries`` are dicts keyed by the run name (the same key used
in ``motif_labels_file_paths`` / ``community_labels_file_paths``).

Call :py:meth:`~neuroconv.datainterfaces.behavior.vame.vamedatainterface.VameInterface.get_metadata`
to retrieve the auto-populated defaults, then edit specific fields before conversion:

.. code-block:: python

    >>> metadata = interface.get_metadata()
    >>> metadata["Behavior"]["VAMEProjects"]["VAMEProject"]["name"] = "VAMEKmeans15"
    >>> metadata["Behavior"]["VAMEProjects"]["VAMEProject"]["MotifSeries"]["kmeans"]["description"] = (
    ...     "k-means motif labels (15 clusters) for the open-field test session."
    ... )
    >>> interface.run_conversion(nwbfile_path="/path/to/output.nwb", metadata=metadata)

The same information can be provided as a YAML file and loaded with
:py:func:`~neuroconv.utils.load_dict_from_file`:

.. code-block:: yaml

    Behavior:
      VAMEProjects:
        VAMEProject:
          name: VAMEKmeans15
          MotifSeries:
            kmeans:
              name: MotifSeriesKmeans
              description: "k-means motif labels (15 clusters) for the open-field test session."
              algorithm: kmeans
          LatentSpaceSeries:
            name: LatentSpaceSeries
            description: "VAME latent-space embeddings (30 dimensions per frame)."
          CommunitySeries:
            kmeans:
              name: CommunitySeriesKmeans
              description: "Community labels grouping kmeans motifs into higher-level behavioral states."
              motif_series_key: kmeans

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

    >>> interface = VameInterface(
    ...     file_path=project / "config.yaml",
    ...     motif_labels_file_paths={"kmeans": motif_labels_file_path},
    ... )
    >>> interface.set_aligned_timestamps(aligned_timestamps)  # seconds, aligned to session start
    >>> interface.run_conversion(nwbfile_path="/path/to/output.nwb", metadata=metadata)


Linking to pose estimation
~~~~~~~~~~~~~~~~~~~~~~~~~~

To record the upstream pose data used by VAME, set ``pose_estimation_metadata_key`` in the
metadata to the name of an existing ``PoseEstimation`` container. The container must already
be present in the NWB file when ``add_to_nwbfile`` is called—typically written by a preceding
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
    ...             file_path=str(project / "config.yaml"),
    ...             motif_labels_file_paths={"kmeans": str(motif_labels_file_path)},
    ...             sampling_frequency_hz=30.0,
    ...         ),
    ...     )
    ... )
    >>> metadata = converter.get_metadata()
    >>> metadata["Behavior"]["VAMEProjects"]["VAMEProject"]["pose_estimation_metadata_key"] = (
    ...     "PoseEstimationDeepLabCut"
    ... )
    >>> converter.run_conversion(nwbfile_path="/path/to/output.nwb", metadata=metadata)


Multiple VAME projects in one file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use ``metadata_key`` to store results from multiple VAME projects in the same NWB file.
Each instance gets its own metadata entry and its own ``VAMEProject`` group:

.. code-block:: python

    >>> from neuroconv import NWBConverter

    >>> class MyConverter(NWBConverter):
    ...     data_interface_classes = dict(
    ...         VameKmeans=VameInterface,
    ...         VameHmm=VameInterface,
    ...     )

    >>> converter = MyConverter(
    ...     source_data=dict(
    ...         VAMEProjectA=dict(
    ...             file_path=str(project_A / "config.yaml"),
    ...             motif_labels_file_paths={"kmeans": str(kmeans_motif_path)},
    ...             sampling_frequency_hz=30.0,
    ...             metadata_key="VAMEProjectA",
    ...         ),
    ...         VAMEProjectB=dict(
    ...             file_path=str(project_B / "config.yaml"),
    ...             motif_labels_file_paths={"hmm": str(hmm_motif_path)},
    ...             sampling_frequency_hz=30.0,
    ...             metadata_key="VAMEProjectB",
    ...         ),
    ...     )
    ... )

The metadata YAML for this multi-run converter looks like:

.. code-block:: yaml

    Behavior:
      VAMEProjects:
        VAMEProjectA:
          name: VAMEProjectA
          MotifSeries:
            kmeans:
              name: MotifSeriesKmeans
              description: "k-means motif labels (15 clusters)."
              algorithm: kmeans
        VAMEProjectB:
          name: VAMEProjectB
          MotifSeries:
            hmm:
              name: MotifSeriesHmm
              description: "HMM motif labels (15 states)."
              algorithm: hmm

.. code-block:: python

    >>> metadata = converter.get_metadata()
    >>> converter.run_conversion(
    ...     nwbfile_path="/path/to/output.nwb",
    ...     metadata=metadata,
    ... )
