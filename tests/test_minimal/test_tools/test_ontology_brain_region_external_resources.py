"""Tests for attaching Allen Mouse Brain Atlas references (HERD) to NWB files."""

from datetime import datetime

from dateutil.tz import tzutc
from pynwb import NWBFile
from pynwb.file import Subject

from neuroconv.tools.ontology import add_brain_region_external_resources


def _make_nwbfile(species="Mus musculus", with_subject=True) -> NWBFile:
    nwbfile = NWBFile(
        session_description="d",
        identifier="id",
        session_start_time=datetime(2020, 1, 1, tzinfo=tzutc()),
    )
    if with_subject:
        nwbfile.subject = Subject(subject_id="s1", species=species)
    return nwbfile


def _add_electrodes(nwbfile: NWBFile, locations) -> None:
    device = nwbfile.create_device(name="probe")
    group = nwbfile.create_electrode_group(name="group0", description="d", location="unknown", device=device)
    for index, location in enumerate(locations):
        nwbfile.add_electrode(location=location, group=group, id=index)


class TestNoOps:
    def test_no_subject(self):
        nwbfile = _make_nwbfile(with_subject=False)
        _add_electrodes(nwbfile, ["CA1"])
        assert add_brain_region_external_resources(nwbfile) == 0
        assert nwbfile.external_resources is None

    def test_non_mouse_subject_is_skipped(self):
        nwbfile = _make_nwbfile(species="Homo sapiens")
        _add_electrodes(nwbfile, ["CA1", "VISp"])
        assert add_brain_region_external_resources(nwbfile) == 0
        assert nwbfile.external_resources is None

    def test_no_recognized_locations(self):
        nwbfile = _make_nwbfile()
        _add_electrodes(nwbfile, ["unknown", "not a region"])
        assert add_brain_region_external_resources(nwbfile) == 0
        assert nwbfile.external_resources is None


class TestElectrodeAnnotation:
    def test_distinct_locations_are_annotated_once_each(self):
        nwbfile = _make_nwbfile()
        _add_electrodes(nwbfile, ["CA1", "CA1", "VISp", "unknown"])

        # "mouse" common name also gates as Mus musculus.
        assert add_brain_region_external_resources(nwbfile) == 2

        dataframe = nwbfile.external_resources.to_dataframe()
        assert sorted(dataframe["key"].tolist()) == ["CA1", "VISp"]
        by_key = dict(zip(dataframe["key"], dataframe["entity_id"]))
        assert by_key == {"CA1": "MBA:382", "VISp": "MBA:385"}
        uris = dict(zip(dataframe["key"], dataframe["entity_uri"]))
        assert uris["CA1"] == "https://purl.brain-bican.org/ontology/mbao/MBA_382"

    def test_reference_points_at_electrodes_location_column(self):
        nwbfile = _make_nwbfile()
        _add_electrodes(nwbfile, ["CA1"])
        add_brain_region_external_resources(nwbfile)

        # HERD records the reference against the ``location`` column (a VectorData), not the table.
        objects = nwbfile.external_resources.objects.to_dataframe()
        assert nwbfile.electrodes["location"].object_id in objects["object_id"].tolist()

    def test_common_name_subject_still_resolves_as_mouse(self):
        nwbfile = _make_nwbfile(species="mouse")
        _add_electrodes(nwbfile, ["CA1"])
        assert add_brain_region_external_resources(nwbfile) == 1


class TestElectrodeGroupAndImagingPlaneAnnotation:
    def test_electrode_group_location_is_annotated(self):
        nwbfile = _make_nwbfile()
        device = nwbfile.create_device(name="probe")
        nwbfile.create_electrode_group(name="g0", description="d", location="VISp", device=device)

        assert add_brain_region_external_resources(nwbfile) == 1
        dataframe = nwbfile.external_resources.to_dataframe()
        assert dataframe["key"].tolist() == ["VISp"]
        assert dataframe["entity_id"].tolist() == ["MBA:385"]

    def test_imaging_plane_location_is_annotated(self):
        nwbfile = _make_nwbfile()
        device = nwbfile.create_device(name="scope")
        optical_channel = _optical_channel()
        nwbfile.create_imaging_plane(
            name="plane0",
            optical_channel=optical_channel,
            description="d",
            device=device,
            excitation_lambda=600.0,
            indicator="GCaMP",
            location="CA1",
            imaging_rate=30.0,
        )

        assert add_brain_region_external_resources(nwbfile) == 1
        dataframe = nwbfile.external_resources.to_dataframe()
        assert dataframe["key"].tolist() == ["CA1"]
        assert dataframe["entity_id"].tolist() == ["MBA:382"]


