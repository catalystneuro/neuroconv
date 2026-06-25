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



Full conversion (auto-discover all runs from config)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pass ``session_name`` and the interface discovers all motif labels, latent vectors, and
community labels from the standard VAME results layout under the config file's parent
directory. Algorithms and ``n_clusters`` are read directly from ``config.yaml``, so both
``kmeans`` and ``hmm`` runs end up in one ``VAMEProject`` group automatically.

When a key in ``community_labels_file_paths`` matches a key in ``motif_labels_file_paths``,
``get_metadata`` automatically sets ``motif_series_key`` so each ``CommunitySeries`` is
linked to its corresponding ``MotifSeries``. No extra metadata wiring is needed.

Use :py:meth:`~neuroconv.datainterfaces.behavior.vame.vamedatainterface.VameInterface.get_available_sessions`
to list the session names recorded in ``config.yaml``.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import VameInterface

    >>> project = BEHAVIOR_DATA_PATH / "vame" / "my_vame_project"

    >>> # Discover available session names from config.yaml
    >>> sessions = VameInterface.get_available_sessions(project / "config.yaml")
    >>> session = sessions[0]

    >>> interface = VameInterface(
    ...     file_path=project / "config.yaml",
    ...     session_name=session,
    ...     sampling_frequency_hz=30.0,
    ... )

    >>> metadata = interface.get_metadata()
    >>> metadata["NWBFile"].update(
    ...     session_start_time=datetime(2024, 1, 1, 12, 0, 0, tzinfo=ZoneInfo("US/Pacific")),
    ...     session_description="Open-field behavioral recording segmented with VAME.",
    ... )
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata)

Explicit file paths take precedence over auto-discovered ones, so you can override
individual paths while still relying on auto-discovery for the rest:

.. code-block:: python

    >>> interface = VameInterface(
    ...     file_path=project / "config.yaml",
    ...     session_name=session,
    ...     # override just the kmeans community labels; everything else is auto-discovered
    ...     community_labels_file_paths={
    ...         "kmeans": project / "results" / session / "VAME" / "kmeans-15" / "community" / f"cohort_community_label_{session}.npy",
    ...     },
    ...     sampling_frequency_hz=30.0,
    ... )


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
    >>> metadata["NWBFile"].update(
    ...     session_start_time=datetime(2024, 1, 1, 12, 0, 0, tzinfo=ZoneInfo("US/Pacific")),
    ...     session_description="Open-field behavioral recording segmented with VAME.",
    ... )
    >>> metadata["Behavior"]["VAMEProjects"]["VAMEProject"]["name"] = "VAMEKmeans15"
    >>> metadata["Behavior"]["VAMEProjects"]["VAMEProject"]["MotifSeries"]["kmeans"]["description"] = (
    ...     "k-means motif labels (15 clusters) for the open-field test session."
    ... )
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata, overwrite=True)


Temporal alignment
~~~~~~~~~~~~~~~~~~

When the VAME outputs need to be aligned to another data stream, use
:py:meth:`~neuroconv.datainterfaces.behavior.vame.vamedatainterface.VameInterface.set_aligned_timestamps`
instead of ``sampling_frequency_hz``:

.. code-block:: python

    >>> import numpy as np
    >>> motif_labels_file_path = project / "results" / session / "VAME" / "kmeans-15" / f"15_kmeans_label_{session}.npy"
    >>> aligned_timestamps = np.arange(len(np.load(motif_labels_file_path))) / 30.0
    >>> interface = VameInterface(
    ...     file_path=project / "config.yaml",
    ...     motif_labels_file_paths={"kmeans": motif_labels_file_path},
    ... )
    >>> interface.set_aligned_timestamps(aligned_timestamps)
    >>> metadata = interface.get_metadata()
    >>> metadata["NWBFile"].update(
    ...     session_start_time=datetime(2024, 1, 1, 12, 0, 0, tzinfo=ZoneInfo("US/Pacific")),
    ...     session_description="Open-field behavioral recording segmented with VAME.",
    ... )
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata, overwrite=True)


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

    >>> converter = PoseAndVameConverter(  # doctest: +SKIP
    ...     source_data=dict(
    ...         DLC=dict(file_path="/path/to/dlc_output.h5"),
    ...         VAME=dict(
    ...             file_path=str(project / "config.yaml"),
    ...             motif_labels_file_paths={"kmeans": str(motif_labels_file_path)},
    ...             sampling_frequency_hz=30.0,
    ...         ),
    ...     )
    ... )
    >>> metadata = converter.get_metadata()  # doctest: +SKIP
    >>> metadata["Behavior"]["VAMEProjects"]["VAMEProject"]["pose_estimation_metadata_key"] = (  # doctest: +SKIP
    ...     "PoseEstimationDeepLabCut"
    ... )
    >>> converter.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata)  # doctest: +SKIP


Multiple VAME projects in one file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use ``metadata_key`` to store results from multiple VAME projects in the same NWB file.
Each instance gets its own metadata entry and its own ``VAMEProject`` group:

.. code-block:: python

    >>> hmm_labels_file_path = project / "results" / session / "VAME" / "hmm-15" / f"15_hmm_label_{session}.npy"
    >>> class MyConverter(NWBConverter):
    ...     data_interface_classes = dict(
    ...         VameKmeans=VameInterface,
    ...         VameHmm=VameInterface,
    ...     )

    >>> converter = MyConverter(
    ...     source_data=dict(
    ...         VameKmeans=dict(
    ...             file_path=str(project / "config.yaml"),
    ...             motif_labels_file_paths={"kmeans": str(motif_labels_file_path)},
    ...             sampling_frequency_hz=30.0,
    ...             metadata_key="VAMEProjectA",
    ...         ),
    ...         VameHmm=dict(
    ...             file_path=str(project / "config.yaml"),
    ...             motif_labels_file_paths={"hmm": str(hmm_labels_file_path)},
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
    >>> metadata["NWBFile"].update(
    ...     session_start_time=datetime(2024, 1, 1, 12, 0, 0, tzinfo=ZoneInfo("US/Pacific")),
    ...     session_description="Multi-project VAME behavioral segmentation.",
    ... )
    >>> converter.run_conversion(
    ...     nwbfile_path=path_to_save_nwbfile,
    ...     metadata=metadata,
    ...     overwrite=True,
    ... )
