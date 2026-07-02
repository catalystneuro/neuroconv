"""Tests for attaching ontology entity references (HERD) to NWB files."""

from datetime import datetime

from dateutil.tz import tzutc
from pynwb import NWBFile
from pynwb.file import Subject

from neuroconv.tools.ontology import add_species_external_resource


def _make_nwbfile(species=None, with_subject=True) -> NWBFile:
    nwbfile = NWBFile(
        session_description="d",
        identifier="id",
        session_start_time=datetime(2020, 1, 1, tzinfo=tzutc()),
    )
    if with_subject:
        nwbfile.subject = Subject(subject_id="s1", species=species)
    return nwbfile


class TestAddSpeciesExternalResourceNoOps:
    def test_no_subject(self):
        nwbfile = _make_nwbfile(with_subject=False)
        assert add_species_external_resource(nwbfile) is False
        assert nwbfile.external_resources is None

    def test_species_is_none(self):
        nwbfile = _make_nwbfile(species=None)
        assert add_species_external_resource(nwbfile) is False
        assert nwbfile.external_resources is None

    def test_unrecognized_species(self):
        nwbfile = _make_nwbfile(species="Octodon degus")
        assert add_species_external_resource(nwbfile) is False
        assert nwbfile.external_resources is None


class TestAddSpeciesExternalResource:
    def test_recognized_species_is_annotated(self):
        nwbfile = _make_nwbfile(species="Mus musculus")
        assert add_species_external_resource(nwbfile) is True

        dataframe = nwbfile.external_resources.to_dataframe()
        assert dataframe["key"].tolist() == ["Mus musculus"]
        assert dataframe["entity_id"].tolist() == ["NCBITaxon:10090"]
        assert dataframe["entity_uri"].tolist() == ["http://purl.obolibrary.org/obo/NCBITaxon_10090"]

    def test_reference_points_at_subject_species(self):
        nwbfile = _make_nwbfile(species="Homo sapiens")
        add_species_external_resource(nwbfile)

        objects = nwbfile.external_resources.objects.to_dataframe()
        assert objects["object_id"].tolist() == [nwbfile.subject.object_id]
        assert objects["relative_path"].tolist() == ["species"]

    def test_idempotent(self):
        nwbfile = _make_nwbfile(species="Mus musculus")
        assert add_species_external_resource(nwbfile) is True
        assert add_species_external_resource(nwbfile) is False
        assert len(nwbfile.external_resources.entities[:]) == 1

    def test_extends_existing_herd_in_place(self):
        from hdmf.common import HERD
        from pynwb import get_type_map

        nwbfile = _make_nwbfile(species="Mus musculus")
        herd = HERD(type_map=get_type_map())
        herd.add_ref(
            container=nwbfile.subject,
            attribute="subject_id",
            key="s1",
            entity_id="EXAMPLE:1",
            entity_uri="https://example.org/1",
        )
        nwbfile.external_resources = herd

        assert add_species_external_resource(nwbfile) is True
        assert nwbfile.external_resources is herd  # extended in place, not replaced
        assert len(herd.entities[:]) == 2

    def test_round_trips_through_file(self, tmp_path):
        from pynwb import NWBHDF5IO

        nwbfile = _make_nwbfile(species="Rattus norvegicus")
        add_species_external_resource(nwbfile)

        path = tmp_path / "species_herd.nwb"
        with NWBHDF5IO(path, "w") as io:
            io.write(nwbfile)
        with NWBHDF5IO(path, "r") as io:
            read_nwbfile = io.read()
            dataframe = read_nwbfile.external_resources.to_dataframe()

        assert dataframe["key"].tolist() == ["Rattus norvegicus"]
        assert dataframe["entity_id"].tolist() == ["NCBITaxon:10116"]
