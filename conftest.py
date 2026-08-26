"""Temporary diagnostic scaffolding for the ndx-pose namespace flake.

Delete this file once the flake is identified. It exists to answer one question and nothing else.

A `PoseEstimation` build intermittently fails in CI with
`AttributeError("'NoneType' object has no attribute 'get_attribute'")`, raised where `ndx-pose` reads
`source_software` off the spec it was handed. The crash names whichever pose doctest happened to run
after the damage was done, which is never the test that did it, and the failure has not reproduced
locally in any configuration tried. Checking the invariant after every test names the culprit directly.

Background and everything ruled out so far: `ongoing_work/pose/ndx_pose_namespace_flake.md` in the vault.
"""

import sys

import pytest

_already_reported = False


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item):
    """Report the first test that leaves the global ndx-pose spec unusable."""
    global _already_reported

    if _already_reported or "ndx_pose" not in sys.modules:
        return

    from pynwb import get_type_map

    # `copy=False` is the live global map. The default deep-copies, which would both hide a problem in
    # the global map and cost real time once per test across the whole suite.
    catalog = get_type_map(copy=False).namespace_catalog

    if "ndx-pose" not in catalog.namespaces:
        _already_reported = True
        pytest.fail(f"{item.nodeid} left no ndx-pose namespace in the global type map.")

    spec = catalog.get_spec("ndx-pose", "PoseEstimation")
    if spec.get_dataset("source_software") is None:
        _already_reported = True
        declared_datasets = [dataset.get("name") for dataset in spec.get("datasets", [])]
        pytest.fail(
            f"{item.nodeid} left the ndx-pose PoseEstimation spec without a reachable source_software "
            f"dataset. Datasets present in the spec dictionary: {declared_datasets}. "
            f"Namespace version: {catalog.get_namespace('ndx-pose').get('version')}."
        )
