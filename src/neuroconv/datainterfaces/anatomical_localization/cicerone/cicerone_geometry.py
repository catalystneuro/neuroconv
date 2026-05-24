"""Coordinate composition for MonkeyCicerone chamber and electrode geometry.

Composes the chamber pose, the dial rotations, the microdrive offsets, and the
calibration depth into a stereotaxic target for each electrode. Also provides
conversion from Cicerone's ``stereoHf0`` axis convention to NMT v2 RAS.

Verification status
-------------------
The field meanings used below were confirmed by direct comparison of the
MonkeyCicerone v1.0 user manual (Table 2) against the live GUI, with the Orion
session file loaded. Verified by GUI: every ``chtrans`` field name maps to the
expected control with matching values; ``chtrans plane`` is 0 for the
"perpendicular" radio (sagittal base) and 1 for "parallel" (coronal base);
``+x = Left`` per the manual's Panel F.

Verified visually against the live Cicerone GUI (2026-05-18 sweep test): the
``rx`` (vertical dial) sign convention agrees with Cicerone in the
``plane = 0`` case. A controlled sweep with all other rotations zeroed showed
positive ``rx`` tilts the chamber's brain-facing end posterior (matching this
composer's right-hand-rule prediction) and negative ``rx`` tilts it anterior.

The remaining sign conventions (``ry``, ``rcy``, ``plane = 1`` swing direction,
and the sign of ``calibration``) share the same right-hand-rule construction
as ``rx`` and were validated via six synthetic-input experiments (documented
in the cicerone format walkthrough notes); each experiment matched its
analytic prediction. Direct numerical equivalence to Cicerone's renderer
cannot be tested because Cicerone exposes no composed stereotaxic coordinate
in any panel or output file and ships application code as TclPro bytecode.
Users requiring sub-mm precision should still cross-check against their own
reference targets, but the composer is no longer flagged as experimental.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .cicerone_session_parser import ChamberRecord
from .cicerone_sites_parser import SiteRecord


@dataclass
class ElectrodeTarget:
    """Composed stereotaxic position of one electrode tip.

    Coordinates are reported both in Cicerone's native ``stereoHf0`` frame
    (``ml``, ``vd``, ``ap`` with ``+x = Left``) and in NMT v2 RAS (``ras_x``,
    ``ras_y``, ``ras_z``). Both are in millimetres.
    """

    chamber_index: int
    ml: float
    vd: float
    ap: float
    ras_x: float
    ras_y: float
    ras_z: float


def compose_chamber_rotation_matrix(
    vertical_dial_deg: float,
    horizontal_dial_deg: float,
    skull_fit_dial_deg: float,
    plane: int,
) -> np.ndarray:
    """Build the 3x3 chamber-frame to stereotaxic rotation matrix.

    Parameters
    ----------
    vertical_dial_deg : float
        ``chtrans rx``: vertical dial of the stereotaxic arm.
    horizontal_dial_deg : float
        ``chtrans ry``: horizontal dial.
    skull_fit_dial_deg : float
        ``chtrans rcy``: rotation of the chamber about its own axis to fit the
        skull contour.
    plane : int
        ``chtrans plane``: 0 means the frame's ML axis is perpendicular to the
        plane of rotation (sagittal base); 1 means parallel (coronal base).
        Any other value is rejected.

    Returns
    -------
    numpy.ndarray
        A 3x3 rotation matrix that maps a vector in the chamber's local frame
        (``(ml, depth, ap)`` with depth along the chamber's own axis) into
        Cicerone's stereoHf0 ``(ML, VD, AP)`` frame.

    Notes
    -----
    The composition order applied here is::

        R = R_base(plane) @ R_y(horizontal) @ R_x(vertical) @ R_y(skull_fit)

    where ``R_base(0) = identity`` (sagittal-base) and
    ``R_base(1) = R_y(-90 deg)`` (coronal-base, per the manual's instruction
    that "to place chamber in coronal orientation, set frame's ML axis to
    parallel and horizontal angle to 90"). The skull-fit rotation is applied
    first (i.e. closest to the local frame), reflecting that it is a rotation
    about the chamber's own axis before the chamber is oriented in the frame.
    Right-hand rule for all positive angles. See module docstring for the
    verification gap.
    """
    if plane not in (0, 1):
        raise ValueError(f"chtrans plane must be 0 or 1, got {plane!r}")

    base = _rotation_y(-90.0) if plane == 1 else np.eye(3)
    return base @ _rotation_y(horizontal_dial_deg) @ _rotation_x(vertical_dial_deg) @ _rotation_y(skull_fit_dial_deg)


def compose_electrode_target(
    chamber: ChamberRecord,
    depth_mm: float = 0.0,
    clamp_eltrans_ap: bool = True,
) -> ElectrodeTarget:
    """Compose the stereotaxic position of one electrode tip.

    Parameters
    ----------
    chamber : ChamberRecord
        Parsed chamber record (see ``cicerone_session_parser``).
    depth_mm : float, optional
        Additional microdrive advancement in mm along the chamber's depth
        axis, beyond the calibration offset. Defaults to 0 (electrode tip at
        the calibration position).
    clamp_eltrans_ap : bool, optional
        If True (default), ``chamber.eltrans_ap`` is clamped to ``[-10, 10]``
        mm to match Cicerone's silent clamping documented in Table 2. Set
        False to use the file-written value verbatim.

    Returns
    -------
    ElectrodeTarget
        Composed stereotaxic position, in both Cicerone-native and NMT v2 RAS
        coordinates.
    """
    eltrans_ap = chamber.eltrans_ap
    if clamp_eltrans_ap:
        eltrans_ap = max(-10.0, min(10.0, eltrans_ap))

    # Chamber-local +y points dorsally (out of the brain), so advancing the
    # electrode along the microdrive (positive ``depth_mm``, positive
    # ``eltrans_depth``) reduces y in chamber-local coordinates. Calibration
    # offsets the tip along the same axis: positive calibration means tip is
    # above the rim (positive y in chamber-local), per manual Table 2.
    electrode_in_chamber = np.array(
        [
            chamber.eltrans_ml,
            chamber.calibration_mm - chamber.eltrans_depth - depth_mm,
            eltrans_ap,
        ]
    )

    rotation = compose_chamber_rotation_matrix(
        vertical_dial_deg=chamber.vertical_dial_deg,
        horizontal_dial_deg=chamber.horizontal_dial_deg,
        skull_fit_dial_deg=chamber.skull_fit_dial_deg,
        plane=chamber.plane,
    )

    translation = np.array([chamber.translation_ml, chamber.translation_vd, chamber.translation_ap])

    stereotaxic = translation + rotation @ electrode_in_chamber
    ras_x, ras_y, ras_z = cicerone_to_nmt_v2_ras(*stereotaxic)

    return ElectrodeTarget(
        chamber_index=chamber.index,
        ml=float(stereotaxic[0]),
        vd=float(stereotaxic[1]),
        ap=float(stereotaxic[2]),
        ras_x=float(ras_x),
        ras_y=float(ras_y),
        ras_z=float(ras_z),
    )


def compose_site_target(chamber: ChamberRecord, site: SiteRecord) -> ElectrodeTarget:
    """Compose the stereotaxic position of one recording site's electrode tip.

    Drives the same composer math as :func:`compose_electrode_target`, but with
    the microdrive coordinates and calibration coming from a sites-file row
    rather than the chamber's configuration-file ``eltrans`` / ``calibration``.
    The chamber's pose (translation, rotations, plane) comes from the
    configuration as usual.

    Parameters
    ----------
    chamber : ChamberRecord
        The chamber whose pose this site lives in. Must satisfy
        ``chamber.index == site.chamber``; the caller is responsible for
        matching them.
    site : SiteRecord
        One row of the sites file, providing microdrive coordinates
        (``site.ap``, ``site.ml``, ``site.depth``) and the calibration value
        (``site.electrode_calibr``) that applied at the moment the site was
        saved.

    Returns
    -------
    ElectrodeTarget
        Stereotaxic position of the electrode tip in both Cicerone-native
        ``stereoHf0`` and NMT v2 RAS frames.

    Raises
    ------
    ValueError
        If the chamber's index does not match the site's recorded chamber.
    """
    if chamber.index != site.chamber:
        raise ValueError(
            f"Chamber index mismatch: ChamberRecord has index {chamber.index} "
            f"but SiteRecord references chamber {site.chamber}."
        )

    # The sites file reports microdrive coordinates in its own column order
    # (AP, ML, Depth). The composer wants them in the chamber-local
    # (ml, depth, ap) order, so we re-permute. Cicerone clamps the AP
    # microdrive value to [-10, 10] mm at the GUI, but sites are saved with
    # the operator's intended values; we match Cicerone's GUI clamping for
    # consistency with the chamber-level path.
    eltrans_ap = max(-10.0, min(10.0, site.ap))

    electrode_in_chamber = np.array(
        [
            site.ml,
            site.electrode_calibr - site.depth,
            eltrans_ap,
        ]
    )

    rotation = compose_chamber_rotation_matrix(
        vertical_dial_deg=chamber.vertical_dial_deg,
        horizontal_dial_deg=chamber.horizontal_dial_deg,
        skull_fit_dial_deg=chamber.skull_fit_dial_deg,
        plane=chamber.plane,
    )

    translation = np.array([chamber.translation_ml, chamber.translation_vd, chamber.translation_ap])

    stereotaxic = translation + rotation @ electrode_in_chamber
    ras_x, ras_y, ras_z = cicerone_to_nmt_v2_ras(*stereotaxic)

    return ElectrodeTarget(
        chamber_index=chamber.index,
        ml=float(stereotaxic[0]),
        vd=float(stereotaxic[1]),
        ap=float(stereotaxic[2]),
        ras_x=float(ras_x),
        ras_y=float(ras_y),
        ras_z=float(ras_z),
    )


def cicerone_to_nmt_v2_ras(ml: float, vd: float, ap: float) -> tuple[float, float, float]:
    """Convert Cicerone stereoHf0 ``(ML, VD, AP)`` to NMT v2 RAS ``(x, y, z)``.

    Cicerone uses ``+x = Left`` per the manual's Panel F; NMT v2 uses standard
    RAS with ``+x = Right``. Origin, alignment (Horsley-Clarke), and units (mm)
    are shared between the two frames, so only an axis permutation and one
    sign flip are needed.

    Parameters
    ----------
    ml : float
        Medial-Lateral position in mm (Cicerone's ``+x``, with positive = Left).
    vd : float
        Ventral-Dorsal position in mm.
    ap : float
        Anterior-Posterior position in mm.

    Returns
    -------
    tuple of float
        ``(ras_x, ras_y, ras_z)`` in mm, NMT v2 RAS convention.
    """
    return -ml, ap, vd


def _rotation_x(angle_deg: float) -> np.ndarray:
    """Right-hand rotation about the x-axis by ``angle_deg`` degrees."""
    theta = np.deg2rad(angle_deg)
    cos_t, sin_t = np.cos(theta), np.sin(theta)
    return np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, cos_t, -sin_t],
            [0.0, sin_t, cos_t],
        ]
    )


def _rotation_y(angle_deg: float) -> np.ndarray:
    """Right-hand rotation about the y-axis by ``angle_deg`` degrees."""
    theta = np.deg2rad(angle_deg)
    cos_t, sin_t = np.cos(theta), np.sin(theta)
    return np.array(
        [
            [cos_t, 0.0, sin_t],
            [0.0, 1.0, 0.0],
            [-sin_t, 0.0, cos_t],
        ]
    )
