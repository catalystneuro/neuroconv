import math
import tempfile
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
from pynwb import NWBHDF5IO, NWBFile

from neuroconv.datainterfaces.anatomical_localization.cicerone import (
    CiceroneSessionInterface,
)
from neuroconv.datainterfaces.anatomical_localization.cicerone.cicerone_geometry import (
    cicerone_to_nmt_v2_ras,
    compose_chamber_rotation_matrix,
    compose_electrode_target,
)
from neuroconv.datainterfaces.anatomical_localization.cicerone.cicerone_session_parser import (
    parse_session_file,
)
from neuroconv.datainterfaces.anatomical_localization.cicerone.cicerone_sites_parser import (
    parse_sites_file,
)

SYNTHETIC = Path(__file__).parent / "synthetic_session.txt"
ANONYMIZED_ORION = Path(__file__).parent / "anonymized_orion_session.txt"
SAMPLE_MER_CONFIG = Path(__file__).parent / "sample_mer_configuration.txt"
SAMPLE_MER_SITES = Path(__file__).parent / "sample_mer_sites.txt"


def _parse_orion_silently():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return parse_session_file(ANONYMIZED_ORION)


def test_parser_reads_subject_and_chambers():
    session = parse_session_file(SYNTHETIC)
    assert session.monkey_name == "SyntheticMonkey"
    assert session.monkey_id == "SYN-001"
    assert session.current_system == "stereoHf0"
    assert len(session.chambers) == 2
    assert session.landmarks.pc_z_trans == -11.7


def test_parser_chamber_fields_match_synthetic_file():
    session = parse_session_file(SYNTHETIC)
    ch1, ch2 = session.chambers
    assert (ch1.translation_ml, ch1.translation_vd, ch1.translation_ap) == (0.0, 30.0, 0.0)
    assert ch1.plane == 0
    assert ch1.chamber_type == "micro"
    assert ch1.calibration_mm == 5.0
    assert ch2.plane == 1
    assert ch2.chamber_type == "dbs"
    assert ch2.calibration_mm == -8.0
    assert ch2.vertical_dial_deg == 10.0


def test_parser_warns_on_out_of_range_eltrans_ap(tmp_path):
    content = SYNTHETIC.read_text()
    content += (
        "\n#Chamber 3 with out-of-range eltrans_ap\n"
        "chview3 1\nchangle3 0\nchtype3 micro\nchelec3 micro\n"
        "chtrans x3 0.0\nchtrans y3 0.0\nchtrans z3 0.0\n"
        "chtrans rx3 0.0\nchtrans ry3 0.0\nchtrans rz3 0\nchtrans rcy3 0.0\nchtrans plane3 0\n"
        "eltrans x3 0.0\neltrans y3 0.0\neltrans z3 15.0\ncalibration elec3 0.0\n"
    )
    out = tmp_path / "with_out_of_range.txt"
    out.write_text(content)
    with pytest.warns(UserWarning, match="outside the documented range"):
        parse_session_file(out)


def test_rotation_identity():
    matrix = compose_chamber_rotation_matrix(0.0, 0.0, 0.0, 0)
    np.testing.assert_allclose(matrix, np.eye(3), atol=1e-12)


def test_rotation_plane_one_is_y_minus_90():
    matrix = compose_chamber_rotation_matrix(0.0, 0.0, 0.0, 1)
    # Right-hand rotation about y by -90 deg maps +z to -x and +x to +z.
    np.testing.assert_allclose(matrix @ np.array([0.0, 0.0, 1.0]), [-1.0, 0.0, 0.0], atol=1e-12)
    np.testing.assert_allclose(matrix @ np.array([1.0, 0.0, 0.0]), [0.0, 0.0, 1.0], atol=1e-12)


def test_rotation_rejects_invalid_plane():
    with pytest.raises(ValueError, match="plane must be 0 or 1"):
        compose_chamber_rotation_matrix(0.0, 0.0, 0.0, plane=2)