class TestMetadataMapping:
    def test_metadata_mapping_annotates_unrecognized_location(self):
        nwbfile = _make_nwbfile()
        _add_electrodes(nwbfile, ["my special area"])
        metadata = {"BrainRegions": {"my special area": "MBA:382"}}

        assert add_brain_region_external_resources(nwbfile, metadata=metadata) == 1
        dataframe = nwbfile.external_resources.to_dataframe()
        assert dataframe["key"].tolist() == ["my special area"]
        assert dataframe["entity_id"].tolist() == ["MBA:382"]

    def test_metadata_mapping_takes_precedence_over_offline_lookup(self):
        nwbfile = _make_nwbfile()
        _add_electrodes(nwbfile, ["CA1"])
        # Override the offline result (MBA:382) with an explicit id.
        metadata = {"BrainRegions": {"CA1": {"mba_id": 999, "name": "custom"}}}

        add_brain_region_external_resources(nwbfile, metadata=metadata)
        dataframe = nwbfile.external_resources.to_dataframe()
        assert dataframe["entity_id"].tolist() == ["MBA:999"]

    def test_metadata_and_offline_combine(self):
        nwbfile = _make_nwbfile()
        _add_electrodes(nwbfile, ["CA1", "my special area"])
        metadata = {"BrainRegions": {"my special area": "42"}}

        assert add_brain_region_external_resources(nwbfile, metadata=metadata) == 2
        dataframe = nwbfile.external_resources.to_dataframe()
        assert dict(zip(dataframe["key"], dataframe["entity_id"])) == {
            "CA1": "MBA:382",
            "my special area": "MBA:42",
        }


class TestHERDLifecycle:
    def test_idempotent(self):
        nwbfile = _make_nwbfile()
        _add_electrodes(nwbfile, ["CA1", "VISp"])
        assert add_brain_region_external_resources(nwbfile) == 2
        assert add_brain_region_external_resources(nwbfile) == 0
        assert len(nwbfile.external_resources.entities[:]) == 2

    def test_extends_existing_herd_in_place(self):
        from hdmf.common import HERD
        from pynwb import get_type_map

        nwbfile = _make_nwbfile()
        _add_electrodes(nwbfile, ["CA1"])
        herd = HERD(type_map=get_type_map())
        herd.add_ref(
            container=nwbfile.subject,
            attribute="subject_id",
            key="s1",
            entity_id="EXAMPLE:1",
            entity_uri="https://example.org/1",
        )
        nwbfile.external_resources = herd

        assert add_brain_region_external_resources(nwbfile) == 1
        assert nwbfile.external_resources is herd  # extended in place, not replaced
        assert len(herd.entities[:]) == 2

    def test_round_trips_through_file(self, tmp_path):
        from pynwb import NWBHDF5IO

        nwbfile = _make_nwbfile()
        _add_electrodes(nwbfile, ["CA1", "VISp"])
        add_brain_region_external_resources(nwbfile)

        path = tmp_path / "brain_region_herd.nwb"
        with NWBHDF5IO(path, "w") as io:
            io.write(nwbfile)
        with NWBHDF5IO(path, "r") as io:
            read_nwbfile = io.read()
            dataframe = read_nwbfile.external_resources.to_dataframe()

        assert sorted(dataframe["key"].tolist()) == ["CA1", "VISp"]
        assert set(dataframe["entity_id"].tolist()) == {"MBA:382", "MBA:385"}


def _optical_channel():
    from pynwb.ophys import OpticalChannel

    return OpticalChannel(name="channel0", description="d", emission_lambda=500.0)
