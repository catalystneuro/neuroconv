"""Tests for attaching strain (RRID) ontology references (HERD) to NWB files."""

from datetime import datetime

import pytest
from dateutil.tz import tzutc
from pynwb import NWBFile
from pynwb.file import Subject

from neuroconv.tools.ontology import add_strain_external_resource


def _make_nwbfile(species="Rattus norvegicus", strain=None, with_subject=True) -> NWBFile:
    nwbfile = NWBFile(
        session_description="d",
        identifier="id",
        session_start_time=datetime(2020, 1, 1, tzinfo=tzutc()),
    )
    if with_subject:
        nwbfile.subject = Subject(subject_id="s1", species=species, strain=strain)
    return nwbfile


class TestAddStrainExternalResourceNoOps:
    def test_no_subject(self):
        nwbfile = _make_nwbfile(with_subject=False)
        assert add_strain_external_resource(nwbfile) is False
        assert nwbfile.external_resources is None

    def test_strain_is_none(self):
        nwbfile = _make_nwbfile(strain=None)
        assert add_strain_external_resource(nwbfile) is False
        assert nwbfile.external_resources is None

    def test_unrecognized_strain(self):
        nwbfile = _make_nwbfile(strain="a custom in-house line")
        assert add_strain_external_resource(nwbfile) is False
        assert nwbfile.external_resources is None


class TestAddStrainExternalResource:
    def test_recognized_strain_is_annotated(self):
        nwbfile = _make_nwbfile(strain="Long-Evans")
        assert add_strain_external_resource(nwbfile) is True

        dataframe = nwbfile.external_resources.to_dataframe()
        assert dataframe["key"].tolist() == ["Long-Evans"]
        assert dataframe["entity_id"].tolist() == ["RRID:RGD_2308852"]
        assert dataframe["entity_uri"].tolist() == ["https://scicrunch.org/resolver/RRID:RGD_2308852"]

    def test_reference_points_at_subject_strain(self):
        nwbfile = _make_nwbfile(species="Mus musculus", strain="C57BL/6J")
        add_strain_external_resource(nwbfile)

        objects = nwbfile.external_resources.objects.to_dataframe()
        assert objects["object_id"].tolist() == [nwbfile.subject.object_id]
        assert objects["relative_path"].tolist() == ["strain"]

    def test_idempotent(self):
        nwbfile = _make_nwbfile(strain="Long-Evans")
        assert add_strain_external_resource(nwbfile) is True
        assert add_strain_external_resource(nwbfile) is False
        assert len(nwbfile.external_resources.entities[:]) == 1

    def test_extends_existing_herd_in_place(self):
        from hdmf.common import HERD
        from pynwb import get_type_map

        nwbfile = _make_nwbfile(strain="Long-Evans")
        herd = HERD(type_map=get_type_map())
        herd.add_ref(
            container=nwbfile.subject,
            attribute="subject_id",
            key="s1",
            entity_id="EXAMPLE:1",
            entity_uri="https://example.org/1",
        )
        nwbfile.external_resources = herd

        assert add_strain_external_resource(nwbfile) is True
        assert nwbfile.external_resources is herd  # extended in place, not replaced
        assert len(herd.entities[:]) == 2

    def test_composes_with_species_annotation(self):
        from neuroconv.tools.ontology import add_species_external_resource

        nwbfile = _make_nwbfile(species="Rattus norvegicus", strain="Long-Evans")
        assert add_species_external_resource(nwbfile) is True
        assert add_strain_external_resource(nwbfile) is True

        dataframe = nwbfile.external_resources.to_dataframe()
        assert sorted(dataframe["key"].tolist()) == ["Long-Evans", "Rattus norvegicus"]

    def test_round_trips_through_file(self, tmp_path):
        from pynwb import NWBHDF5IO

        nwbfile = _make_nwbfile(strain="Long-Evans")
        add_strain_external_resource(nwbfile)

        path = tmp_path / "strain_herd.nwb"
        with NWBHDF5IO(path, "w") as io:
            io.write(nwbfile)
        with NWBHDF5IO(path, "r") as io:
            read_nwbfile = io.read()
            dataframe = read_nwbfile.external_resources.to_dataframe()

        assert dataframe["key"].tolist() == ["Long-Evans"]
        assert dataframe["entity_id"].tolist() == ["RRID:RGD_2308852"]


class TestMetadataMapping:
    def test_metadata_mapping_annotates_unrecognized_strain(self):
        nwbfile = _make_nwbfile(strain="an in-house line")
        metadata = {"Strain": {"an in-house line": {"id": "RRID:EXAMPLE:1", "uri": "https://example.org/1"}}}

        assert add_strain_external_resource(nwbfile, metadata=metadata) is True
        dataframe = nwbfile.external_resources.to_dataframe()
        assert dataframe["key"].tolist() == ["an in-house line"]
        assert dataframe["entity_id"].tolist() == ["RRID:EXAMPLE:1"]
        assert dataframe["entity_uri"].tolist() == ["https://example.org/1"]

    def test_metadata_mapping_takes_precedence_over_offline_lookup(self):
        nwbfile = _make_nwbfile(strain="Long-Evans")
        # Override the curated result (RRID:RGD_2308852) with an explicit term.
        metadata = {"Strain": {"Long-Evans": {"id": "RRID:EXAMPLE:2", "uri": "https://example.org/2"}}}

        add_strain_external_resource(nwbfile, metadata=metadata)
        dataframe = nwbfile.external_resources.to_dataframe()
        assert dataframe["entity_id"].tolist() == ["RRID:EXAMPLE:2"]

    def test_maps_strain_to_multiple_ontology_terms(self):
        nwbfile = _make_nwbfile(strain="Long-Evans")
        metadata = {
            "Strain": {
                "Long-Evans": [
                    {"id": "RRID:RGD_2308852", "uri": "https://scicrunch.org/resolver/RRID:RGD_2308852"},
                    {"id": "RRID:EXAMPLE:3", "uri": "https://example.org/3"},
                ]
            }
        }

        assert add_strain_external_resource(nwbfile, metadata=metadata) is True
        dataframe = nwbfile.external_resources.to_dataframe()
        assert dataframe["key"].tolist() == ["Long-Evans", "Long-Evans"]
        assert sorted(dataframe["entity_id"].tolist()) == ["RRID:EXAMPLE:3", "RRID:RGD_2308852"]

    def test_metadata_mapping_without_matching_entry_falls_back_to_offline_lookup(self):
        nwbfile = _make_nwbfile(strain="Long-Evans")
        metadata = {"Strain": {"a different strain": {"id": "RRID:EXAMPLE:4", "uri": "https://example.org/4"}}}

        assert add_strain_external_resource(nwbfile, metadata=metadata) is True
        dataframe = nwbfile.external_resources.to_dataframe()
        assert dataframe["entity_id"].tolist() == ["RRID:RGD_2308852"]

    @pytest.mark.parametrize(
        "bad_value",
        ["RRID:EXAMPLE:1", {"id": "RRID:EXAMPLE:1"}, {"uri": "https://example.org/1"}, {"id": "", "uri": ""}],
    )
    def test_malformed_metadata_term_raises(self, bad_value):
        nwbfile = _make_nwbfile(strain="a strain")
        metadata = {"Strain": {"a strain": bad_value}}
        with pytest.raises((TypeError, ValueError)):
            add_strain_external_resource(nwbfile, metadata=metadata)