def test_axis_conversion_to_nmt_v2_ras():
    assert cicerone_to_nmt_v2_ras(1.0, 2.0, 3.0) == (-1.0, 3.0, 2.0)


def test_compose_electrode_target_basic_geometry():
    """Chamber 1 of the synthetic file has no rotation, no microdrive offset,
    just a chamber VD translation of 30 mm and calibration of +5 mm. The
    composed tip should sit at (0, 35, 0) in Cicerone-native coordinates.
    This is the analytic regression check on the composition formula."""
    session = parse_session_file(SYNTHETIC)
    target = compose_electrode_target(session.chambers[0])
    assert math.isclose(target.ml, 0.0, abs_tol=1e-9)
    assert math.isclose(target.vd, 35.0, abs_tol=1e-9)
    assert math.isclose(target.ap, 0.0, abs_tol=1e-9)
    assert math.isclose(target.ras_x, 0.0, abs_tol=1e-9)
    assert math.isclose(target.ras_y, 0.0, abs_tol=1e-9)
    assert math.isclose(target.ras_z, 35.0, abs_tol=1e-9)


def test_anonymized_orion_three_chambers_with_expected_plane_distribution():
    """All values verified against the live Cicerone GUI on 2026-05-14.
    Chamber 1 has plane=0 (perpendicular, sagittal base); chambers 2 and 3
    have plane=1 (parallel, coronal base)."""
    session = _parse_orion_silently()
    assert session.monkey_id == "ANIMAL-A-001"
    assert len(session.chambers) == 3
    assert [c.plane for c in session.chambers] == [0, 1, 1]
    assert [c.chamber_type for c in session.chambers] == ["micro", "dbs", "dbs"]
    assert [c.calibration_mm for c in session.chambers] == pytest.approx([10.23, -20.01, -20.02])


def test_anonymized_orion_produces_finite_anatomically_plausible_targets():
    session = _parse_orion_silently()
    for chamber in session.chambers:
        target = compose_electrode_target(chamber)
        assert np.isfinite([target.ml, target.vd, target.ap]).all()
        assert abs(target.ml) < 50
        assert abs(target.ap) < 50
        assert -20 < target.vd < 100


def test_sites_parser_reads_bundled_sample():
    """The Cicerone-shipped sample MER file has 189 sites across 2 tracks in
    Chamber 1, with annotations like ``stn``, ``background``, ``other``."""
    sites = parse_sites_file(SAMPLE_MER_SITES)
    assert len(sites) == 189
    assert {s.chamber for s in sites} == {1}
    assert sorted({s.track_number for s in sites}) == [1, 2]
    assert sum(1 for s in sites if s.track_number == 1) == 70
    assert sum(1 for s in sites if s.track_number == 2) == 119
    # SiteNumber RESETS at each new track: confirms the (track, site) pair
    # is the row-unique key, not SiteNumber alone.
    track1_site_numbers = sorted({s.site_number for s in sites if s.track_number == 1})
    track2_site_numbers = sorted({s.site_number for s in sites if s.track_number == 2})
    assert track1_site_numbers[0] == 1 and track1_site_numbers[-1] == 70
    assert track2_site_numbers[0] == 1 and track2_site_numbers[-1] == 119
    # Sample contains real anatomical labels and clinical annotations
    locations = {s.location for s in sites if s.location}
    assert "stn" in locations
    assert "background" in locations
    assert any(s.site_comment for s in sites)


