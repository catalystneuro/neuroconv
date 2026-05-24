"""NeuroConv DataInterface for MonkeyCicerone session files.

Reads two paired text files from a Cicerone recording session:

- The **configuration file** (``*_Configuration_*.txt``), describing the
  chambers' stereotaxic poses and dial rotations.
- The **sites file** (``Cicerone_Sites_<date>.txt`` or the bundled
  ``Cicerone_sample_MER.txt``), describing each saved recording site's
  chamber-local microdrive coordinates plus its clinical annotations
  (anatomical region label, motor / microstim response, comments, recording
  filename).

For each site row, the interface composes the stereotaxic position by
applying the matching chamber's pose (from the configuration) to the site's
microdrive coordinates (from the sites file). The resulting NWB carries:

- One ``Device`` per chamber, holding chamber-type metadata.
- One ``ElectrodeGroup`` per chamber, referencing the chamber Device.
- One row per filtered recording site on ``nwbfile.electrodes``, with
  chamber-relative microdrive parameters and the full set of site
  annotations as ``cicerone_*`` custom columns.
- One ``Localization`` container in ``nwbfile.lab_meta_data['localization']``,
  wrapping two ``Space`` objects and two parallel ``AnatomicalCoordinatesTable``
  instances, one per coordinate frame:

  * ``NMTv2Coordinates`` linked to ``NMTv2Space`` (RAS, ``+x = Right``). Each
    row's ``x, y, z`` is the composed stereotaxic target in NMT v2 RAS, in mm.
  * ``CiceroneStereoHf0Coordinates`` linked to ``CiceroneStereoHf0`` (LSA,
    ``+x = Left``, ``+y = Superior/Dorsal``, ``+z = Anterior``). Each row's
    ``x, y, z`` is the same physical point expressed in Cicerone's native frame.

  Both tables' ``localized_entity`` columns reference the same rows in
  ``nwbfile.electrodes``; consumers can join either table back to the chamber
  metadata.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import FilePath, validate_call
from pynwb import NWBFile
from pynwb.device import Device
from pynwb.ecephys import ElectrodeGroup

from .cicerone_geometry import compose_site_target
from .cicerone_session_parser import CiceroneSession, parse_session_file
from .cicerone_sites_parser import SiteRecord, parse_sites_file
from ....basedatainterface import BaseDataInterface
from ....utils import DeepDict


class CiceroneSessionInterface(BaseDataInterface):
    """Writes a MonkeyCicerone stereotaxic-planning session into NWB.

    Composition verified against the live Cicerone GUI on 2026-05-18: the
    ``rx`` (vertical dial) sign convention agrees with Cicerone in the
    ``plane = 0`` case. Other dial signs share the same right-hand-rule
    construction as ``rx`` and were validated via six synthetic-input
    experiments (see ``cicerone_geometry.py`` module docstring). Cicerone
    exposes no composed stereotaxic coordinate in any GUI panel or output
    file, so direct numerical equivalence to Cicerone's renderer cannot be
    tested. Users requiring sub-mm precision should still cross-check against
    their own reference targets.
    """

    display_name = "MonkeyCicerone session"
    keywords = (
        "stereotaxy",
        "neurosurgical planning",
        "non-human primate",
        "anatomical localization",
    )
    associated_suffixes = (".txt",)
    info = "Interface for MonkeyCicerone v1.0 stereotaxic planning session files."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"][
            "description"
        ] = "Path to the Cicerone configuration text file (typically *_Configuration_*.txt)."
        return source_schema

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        sites_file_path: FilePath,
        *,
        track_numbers: list[int] | None = None,
        site_numbers: list[int] | None = None,
        verbose: bool = False,
    ):
        """
        Parameters
        ----------
        file_path : FilePath
            Path to the Cicerone configuration text file
            (``*_Configuration_*.txt``). Chamber poses and the rotation
            composition come from this file.
        sites_file_path : FilePath
            Path to a Cicerone sites file
            (``Cicerone_Sites_<date>.txt`` or the bundled
            ``Cicerone_sample_MER.txt``). One electrode row is written per
            selected site, joined to the chamber pose in ``file_path``.
        track_numbers : list of int, optional, keyword-only
            Values of the sites file's ``TrackNumber`` column to keep, paired
            element-by-element with ``site_numbers``. The combination
            ``(track_numbers[i], site_numbers[i])`` identifies one site row.
            ``TrackNumber`` resets per track in Cicerone, so a SiteNumber
            alone is not unique; the pair always is.
        site_numbers : list of int, optional, keyword-only
            Values of the sites file's ``SiteNumber`` column to keep, paired
            element-by-element with ``track_numbers``. Must be the same
            length as ``track_numbers``; both must be supplied together (or
            neither, to include every site in the sites file).
        verbose : bool, default: False
            Whether to print progress.

        Notes
        -----
        ``track_numbers`` and ``site_numbers`` are keyword-only and form a
        unit. If you pass one without the other, or pass them with mismatched
        lengths, the interface raises with a precise error message naming
        both columns by their Cicerone-file names (``TrackNumber``,
        ``SiteNumber``).
        """
        self.file_path = Path(file_path)
        self.sites_file_path = Path(sites_file_path)
        self.verbose = verbose
        self._session: CiceroneSession = parse_session_file(self.file_path)

        all_sites = parse_sites_file(self.sites_file_path)
        self._selected_sites = self._filter_and_validate_sites(
            all_sites, track_numbers=track_numbers, site_numbers=site_numbers
        )

        super().__init__(file_path=str(self.file_path))

    def _filter_and_validate_sites(
        self,
        all_sites: list[SiteRecord],
        *,
        track_numbers: list[int] | None,
        site_numbers: list[int] | None,
    ) -> list[SiteRecord]:
        """Apply the (TrackNumber, SiteNumber) selection and validate against
        both the sites file and the configuration's chambers.

        - Both ``None`` → keep every site (no filter).
        - Exactly one provided → ``ValueError`` naming the missing parameter.
        - Same length required when both provided; mismatch → ``ValueError``
          stating the two lengths.
        - Both empty → ``ValueError`` (user probably did not mean to write
          zero sites).
        - Each ``(track_numbers[i], site_numbers[i])`` pair must correspond
          to a row in ``all_sites``; missing pairs → ``ValueError`` with the
          exact tuple.
        - Every selected site's chamber must exist in the configuration
          (raises ``ValueError`` otherwise; the composer cannot work without
          a chamber pose).
        """
        chamber_indices = {chamber.index for chamber in self._session.chambers}

        if track_numbers is None and site_numbers is None:
            chosen = list(all_sites)
        else:
            if track_numbers is None:
                raise ValueError(
                    "site_numbers was provided but track_numbers was not. "
                    "Both must be supplied together (paired element-by-element) "
                    "because SiteNumber resets per track in Cicerone sites files; "
                    "a SiteNumber alone does not uniquely identify a row."
                )
            if site_numbers is None:
                raise ValueError(
                    "track_numbers was provided but site_numbers was not. "
                    "Both must be supplied together (paired element-by-element)."
                )
            if len(track_numbers) != len(site_numbers):
                raise ValueError(
                    f"track_numbers and site_numbers must have the same length; "
                    f"got {len(track_numbers)} and {len(site_numbers)}."
                )
            if not track_numbers:
                raise ValueError(
                    "track_numbers and site_numbers are both empty. Pass them as "
                    "None (or omit them entirely) to include every site, or omit "
                    "sites_file_path to fall back to chamber-level output."
                )

            by_key = {(site.track_number, site.site_number): site for site in all_sites}
            chosen = []
            for track, site_id in zip(track_numbers, site_numbers):
                key = (track, site_id)
                if key not in by_key:
                    raise ValueError(
                        f"No site with TrackNumber={track}, SiteNumber={site_id} in "
                        f"{self.sites_file_path}. Available SiteNumbers in TrackNumber={track}: "
                        f"{sorted(s.site_number for s in all_sites if s.track_number == track) or 'none (track does not exist)'}."
                    )
                chosen.append(by_key[key])

        for site in chosen:
            if site.chamber not in chamber_indices:
                raise ValueError(
                    f"Site (TrackNumber={site.track_number}, SiteNumber={site.site_number}) "
                    f"references Chamber={site.chamber}, which is not defined in the "
                    f"configuration file {self.file_path}. Cannot compose stereotaxic target."
                )
        return chosen

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        if self._session.monkey_id:
            metadata["Subject"]["subject_id"] = self._session.monkey_id
        if self._session.monkey_name:
            existing = metadata["Subject"].get("description", "")
            description = f"MonkeyName: {self._session.monkey_name}"
            if existing:
                description = f"{existing}; {description}"
            metadata["Subject"]["description"] = description
        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
    ) -> None:
        """Add chamber Devices, one electrode row per selected site, and the
        ``Localization`` container with two coordinate-frame tables."""
        import ndx_anatomical_localization

        self._add_extra_electrode_columns(nwbfile)
        groups_by_chamber = self._add_chamber_devices_and_groups(nwbfile)
        electrode_indices = self._add_electrode_rows(nwbfile, groups_by_chamber)
        self._add_localization(nwbfile, ndx_anatomical_localization, electrode_indices)

    def _add_extra_electrode_columns(self, nwbfile: NWBFile) -> None:
        """Declare Cicerone-specific columns on ``nwbfile.electrodes``: the
        chamber-level columns (pose / microdrive parameters / calibration)
        plus the site-level annotation columns."""
        existing = nwbfile.electrodes.colnames if nwbfile.electrodes is not None else ()

        column_specs = [
            ("cicerone_chamber_index", "Cicerone chamber index (1, 2, or 3)."),
            ("cicerone_eltrans_ml", "Electrode ML microdrive coordinate in mm (Cicerone eltrans x)."),
            ("cicerone_eltrans_depth", "Electrode depth microdrive coordinate in mm (Cicerone eltrans y)."),
            ("cicerone_eltrans_ap", "Electrode AP microdrive coordinate in mm (Cicerone eltrans z)."),
            (
                "cicerone_calibration_mm",
                (
                    "Distance from electrode tip to top chamber rim at zero microdrive depth, "
                    "in mm. Positive if the tip is above the rim."
                ),
            ),
            ("cicerone_chamber_plane", "Cicerone chamber-orientation toggle (0=perpendicular, 1=parallel)."),
            ("cicerone_site_number", "Cicerone SiteNumber column (resets per track)."),
            ("cicerone_track_number", "Cicerone TrackNumber column (one trajectory per track)."),
            ("cicerone_electrode_number", "Cicerone ElectrodeNumber column (which electrode the site used)."),
            (
                "cicerone_location",
                "Cicerone Location column: anatomical region label assigned by the operator from "
                "the configuration's site_markers vocabulary (e.g., 'stn', 'gpi', 'other').",
            ),
            ("cicerone_site_comment", "Cicerone SiteComment column: freeform per-site annotation."),
            (
                "cicerone_motor_response",
                "Cicerone MotorResponse column: presence of motor response to passive or active limb movement.",
            ),
            (
                "cicerone_microstim_response",
                "Cicerone MicrostimResponse column: presence of response to microstimulation.",
            ),
            (
                "cicerone_record_file",
                "Cicerone RecordFile column: filename pointer to the associated neural recording, if any.",
            ),
            ("cicerone_date", "Cicerone Date column: date the site was saved by the operator."),
            ("cicerone_track_comment", "Cicerone TrackComment column: freeform per-track annotation."),
        ]
        for name, description in column_specs:
            if name not in existing:
                nwbfile.add_electrode_column(name=name, description=description)

    def _add_chamber_devices_and_groups(self, nwbfile: NWBFile) -> dict[int, ElectrodeGroup]:
        """Add one Device and one ElectrodeGroup per chamber.

        Returns a mapping from chamber index to its ElectrodeGroup, used by
        the row-writing helpers.
        """
        groups: dict[int, ElectrodeGroup] = {}
        for chamber in self._session.chambers:
            device = Device(
                name=f"CiceroneChamber{chamber.index}",
                description=(
                    f"MonkeyCicerone chamber {chamber.index}: type={chamber.chamber_type}, "
                    f"electrode={chamber.electrode_type}, physical angle={chamber.chamber_angle_deg} deg, "
                    f"plane={chamber.plane} ("
                    f"{'parallel' if chamber.plane == 1 else 'perpendicular'} to plane of rotation)."
                ),
            )
            nwbfile.add_device(device)

            group = ElectrodeGroup(
                name=f"ElectrodeGroupCiceroneChamber{chamber.index}",
                description=(
                    f"Electrode in MonkeyCicerone chamber {chamber.index}. "
                    f"Stereotaxic position derived from the configuration's chamber pose "
                    f"and the microdrive parameters of each row."
                ),
                location="Cicerone-planned stereotaxic target",
                device=device,
            )
            nwbfile.add_electrode_group(group)
            groups[chamber.index] = group
        return groups

    def _add_electrode_rows(
        self,
        nwbfile: NWBFile,
        groups_by_chamber: dict[int, ElectrodeGroup],
    ) -> list[int]:
        """One electrode row per filtered site, joining each site to its
        chamber's ElectrodeGroup. Returns a list of the assigned row indices
        in the order of ``self._selected_sites``."""
        chamber_by_index = {chamber.index: chamber for chamber in self._session.chambers}
        row_indices: list[int] = []
        for site in self._selected_sites:
            chamber = chamber_by_index[site.chamber]
            nwbfile.add_electrode(
                group=groups_by_chamber[site.chamber],
                location=(
                    f"Cicerone site (TrackNumber={site.track_number}, "
                    f"SiteNumber={site.site_number}, Chamber={site.chamber})"
                ),
                cicerone_chamber_index=site.chamber,
                cicerone_eltrans_ml=site.ml,
                cicerone_eltrans_depth=site.depth,
                cicerone_eltrans_ap=site.ap,
                cicerone_calibration_mm=site.electrode_calibr,
                cicerone_chamber_plane=chamber.plane,
                cicerone_site_number=site.site_number,
                cicerone_track_number=site.track_number,
                cicerone_electrode_number=site.electrode_number,
                cicerone_location=site.location,
                cicerone_site_comment=site.site_comment,
                cicerone_motor_response=site.motor_response,
                cicerone_microstim_response=site.microstim_response,
                cicerone_record_file=site.record_file,
                cicerone_date=site.date,
                cicerone_track_comment=site.track_comment,
            )
            row_indices.append(len(nwbfile.electrodes) - 1)
        return row_indices

    def _build_localization_skeleton(self, nwbfile: NWBFile, ndx_anatomical_localization):
        """Create the Localization container with both Spaces and both
        (empty) AnatomicalCoordinatesTables. Returns the two tables for the
        caller to populate row-by-row."""
        nmt_space = ndx_anatomical_localization.NMTv2Space(name="NMTv2")
        cicerone_space = ndx_anatomical_localization.Space(
            name="CiceroneStereoHf0",
            space_name="Cicerone stereoHf0",
            origin=(
                "Ear bar zero (EBZ): intersection of the midsagittal plane and the interaural "
                "line, with the horizontal plane aligned to the Horsley-Clarke stereotaxic "
                "convention. Identical origin and alignment to NMT v2; differs only in axis "
                "convention (Cicerone uses LSA: +x = Left, +y = Superior/Dorsal, +z = Anterior). "
                "Documented in the MonkeyCicerone v1.0 user manual, Panel F."
            ),
            units="mm",
            orientation="LSA",
        )
        localization = ndx_anatomical_localization.Localization(spaces=[nmt_space, cicerone_space])
        nwbfile.add_lab_meta_data(localization)

        method_description = (
            "Composed from MonkeyCicerone session-file fields (chtrans translation "
            "and dial rotations, eltrans microdrive coordinates, calibration depth, "
            "chtrans plane base orientation) by neuroconv's CiceroneSessionInterface. "
            "Field meanings were verified against the MonkeyCicerone v1.0 GUI on the "
            "loaded session. The rx (vertical dial) sign convention was verified by a "
            "controlled GUI sweep on 2026-05-18: +rx tilts the chamber posterior and "
            "-rx tilts it anterior in the plane=0 case, matching the right-hand-rule "
            "prediction implemented here. Other dial signs and the rotation-matrix "
            "order share the same construction and were validated via six "
            "synthetic-input experiments. Direct numerical equivalence to Cicerone's "
            "renderer is not testable (Cicerone exposes no composed coordinate)."
        )

        nmt_table = ndx_anatomical_localization.AnatomicalCoordinatesTable(
            name="NMTv2Coordinates",
            description=(
                "Composed stereotaxic targets for each MonkeyCicerone electrode, expressed "
                "in NMT v2 RAS (mm). Derived from the chamber pose and electrode microdrive "
                "parameters that live on the linked rows of nwbfile.electrodes. The same "
                "physical points expressed in Cicerone's native frame are in the parallel "
                "CiceroneStereoHf0Coordinates table. See CiceroneSessionInterface docstring "
                "for the verification status of the chamber rotation composition."
            ),
            space=nmt_space,
            method=method_description,
            target=nwbfile.electrodes,
        )
        cicerone_table = ndx_anatomical_localization.AnatomicalCoordinatesTable(
            name="CiceroneStereoHf0Coordinates",
            description=(
                "Composed stereotaxic targets for each MonkeyCicerone electrode, expressed "
                "in Cicerone's native stereoHf0 frame (LSA: +x = Left, +y = Superior/Dorsal, "
                "+z = Anterior; mm). Same physical points as the parallel NMTv2Coordinates "
                "table, only the axis convention differs (axis permutation plus one sign flip)."
            ),
            space=cicerone_space,
            method=method_description,
            target=nwbfile.electrodes,
        )
        localization.add_anatomical_coordinates_tables(nmt_table)
        localization.add_anatomical_coordinates_tables(cicerone_table)
        return nmt_table, cicerone_table

    def _add_localization(
        self,
        nwbfile: NWBFile,
        ndx_anatomical_localization,
        site_electrode_indices: list[int],
    ) -> None:
        """One row per filtered site, composing the chamber pose from the
        configuration with the site's microdrive coordinates."""
        nmt_table, cicerone_table = self._build_localization_skeleton(nwbfile, ndx_anatomical_localization)
        chamber_by_index = {chamber.index: chamber for chamber in self._session.chambers}
        for site, electrode_index in zip(self._selected_sites, site_electrode_indices):
            chamber = chamber_by_index[site.chamber]
            target = compose_site_target(chamber=chamber, site=site)
            nmt_table.add_row(
                x=target.ras_x,
                y=target.ras_y,
                z=target.ras_z,
                localized_entity=electrode_index,
            )
            cicerone_table.add_row(
                x=target.ml,
                y=target.vd,
                z=target.ap,
                localized_entity=electrode_index,
            )
