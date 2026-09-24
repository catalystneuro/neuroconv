"""Ontology annotation of ``ndx-pose`` skeleton node names (general anatomy, UBERON).

These live here rather than in ``tests/test_minimal`` because they need ``ndx-pose``, which the behavior
test job installs.
"""

from datetime import datetime

import pytest
from dateutil.tz import tzutc
from ndx_pose import Skeleton, Skeletons
from pynwb import NWBFile
from pynwb.file import Subject

from neuroconv.tools.ontology import (
    add_anatomy_external_resources,
    get_anatomy_term,
    infer_anatomy_ontology_metadata,
    infer_species_ontology_metadata,
)
from neuroconv.tools.testing.mock_interfaces import MockPoseEstimationInterface


def _make_nwbfile(species="Mus musculus") -> NWBFile:
    nwbfile = NWBFile(session_description="d", identifier="id", session_start_time=datetime(2020, 1, 1, tzinfo=tzutc()))
    nwbfile.subject = Subject(subject_id="s1", species=species)
    return nwbfile


def _add_skeleton(nwbfile: NWBFile, node_names, name="skeleton0"):
    skeleton = Skeleton(name=name, nodes=list(node_names), edges=None)
    behavior_module = nwbfile.processing.get("behavior") or nwbfile.create_processing_module(
        name="behavior", description="d"
    )
    if "Skeletons" not in behavior_module.data_interfaces:
        behavior_module.add(Skeletons(skeletons=[skeleton]))
    else:
        behavior_module["Skeletons"].add_skeletons(skeleton)
    return skeleton


def _anatomy_metadata(mapping: dict) -> dict:
    """A metadata dict carrying a file-wide ``ontology.anatomy`` map."""
    return {"ontology": {"anatomy": mapping}}


# ---------------------------------------------------------------------------
# Anatomy ontology inference (file + metadata -> metadata)
# ---------------------------------------------------------------------------


class TestInferAnatomyOntologyMetadata:
    def test_skeleton_node_names_are_resolved(self):
        nwbfile = _make_nwbfile()
        _add_skeleton(nwbfile, ["Snout", "Shoulder", "EarL"])
        metadata = {}

        infer_anatomy_ontology_metadata(nwbfile, metadata)
        anatomy = metadata["ontology"]["anatomy"]
        assert anatomy["Snout"]["id"] == get_anatomy_term("Snout").curie
        assert anatomy["Shoulder"]["id"] == get_anatomy_term("Shoulder").curie
        assert "EarL" not in anatomy  # unresolved (lab-specific, laterality marker) is skipped

    def test_no_skeleton_is_a_noop(self):
        nwbfile = _make_nwbfile()
        metadata = {}
        infer_anatomy_ontology_metadata(nwbfile, metadata)
        assert metadata == {}

    def test_existing_user_term_is_not_overwritten(self):
        nwbfile = _make_nwbfile()
        _add_skeleton(nwbfile, ["Snout"])
        curated = {"id": "UBERON:9999999", "uri": "https://example.org/custom"}
        metadata = _anatomy_metadata({"Snout": curated})

        infer_anatomy_ontology_metadata(nwbfile, metadata)
        assert metadata["ontology"]["anatomy"]["Snout"] == curated


# ---------------------------------------------------------------------------
# General-anatomy HERD annotation (metadata -> file)
# ---------------------------------------------------------------------------