def test_sites_interface_writes_all_sites_when_no_selection():
    """With sites_file_path provided and no track_numbers/site_numbers, the
    interface writes one electrode row per site (189 in the sample)."""
    interface = CiceroneSessionInterface(
        file_path=SAMPLE_MER_CONFIG,
        sites_file_path=SAMPLE_MER_SITES,
    )
    nwbfile = NWBFile(
        session_description="Cicerone sites mode test",
        identifier="cicerone-sites-all",
        session_start_time=datetime(2026, 1, 1).astimezone(),
    )
    interface.add_to_nwbfile(nwbfile)
    assert len(nwbfile.electrodes) == 189
    coords_table = nwbfile.lab_meta_data["localization"].anatomical_coordinates_tables["NMTv2Coordinates"]
    assert len(coords_table) == 189
    df = nwbfile.electrodes.to_dataframe()
    assert "cicerone_site_number" in df.columns
    assert "cicerone_location" in df.columns
    assert (df["cicerone_track_number"] == 1).sum() == 70
    assert (df["cicerone_track_number"] == 2).sum() == 119


def test_sites_interface_filters_by_track_site_pairs():
    """Three specific sites: site 1 of track 1, site 69 of track 2 (which is
    labeled stn in the sample), and site 119 of track 2 (the last one)."""
    interface = CiceroneSessionInterface(
        file_path=SAMPLE_MER_CONFIG,
        sites_file_path=SAMPLE_MER_SITES,
        track_numbers=[1, 2, 2],
        site_numbers=[1, 69, 119],
    )
    nwbfile = NWBFile(
        session_description="Cicerone sites filter test",
        identifier="cicerone-sites-filter",
        session_start_time=datetime(2026, 1, 1).astimezone(),
    )
    interface.add_to_nwbfile(nwbfile)
    df = nwbfile.electrodes.to_dataframe()
    assert len(df) == 3
    assert df["cicerone_track_number"].tolist() == [1, 2, 2]
    assert df["cicerone_site_number"].tolist() == [1, 69, 119]
    # Site 69 of track 2 is the first STN-labeled site in the sample
    site_stn = df[(df["cicerone_track_number"] == 2) & (df["cicerone_site_number"] == 69)]
    assert site_stn["cicerone_location"].iloc[0] == "stn"


def test_sites_interface_raises_on_unknown_track_site_pair():
    """A (track, site) combination that does not exist in the file must
    raise at construction with a helpful error."""
    with pytest.raises(ValueError, match="No site with TrackNumber=2, SiteNumber=250"):
        CiceroneSessionInterface(
            file_path=SAMPLE_MER_CONFIG,
            sites_file_path=SAMPLE_MER_SITES,
            track_numbers=[2],
            site_numbers=[250],
        )


def test_sites_interface_raises_when_only_one_list_provided():
    with pytest.raises(ValueError, match="site_numbers was provided but track_numbers was not"):
        CiceroneSessionInterface(
            file_path=SAMPLE_MER_CONFIG,
            sites_file_path=SAMPLE_MER_SITES,
            site_numbers=[1],
        )
    with pytest.raises(ValueError, match="track_numbers was provided but site_numbers was not"):
        CiceroneSessionInterface(
            file_path=SAMPLE_MER_CONFIG,
            sites_file_path=SAMPLE_MER_SITES,
            track_numbers=[1],
        )


def test_sites_interface_raises_on_length_mismatch():
    with pytest.raises(ValueError, match="must have the same length; got 2 and 1"):
        CiceroneSessionInterface(
            file_path=SAMPLE_MER_CONFIG,
            sites_file_path=SAMPLE_MER_SITES,
            track_numbers=[1, 2],
            site_numbers=[1],
        )


