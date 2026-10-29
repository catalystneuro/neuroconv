"""External-resource annotation of ``ndx-pose`` skeleton node names (anatomy).

These live here rather than in ``tests/test_minimal`` because they need ``ndx-pose``, which the behavior
test job installs.
"""

from datetime import datetime

import pytest
from dateutil.tz import tzutc
from ndx_pose import Skeleton, Skeletons
from pynwb import NWBFile

from neuroconv.tools.external_resources import add_external_resources_to_nwbfile
from neuroconv.tools.testing.mock_interfaces import MockPoseEstimationInterface

SNOUT_TERM = {"id": "UBERON:0006333", "uri": "http://purl.obolibrary.org/obo/UBERON_0006333"}
NOSE_TIP_TERM = {"id": "UBERON:0012128", "uri": "http://purl.obolibrary.org/obo/UBERON_0012128"}
SHOULDER_TERM = {"id": "UBERON:0001467", "uri": "http://purl.obolibrary.org/obo/UBERON_0001467"}
TAIL_TERM = {"id": "UBERON:0002415", "uri": "http://purl.obolibrary.org/obo/UBERON_0002415"}


def _make_nwbfile() -> NWBFile:
    return NWBFile(session_description="d", identifier="id", session_start_time=datetime(2020, 1, 1, tzinfo=tzutc()))


def _add_skeleton(nwbfile: NWBFile, node_names, name="skeleton0", module_name="behavior"):
    skeleton = Skeleton(name=name, nodes=list(node_names), edges=None)
    behavior_module = nwbfile.processing.get(module_name) or nwbfile.create_processing_module(
        name=module_name, description="d"
    )
    if "Skeletons" not in behavior_module.data_interfaces:
        behavior_module.add(Skeletons(skeletons=[skeleton]))
    else:
        behavior_module["Skeletons"].add_skeletons(skeleton)
    return skeleton


def _anatomy_metadata(mapping: dict) -> dict:
    """A metadata dict carrying a file-wide ``ExternalResources.anatomy`` map."""
    return {"ExternalResources": {"anatomy": mapping}}


class TestAnatomyExternalResources:
    @pytest.mark.parametrize(
        "metadata",
        [None, _anatomy_metadata({"some other node": TAIL_TERM})],
        ids=["no_metadata", "no_present_node"],
    )
    def test_noop_cases(self, metadata):
        nwbfile = _make_nwbfile()
        _add_skeleton(nwbfile, ["Snout", "EarL"])
        assert add_external_resources_to_nwbfile(nwbfile, metadata=metadata) == 0
        assert nwbfile.external_resources is None

    def test_skeleton_nodes_are_annotated(self):
        nwbfile = _make_nwbfile()
        skeleton = _add_skeleton(nwbfile, ["Snout", "Snout", "EarL", "Shoulder"])  # duplicates collapse
        metadata = _anatomy_metadata({"Snout": SNOUT_TERM, "Shoulder": SHOULDER_TERM})

        assert add_external_resources_to_nwbfile(nwbfile, metadata=metadata) == 2
        dataframe = nwbfile.external_resources.to_dataframe()
        assert dict(zip(dataframe["key"], dataframe["entity_id"])) == {
            "Snout": "UBERON:0006333",
            "Shoulder": "UBERON:0001467",
        }
        # HERD records the reference against the Skeleton itself (nodes is a plain array attribute, not a
        # separate VectorData column); both keys share that one object row.
        objects = nwbfile.external_resources.objects.to_dataframe()
        assert objects["object_id"].tolist() == [skeleton.object_id]
        assert objects["relative_path"].tolist() == ["nodes"]
        # Idempotent.
        assert add_external_resources_to_nwbfile(nwbfile, metadata=metadata) == 0

    def test_multiple_skeletons_are_all_annotated(self):
        nwbfile = _make_nwbfile()
        _add_skeleton(nwbfile, ["Snout"], name="skeleton_rat1")
        _add_skeleton(nwbfile, ["Tail"], name="skeleton_rat2")
        metadata = _anatomy_metadata({"Snout": SNOUT_TERM, "Tail": TAIL_TERM})

        assert add_external_resources_to_nwbfile(nwbfile, metadata=metadata) == 2
        dataframe = nwbfile.external_resources.to_dataframe()
        assert sorted(dataframe["key"].tolist()) == ["Snout", "Tail"]

    def test_skeletons_sharing_node_names_are_each_annotated(self, tmp_path):
        # Several animals tracked with the same skeleton: each Skeleton gets its own reference per node.
        from pynwb import NWBHDF5IO

        nwbfile = _make_nwbfile()
        skeleton_mouse1 = _add_skeleton(nwbfile, ["Snout", "Tail"], name="skeleton_mouse1")
        skeleton_mouse2 = _add_skeleton(nwbfile, ["Snout", "Tail"], name="skeleton_mouse2")
        metadata = _anatomy_metadata({"Snout": SNOUT_TERM, "Tail": TAIL_TERM})

        assert add_external_resources_to_nwbfile(nwbfile, metadata=metadata) == 4
        # Idempotent.
        assert add_external_resources_to_nwbfile(nwbfile, metadata=metadata) == 0

        path = tmp_path / "shared_nodes.nwb"
        with NWBHDF5IO(path, "w") as io:
            io.write(nwbfile)
        with NWBHDF5IO(path, "r") as io:
            dataframe = io.read().external_resources.to_dataframe()
        assert set(zip(dataframe["object_id"], dataframe["key"], dataframe["entity_id"])) == {
            (skeleton_mouse1.object_id, "Snout", "UBERON:0006333"),
            (skeleton_mouse1.object_id, "Tail", "UBERON:0002415"),
            (skeleton_mouse2.object_id, "Snout", "UBERON:0006333"),
            (skeleton_mouse2.object_id, "Tail", "UBERON:0002415"),
        }

    def test_several_terms_share_one_key(self):
        nwbfile = _make_nwbfile()
        _add_skeleton(nwbfile, ["Snout"])
        metadata = _anatomy_metadata({"Snout": [SNOUT_TERM, NOSE_TIP_TERM]})

        assert add_external_resources_to_nwbfile(nwbfile, metadata=metadata) == 2
        herd = nwbfile.external_resources
        assert herd.keys.to_dataframe()["key"].tolist() == ["Snout"]
        assert herd.to_dataframe()["entity_id"].tolist() == ["UBERON:0006333", "UBERON:0012128"]

    def test_skeleton_outside_the_behavior_module_is_annotated(self):
        nwbfile = _make_nwbfile()
        skeleton = _add_skeleton(nwbfile, ["Snout"], module_name="pose")
        metadata = _anatomy_metadata({"Snout": SNOUT_TERM})

        assert add_external_resources_to_nwbfile(nwbfile, metadata=metadata) == 1
        objects = nwbfile.external_resources.objects.to_dataframe()
        assert objects["object_id"].tolist() == [skeleton.object_id]


class TestAnatomyConversionPipeline:
    def test_run_conversion_writes_anatomy_references(self, tmp_path):
        from pynwb import NWBHDF5IO

        interface = MockPoseEstimationInterface(num_nodes=3)  # nodes: head, neck, left_shoulder
        metadata = interface.get_metadata()
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