class TestAnatomyExternalResources:
    def test_noop_without_metadata(self):
        nwbfile = _make_nwbfile()
        _add_skeleton(nwbfile, ["Snout"])
        assert add_anatomy_external_resources(nwbfile) == 0
        assert nwbfile.external_resources is None

    def test_noop_when_metadata_covers_no_present_node(self):
        nwbfile = _make_nwbfile()
        _add_skeleton(nwbfile, ["Snout", "EarL"])
        metadata = _anatomy_metadata({"some other node": {"id": "UBERON:1", "uri": "https://example.org/1"}})
        assert add_anatomy_external_resources(nwbfile, metadata=metadata) == 0
        assert nwbfile.external_resources is None

    def test_skeleton_nodes_are_annotated(self):
        nwbfile = _make_nwbfile()
        skeleton = _add_skeleton(nwbfile, ["Snout", "Snout", "EarL", "Shoulder"])  # duplicates collapse
        metadata = _anatomy_metadata(
            {
                "Snout": {"id": "UBERON:0006333", "uri": "https://example.org/UBERON_0006333"},
                "Shoulder": {"id": "UBERON:0001467", "uri": "https://example.org/UBERON_0001467"},
            }
        )

        assert add_anatomy_external_resources(nwbfile, metadata=metadata) == 2
        dataframe = nwbfile.external_resources.to_dataframe()
        by_key = dict(zip(dataframe["key"], dataframe["entity_id"]))
        assert by_key == {"Snout": "UBERON:0006333", "Shoulder": "UBERON:0001467"}

        # HERD records the reference against the Skeleton itself (nodes is a plain array
        # attribute, not a separate VectorData column); both keys share that one object row.
        objects = nwbfile.external_resources.objects.to_dataframe()
        assert objects["object_id"].tolist() == [skeleton.object_id]
        assert objects["relative_path"].tolist() == ["nodes"]

    def test_multiple_skeletons_are_all_annotated(self):
        nwbfile = _make_nwbfile()
        _add_skeleton(nwbfile, ["Snout"], name="skeleton_rat1")
        _add_skeleton(nwbfile, ["Tail"], name="skeleton_rat2")
        metadata = _anatomy_metadata(
            {
                "Snout": {"id": "UBERON:0006333", "uri": "https://example.org/UBERON_0006333"},
                "Tail": {"id": "UBERON:0002415", "uri": "https://example.org/UBERON_0002415"},
            }
        )

        assert add_anatomy_external_resources(nwbfile, metadata=metadata) == 2
        dataframe = nwbfile.external_resources.to_dataframe()
        assert sorted(dataframe["key"].tolist()) == ["Snout", "Tail"]

    def test_maps_one_node_to_multiple_ontology_terms(self):
        nwbfile = _make_nwbfile()
        _add_skeleton(nwbfile, ["Snout"])
        metadata = _anatomy_metadata(
            {
                "Snout": [
                    {"id": "UBERON:0006333", "uri": "http://purl.obolibrary.org/obo/UBERON_0006333"},
                    {"id": "EXAMPLE:1", "uri": "https://example.org/1"},
                ]
            }
        )

        assert add_anatomy_external_resources(nwbfile, metadata=metadata) == 2
        dataframe = nwbfile.external_resources.to_dataframe()
        assert sorted(dataframe["entity_id"].tolist()) == ["EXAMPLE:1", "UBERON:0006333"]

    @pytest.mark.parametrize(
        "bad_value",
        ["UBERON:0006333", {"id": "UBERON:0006333"}, {"uri": "https://example.org/1"}, {"id": "", "uri": ""}],
    )
    def test_malformed_metadata_term_raises(self, bad_value):
        nwbfile = _make_nwbfile()
        _add_skeleton(nwbfile, ["Snout"])
        metadata = _anatomy_metadata({"Snout": bad_value})
        with pytest.raises((TypeError, ValueError)):
            add_anatomy_external_resources(nwbfile, metadata=metadata)

    def test_idempotent(self):
        nwbfile = _make_nwbfile()
        _add_skeleton(nwbfile, ["Snout", "Tail"])
        metadata = _anatomy_metadata(
            {
                "Snout": {"id": "UBERON:0006333", "uri": "https://example.org/UBERON_0006333"},
                "Tail": {"id": "UBERON:0002415", "uri": "https://example.org/UBERON_0002415"},
            }
        )
        assert add_anatomy_external_resources(nwbfile, metadata=metadata) == 2
        assert add_anatomy_external_resources(nwbfile, metadata=metadata) == 0
        assert len(nwbfile.external_resources.entities[:]) == 2

    def test_extends_existing_herd_in_place(self):
        from hdmf.common import HERD
        from pynwb import get_type_map

        nwbfile = _make_nwbfile()
        _add_skeleton(nwbfile, ["Snout"])
        herd = HERD(type_map=get_type_map())
        herd.add_ref(
            container=nwbfile.subject,
            attribute="subject_id",
            key="s1",
            entity_id="EXAMPLE:1",
            entity_uri="https://example.org/1",
        )
        nwbfile.external_resources = herd

        metadata = _anatomy_metadata({"Snout": {"id": "UBERON:0006333", "uri": "https://example.org/UBERON_0006333"}})
        assert add_anatomy_external_resources(nwbfile, metadata=metadata) == 1
        assert nwbfile.external_resources is herd  # extended in place, not replaced
        assert len(herd.entities[:]) == 2


# ---------------------------------------------------------------------------
# Conversion pipeline: infer -> create_nwbfile writes the stated anatomy terms
# ---------------------------------------------------------------------------


class TestAnatomyConversionPipeline:
    def test_inferred_anatomy_terms_are_written_through_create_nwbfile(self):
        interface = MockPoseEstimationInterface(num_nodes=3)  # nodes: head, neck, left_shoulder
        metadata = interface.get_metadata()
        metadata["Subject"] = dict(subject_id="m1", species="Mus musculus", sex="M", age="P30D")

        # Inference needs the populated file to see the skeleton node names.
        staging_nwbfile = interface.create_nwbfile(metadata=metadata)
        infer_species_ontology_metadata(metadata)
        infer_anatomy_ontology_metadata(staging_nwbfile, metadata)

        nwbfile = interface.create_nwbfile(metadata=metadata)
        entity_ids = set(nwbfile.external_resources.to_dataframe()["entity_id"].tolist())
        assert "NCBITaxon:10090" in entity_ids
        assert {"UBERON:0000033", "UBERON:0000974"}.issubset(entity_ids)  # head, neck