def test_sites_two_tables_describe_same_points():
    """For each filtered site, NMT (x, y, z) = (-cic_x, cic_z, cic_y)."""
    interface = CiceroneSessionInterface(
        file_path=SAMPLE_MER_CONFIG,
        sites_file_path=SAMPLE_MER_SITES,
        track_numbers=[1, 2, 2, 2],
        site_numbers=[1, 1, 47, 119],
    )
    nwbfile = NWBFile(
        session_description="Cicerone sites axis-frame test",
        identifier="cicerone-sites-frames",
        session_start_time=datetime(2026, 1, 1).astimezone(),
    )
    interface.add_to_nwbfile(nwbfile)
    loc = nwbfile.lab_meta_data["localization"]
    nmt_df = loc.anatomical_coordinates_tables["NMTv2Coordinates"].to_dataframe()
    cic_df = loc.anatomical_coordinates_tables["CiceroneStereoHf0Coordinates"].to_dataframe()
    np.testing.assert_allclose(nmt_df["x"].to_numpy(), -cic_df["x"].to_numpy(), atol=1e-9)
    np.testing.assert_allclose(nmt_df["y"].to_numpy(), cic_df["z"].to_numpy(), atol=1e-9)
    np.testing.assert_allclose(nmt_df["z"].to_numpy(), cic_df["y"].to_numpy(), atol=1e-9)


def test_interface_roundtrip_writes_and_reads_back():
    interface = CiceroneSessionInterface(
        file_path=SAMPLE_MER_CONFIG,
        sites_file_path=SAMPLE_MER_SITES,
        track_numbers=[1, 2],
        site_numbers=[1, 1],
    )

    metadata = interface.get_metadata()
    assert metadata["Subject"]["subject_id"] == "M-001"
    assert "Rhesus" in metadata["Subject"]["description"]

    nwbfile = NWBFile(
        session_description="Cicerone interface roundtrip test",
        identifier="cicerone-roundtrip",
        session_start_time=datetime(2026, 1, 1).astimezone(),
    )
    interface.add_to_nwbfile(nwbfile)

    assert "CiceroneChamber1" in nwbfile.devices
    assert "localization" in nwbfile.lab_meta_data
    localization = nwbfile.lab_meta_data["localization"]
    assert {"NMTv2", "CiceroneStereoHf0"} <= set(localization.spaces.keys())
    assert {"NMTv2Coordinates", "CiceroneStereoHf0Coordinates"} <= set(
        localization.anatomical_coordinates_tables.keys()
    )
    assert len(nwbfile.electrodes) == 2
    assert {
        "cicerone_chamber_index",
        "cicerone_eltrans_ml",
        "cicerone_calibration_mm",
        "cicerone_site_number",
        "cicerone_track_number",
    } <= set(nwbfile.electrodes.colnames)

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "cicerone.nwb"
        with NWBHDF5IO(path, "w") as io:
            io.write(nwbfile)
        with NWBHDF5IO(path, "r") as io:
            nwb_read = io.read()
            assert "CiceroneChamber1" in nwb_read.devices
            assert "localization" in nwb_read.lab_meta_data
            loc = nwb_read.lab_meta_data["localization"]

            nmt_df = loc.anatomical_coordinates_tables["NMTv2Coordinates"].to_dataframe()
            cicerone_df = loc.anatomical_coordinates_tables["CiceroneStereoHf0Coordinates"].to_dataframe()
            assert len(nmt_df) == 2
            assert len(cicerone_df) == 2
            assert {"x", "y", "z"} <= set(nmt_df.columns)
            assert {"x", "y", "z"} <= set(cicerone_df.columns)
            assert "x_raw" not in nmt_df.columns
            assert "x_raw" not in cicerone_df.columns
            assert np.all(np.isfinite(nmt_df[["x", "y", "z"]].values))
            assert np.all(np.isfinite(cicerone_df[["x", "y", "z"]].values))

            # The two tables describe the SAME physical points in different frames;
            # the axis permutation/sign flip must hold: NMT (x, y, z) = (-cic_x, cic_z, cic_y)
            np.testing.assert_allclose(nmt_df["x"].to_numpy(), -cicerone_df["x"].to_numpy(), atol=1e-9)
            np.testing.assert_allclose(nmt_df["y"].to_numpy(), cicerone_df["z"].to_numpy(), atol=1e-9)
            np.testing.assert_allclose(nmt_df["z"].to_numpy(), cicerone_df["y"].to_numpy(), atol=1e-9)
