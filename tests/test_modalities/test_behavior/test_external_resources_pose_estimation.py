"""External-resource annotation of ``ndx-pose`` skeleton node names (general anatomy, UBERON).

These live here rather than in ``tests/test_minimal`` because they need ``ndx-pose``, which the behavior
test job installs.
"""

from datetime import datetime

import pytest
from dateutil.tz import tzutc
from ndx_pose import Skeleton, Skeletons
from pynwb import NWBFile
from pynwb.file import Subject

from neuroconv.tools.external_resources import (
    add_anatomy_external_resources,
    get_anatomy_term,
    infer_anatomy_external_resources,
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
    """A metadata dict carrying a file-wide ``ExternalResources.anatomy`` map."""
    return {"ExternalResources": {"anatomy": mapping}}


# ---------------------------------------------------------------------------
# Anatomy inference (file -> ExternalResources metadata)
# ---------------------------------------------------------------------------


class TestInferAnatomyExternalResources:
    def test_skeleton_node_names_are_resolved(self):
        nwbfile = _make_nwbfile()
        _add_skeleton(nwbfile, ["Snout", "Shoulder", "EarL"])

        anatomy = infer_anatomy_external_resources(nwbfile)["ExternalResources"]["anatomy"]
        assert anatomy["Snout"]["id"] == get_anatomy_term("Snout").curie
        assert anatomy["Shoulder"]["id"] == get_anatomy_term("Shoulder").curie
        assert "EarL" not in anatomy  # unresolved (lab-specific, laterality marker) is skipped

    def test_no_skeleton_returns_empty(self):
        assert infer_anatomy_external_resources(_make_nwbfile()) == {}


# ---------------------------------------------------------------------------
# General-anatomy HERD annotation (metadata -> file)
# ---------------------------------------------------------------------------


class TestAnatomyExternalResources:
    @pytest.mark.parametrize(
        "metadata",
        [None, _anatomy_metadata({"some other node": {"id": "UBERON:1", "uri": "https://example.org/1"}})],
        ids=["no_metadata", "no_present_node"],
    )
    def test_noop_cases(self, metadata):
        nwbfile = _make_nwbfile()
        _add_skeleton(nwbfile, ["Snout", "EarL"])
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


# ---------------------------------------------------------------------------
# Conversion pipeline: annotation at write time
# ---------------------------------------------------------------------------


class TestAnatomyConversionPipeline:
    def _pose_interface(self):
        interface = MockPoseEstimationInterface(num_nodes=3)  # nodes: head, neck, left_shoulder
        metadata = interface.get_metadata()
        metadata["Subject"] = dict(subject_id="m1", species="Mus musculus", sex="M", age="P30D")
        return interface, metadata

    def test_run_conversion_writes_anatomy_references(self, tmp_path):
        from pynwb import NWBHDF5IO

        interface, metadata = self._pose_interface()
        metadata["ExternalResources"] = {
            "anatomy": {
                "head": {"id": "UBERON:0000033", "uri": "http://purl.obolibrary.org/obo/UBERON_0000033"},
                "neck": {"id": "UBERON:0000974", "uri": "http://purl.obolibrary.org/obo/UBERON_0000974"},
            }
        }
        path = tmp_path / "pose.nwb"
        interface.run_conversion(nwbfile_path=path, metadata=metadata)

        with NWBHDF5IO(path, "r") as io:
            dataframe = io.read().external_resources.to_dataframe()
        assert set(zip(dataframe["object_type"], dataframe["key"], dataframe["entity_id"])) == {
            ("Skeleton", "head", "UBERON:0000033"),
            ("Skeleton", "neck", "UBERON:0000974"),
        }
