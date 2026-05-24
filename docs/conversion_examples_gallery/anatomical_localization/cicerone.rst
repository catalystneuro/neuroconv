MonkeyCicerone session conversion
---------------------------------

Install NeuroConv with the additional dependencies necessary for reading MonkeyCicerone session files.

.. code-block:: bash

    pip install "neuroconv[cicerone]"

Convert MonkeyCicerone recording-session data to NWB using
:py:class:`~neuroconv.datainterfaces.anatomical_localization.cicerone.ciceronesessioninterface.CiceroneSessionInterface`.
The interface reads two paired text files from one Cicerone recording session, joins each saved recording site to its
chamber's stereotaxic pose, and writes one electrode row per site plus two coordinate-frame tables into NWB via the
ndx-anatomical-localization extension.

What you need
~~~~~~~~~~~~~

Two text files, both required:

- **Configuration file** (``*_Configuration_*.txt``, ~6 KB). Holds the chamber poses (translation, dial rotations,
  plane), the chamber types, and the current microdrive settings.
- **Sites file** (``Cicerone_Sites_<date>.txt`` or the bundled ``Cicerone_sample_MER.txt``). One row per recording
  site, with microdrive ``AP``, ``ML``, ``Depth``, calibration, anatomical-region label, clinical-observation
  columns, and a pointer to the associated neural-recording file.

No DICOM volumes, no STL meshes, no auxiliary files are read.

Basic usage
~~~~~~~~~~~

The default writes one electrode row per recording site in the sites file (every row).

.. code-block:: python

    from datetime import datetime
    from zoneinfo import ZoneInfo
    from neuroconv.datainterfaces import CiceroneSessionInterface

    interface = CiceroneSessionInterface(
        file_path="path/to/Monkey1_Configuration.txt",
        sites_file_path="path/to/Cicerone_Sites_2024-11-24.txt",
    )

    metadata = interface.get_metadata()
    session_start_time = datetime(2024, 11, 24, 0, 0, 0, tzinfo=ZoneInfo("US/Pacific"))
    metadata["NWBFile"].update(session_start_time=session_start_time)
    # Subject identity comes from the configuration's MonkeyID / MonkeyName automatically.
    # NWB requires species and sex:
    metadata["Subject"]["species"] = "Macaca mulatta"
    metadata["Subject"]["sex"] = "U"

    interface.run_conversion(nwbfile_path="Monkey1_session.nwb", metadata=metadata)

The resulting NWB file has:

- A ``Device`` per chamber declared in the configuration (e.g., ``CiceroneChamber1``) carrying the chamber type,
  electrode type, physical angle, and plane.
- An ``ElectrodeGroup`` linking to each Device.
- One row per recording site on ``nwbfile.electrodes`` carrying chamber-level columns (``cicerone_chamber_index``,
  ``cicerone_eltrans_ml`` / ``_depth`` / ``_ap``, ``cicerone_calibration_mm``, ``cicerone_chamber_plane``) plus
  site-level annotation columns (``cicerone_site_number``, ``cicerone_track_number``, ``cicerone_electrode_number``,
  ``cicerone_location``, ``cicerone_site_comment``, ``cicerone_motor_response``, ``cicerone_microstim_response``,
  ``cicerone_record_file``, ``cicerone_date``, ``cicerone_track_comment``).
- A ``Localization`` container at ``nwbfile.lab_meta_data['localization']`` with two ``Space`` objects (``NMTv2`` in
  RAS and ``CiceroneStereoHf0`` in LSA) and two parallel ``AnatomicalCoordinatesTable`` instances, one row per site
  in each table.

Filtering to a subset of sites
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A single Cicerone sites file can accumulate sites across many recording sessions. Filter to the sites that belong in
one NWB file by passing two paired keyword-only arguments: ``track_numbers`` and ``site_numbers``. Element-by-element,
the pair ``(track_numbers[i], site_numbers[i])`` identifies one site row. SiteNumber resets per track in Cicerone, so
the pair is the row-unique key.

.. code-block:: python

    import pandas as pd

    # Pre-compute the (track, site) lists with whatever lab-specific criterion you like.
    df = pd.read_csv("path/to/Cicerone_Sites_2024-11-24.txt", sep="\t")
    selection = df.query("Date == '11/24/2024' and TrackNumber == 2")

    interface = CiceroneSessionInterface(
        file_path="path/to/Monkey1_Configuration.txt",
        sites_file_path="path/to/Cicerone_Sites_2024-11-24.txt",
        track_numbers=selection["TrackNumber"].tolist(),
        site_numbers=selection["SiteNumber"].tolist(),
    )

    interface.run_conversion(nwbfile_path="Monkey1_session_track2.nwb", metadata=metadata)

Validation is strict and fails fast:

- ``track_numbers`` and ``site_numbers`` must both be provided (or both omitted to include every site).
- They must have the same length.
- Each ``(track_numbers[i], site_numbers[i])`` pair must correspond to a row that exists in the sites file. Missing
  combinations raise immediately with the actual SiteNumbers available in that TrackNumber.
- Every selected site's ``Chamber`` must correspond to a chamber defined in the configuration file. Mismatches raise.

Coordinate frames
~~~~~~~~~~~~~~~~~

The interface writes the same physical points in two coordinate frames, one per ``AnatomicalCoordinatesTable``:

- **NMT v2 RAS** (``NMTv2Coordinates`` linked to ``NMTv2Space``, orientation RAS, mm, ear-bar-zero origin). The
  canonical macaque atlas frame.
- **Cicerone-native stereoHf0** (``CiceroneStereoHf0Coordinates`` linked to a ``Space`` with orientation LSA,
  ``+x = Left``, ``+y = Superior/Dorsal``, ``+z = Anterior``). The frame the original session file uses, preserved
  for archival fidelity.

Both tables' ``localized_entity`` column references the same rows in ``nwbfile.electrodes``, so a consumer can join
either table back to the chamber metadata.

Verification status
~~~~~~~~~~~~~~~~~~~

The rotation composer's ``rx`` sign convention was verified visually against the live MonkeyCicerone GUI on
2026-05-18 (positive ``rx`` tilts the chamber posterior with ``plane = 0``). Other dial signs share the same
right-hand-rule construction as ``rx`` and were validated via six synthetic-input experiments. Direct numerical
equivalence to Cicerone's renderer is not testable: Cicerone exposes no composed coordinate in any GUI panel or
output file, and ships application code as opaque TclPro bytecode. Each ``AnatomicalCoordinatesTable``'s ``method``
attribute carries this verification record verbatim, so consumers reading the produced NWB can see what was checked.
