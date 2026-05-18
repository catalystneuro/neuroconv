"""NeuroConv DataInterface for MonkeyCicerone session files.

Layout in the produced NWB file follows the ndx-anatomical-localization pattern
used by the Turner-Delong M1 (primary motor cortex) MPTP
(1-methyl-4-phenyl-1,2,3,6-tetrahydropyridine) conversion:

- One ``Device`` per chamber, holding chamber-type metadata.
- One ``ElectrodeGroup`` per chamber, referencing the chamber Device.
- One row per chamber on the standard ``nwbfile.electrodes`` table, with
  chamber-relative microdrive parameters as custom columns.
- One ``Localization`` container in ``nwbfile.lab_meta_data['localization']``,
  wrapping the ``NMTv2Space`` and one ``AnatomicalCoordinatesTable`` whose rows
  carry both Cicerone-native (``x_raw, y_raw, z_raw`` in ``(ML, VD, AP)``) and
  NMT v2 RAS (``x, y, z``) coordinates. The table's ``localized_entity`` column
  references the electrode rows in ``nwbfile.electrodes``.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import FilePath, validate_call
from pynwb import NWBFile
from pynwb.device import Device
from pynwb.ecephys import ElectrodeGroup

from .cicerone_geometry import compose_electrode_target
from .cicerone_session_parser import CiceroneSession, parse_session_file
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
        ] = "Path to the Cicerone session text file (typically *_Configuration_*.txt)."
        return source_schema

    @validate_call
    def __init__(self, file_path: FilePath, verbose: bool = False):
        """
        Parameters
        ----------
        file_path : FilePath
            Path to the Cicerone session text file.
        verbose : bool, default: False
            Whether to print progress.
        """
        self.file_path = Path(file_path)
        self.verbose = verbose
        self._session: CiceroneSession = parse_session_file(self.file_path)
        super().__init__(file_path=str(self.file_path))

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
        """Add chamber Devices, electrode rows, and a Localization container."""
        import ndx_anatomical_localization

        self._add_extra_electrode_columns(nwbfile)
        electrode_row_indices = self._add_chambers_and_electrodes(nwbfile)
        self._add_localization(nwbfile, ndx_anatomical_localization, electrode_row_indices)

    @staticmethod
    def _add_extra_electrode_columns(nwbfile: NWBFile) -> None:
        """Declare Cicerone-specific columns on ``nwbfile.electrodes``.

        These hold the chamber-relative microdrive parameters as they appear
        in the session file, before any rotation composition. Adding the
        columns here keeps the source-level fidelity Tier A targets without
        introducing a parallel processing-module table.
        """
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
        ]
        for name, description in column_specs:
            if name not in existing:
                nwbfile.add_electrode_column(name=name, description=description)

    def _add_chambers_and_electrodes(self, nwbfile: NWBFile) -> dict[int, int]:
        """Create per-chamber Device, ElectrodeGroup, and one electrode row each.

        Returns a mapping from Cicerone chamber index to the row index assigned
        in ``nwbfile.electrodes``, used to back-link the
        ``AnatomicalCoordinatesTable``'s ``localized_entity`` column.
        """
        electrode_row_by_chamber: dict[int, int] = {}
        for chamber in self._session.chambers:
            device_name = f"CiceroneChamber{chamber.index}"
            device_description = (
                f"MonkeyCicerone chamber {chamber.index}: type={chamber.chamber_type}, "
                f"electrode={chamber.electrode_type}, physical angle={chamber.chamber_angle_deg} deg, "
                f"plane={chamber.plane} ("
                f"{'parallel' if chamber.plane == 1 else 'perpendicular'} to plane of rotation)."
            )
            device = Device(name=device_name, description=device_description)
            nwbfile.add_device(device)

            group = ElectrodeGroup(
                name=f"ElectrodeGroupCiceroneChamber{chamber.index}",
                description=(
                    f"Planned electrode in MonkeyCicerone chamber {chamber.index}. "
                    f"Position derived from session-file chamber pose and microdrive parameters."
                ),
                location="Cicerone-planned stereotaxic target",
                device=device,
            )
            nwbfile.add_electrode_group(group)

            nwbfile.add_electrode(
                group=group,
                location=f"Cicerone chamber {chamber.index} planned target",
                cicerone_chamber_index=chamber.index,
                cicerone_eltrans_ml=chamber.eltrans_ml,
                cicerone_eltrans_depth=chamber.eltrans_depth,
                cicerone_eltrans_ap=chamber.eltrans_ap,
                cicerone_calibration_mm=chamber.calibration_mm,
                cicerone_chamber_plane=chamber.plane,
            )
            electrode_row_by_chamber[chamber.index] = len(nwbfile.electrodes) - 1
        return electrode_row_by_chamber

    def _add_localization(
        self,
        nwbfile: NWBFile,
        ndx_anatomical_localization,
        electrode_row_by_chamber: dict[int, int],
    ) -> None:
        """Build a ``Localization`` container with the NMT v2 space and an
        ``AnatomicalCoordinatesTable`` carrying both Cicerone-native and
        NMT v2 RAS coordinates for every chamber's planned electrode."""
        space = ndx_anatomical_localization.NMTv2Space(name="NMTv2")
        localization = ndx_anatomical_localization.Localization(spaces=[space])
        nwbfile.add_lab_meta_data(localization)

        coordinates_table = ndx_anatomical_localization.AnatomicalCoordinatesTable(
            name="NMTv2Coordinates",
            description=(
                "Composed stereotaxic targets for each MonkeyCicerone electrode. The "
                "x/y/z columns are in NMT v2 RAS (mm), derived from the chamber pose "
                "and electrode microdrive parameters that live on the linked rows of "
                "nwbfile.electrodes. The x_raw/y_raw/z_raw columns preserve the same "
                "point in Cicerone's native stereoHf0 frame (ML, VD, AP), with "
                "+x = Left per the MonkeyCicerone v1.0 manual Panel F. See the "
                "CiceroneSessionInterface docstring for the verification status of "
                "the chamber rotation composition."
            ),
            space=space,
            method=(
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
                "renderer is not testable (Cicerone exposes no composed coordinate). "
                "Tier A archival output: coordinates only, no atlas brain-region lookup."
            ),
            target=nwbfile.electrodes,
            columns=[_make_raw_coordinate_column("x_raw", "ML axis (Cicerone native, +x = Left), in mm.")[0]]
            + [_make_raw_coordinate_column("y_raw", "VD axis (Cicerone native, ventral-dorsal), in mm.")[0]]
            + [_make_raw_coordinate_column("z_raw", "AP axis (Cicerone native, anterior-posterior), in mm.")[0]],
        )
        localization.add_anatomical_coordinates_tables(coordinates_table)
        for chamber in self._session.chambers:
            target = compose_electrode_target(chamber)
            coordinates_table.add_row(
                x=target.ras_x,
                y=target.ras_y,
                z=target.ras_z,
                x_raw=target.ml,
                y_raw=target.vd,
                z_raw=target.ap,
                localized_entity=electrode_row_by_chamber[chamber.index],
            )


def _make_raw_coordinate_column(name: str, description: str):
    """Create a VectorData column for a raw-coordinate axis.

    Wrapped in a function so we can pass these to ``AnatomicalCoordinatesTable``
    via the ``columns=`` kwarg; the table only declares ``x``, ``y``, ``z`` and
    ``localized_entity`` as required columns, so the raw axes need to be added
    explicitly.
    """
    from hdmf.common.table import VectorData

    return (VectorData(name=name, description=description, data=[]),)
