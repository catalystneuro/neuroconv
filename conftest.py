"""Temporary diagnostic scaffolding for the ndx-pose namespace flake.

Delete this file once the flake is identified. It exists to answer one question and nothing else.

A `PoseEstimation` build intermittently fails in CI with
`AttributeError("'NoneType' object has no attribute 'get_attribute'")`, raised where `ndx-pose` reads
`source_software` off the spec it was handed. The crash names whichever pose doctest happened to run
after the damage was done, which is never the test that did it, and the failure has not reproduced
locally in any configuration tried. Checking the invariant after every test names the culprit directly.

The dump below fired for the first time on run 33227570960 and showed what that spec is: the core
`NWBDataInterface` spec, not a damaged `PoseEstimation` one. `TypeMap.get_map` picks the mapper class and
the spec through two different registries, so once `ndx_pose.PoseEstimation` goes missing from the class
to (namespace, data type) map, the data type resolves up the method resolution order to
`NWBDataInterface` while the mapper class is still `PoseEstimationMap`. The teardown check below reads
that registry rather than the namespace catalog, which is intact in every sighting.

Background and everything ruled out so far: `ongoing_work/pose/ndx_pose_namespace_flake.md` in the vault.
"""

import doctest
import sys

import pytest

_already_reported = False
_first_seen_pose_estimation_class = None


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item):
    """Report the first test that unregisters the ndx-pose PoseEstimation class."""
    global _already_reported, _first_seen_pose_estimation_class

    if _already_reported or "ndx_pose" not in sys.modules:
        return

    import ndx_pose
    from pynwb import get_type_map

    # `copy=False` is the live global map. The default rebuilds the whole map through `merge`, which
    # would both hide a problem in the global map and cost real time once per test across the suite.
    type_map = get_type_map(copy=False)

    if _first_seen_pose_estimation_class is None:
        _first_seen_pose_estimation_class = ndx_pose.PoseEstimation

    # Both generations are checked. A test that clears `ndx_pose` out of `sys.modules` makes the next
    # import build a second `PoseEstimation` class and evicts the first, and the currently imported class
    # looks healthy afterwards while anything still holding the first builds against an ancestor's spec.
    candidates = {
        "the class first seen in this process": _first_seen_pose_estimation_class,
        "the class imported now": ndx_pose.PoseEstimation,
    }
    for description, container_class in candidates.items():
        resolved = type_map.get_container_cls_dt(container_class)
        if resolved == ("ndx-pose", "PoseEstimation"):
            continue

        # Reached privately because hdmf exposes no accessor for the forward map. The class it holds is
        # what separates an eviction, where a second generation replaced the first, from a namespace that
        # never registered a real class and left a `TypeSource` placeholder behind.
        forward_map = getattr(type_map, "_TypeMap__ns_dt_to_container_cls", {})
        registered_class = forward_map.get("ndx-pose", {}).get("PoseEstimation")

        _already_reported = True
        pytest.fail(
            f"{item.nodeid} left {description} resolving to {resolved} rather than "
            f"('ndx-pose', 'PoseEstimation'), so a PoseEstimation build is handed the spec of whichever "
            f"ancestor is still registered. Checked {container_class!r} at {id(container_class)}; the "
            f"class registered for ndx-pose/PoseEstimation is {registered_class!r} at "
            f"{id(registered_class)}; the class imported now is {ndx_pose.PoseEstimation!r} at "
            f"{id(ndx_pose.PoseEstimation)}."
        )


def _unwrap_error(error):
    """Return the (error, traceback) a doctest wrapper is carrying, or the error itself.

    Every sighting so far has landed on a doctest, and a doctest item raises
    `doctest.UnexpectedException` rather than the error inside it, so a filter on the exception the hook
    receives never matches.
    """
    if isinstance(error, doctest.UnexpectedException):
        return error.exc_info[1], error.exc_info[2]

    for failure in getattr(error, "failures", None) or []:  # MultipleDoctestFailures
        exc_info = getattr(failure, "exc_info", None)
        if exc_info is not None:
            return exc_info[1], exc_info[2]

    return error, error.__traceback__


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    """Attach the spec the mapper was handed to the report, at the moment the flake fires.

    The teardown sentinel above watches the global type map and has stayed silent through two runs where
    this crash still happened, which says the damaged spec is not the registered one. What is left is the
    deep copy the write path makes, so the question this answers is whether the mapper's spec is the
    global object or a copy that diverged from it. Comparing the two ``id`` values settles it.

    This has to be `pytest_runtest_makereport` rather than `pytest_exception_interact`, and the text has
    to go out through `report.sections` rather than a `print`: the suite always runs under xdist, a
    worker's stdout is not forwarded to the master, and `pytest_exception_interact` runs after
    `pytest_runtest_logreport` has already shipped the report.
    """
    report = yield
    if call.excinfo is None:
        return report

    error, traceback = _unwrap_error(call.excinfo.value)
    if not isinstance(error, AttributeError) or "get_attribute" not in str(error):
        return report

    lines = []
    try:
        while traceback is not None:
            mapper = traceback.tb_frame.f_locals.get("self")
            spec = getattr(mapper, "spec", None)
            if spec is not None and hasattr(spec, "get_dataset"):
                declared_datasets = [dataset.get("name") for dataset in spec.get("datasets", [])]
                lines.append(f"mapper spec id={id(spec)} type={spec.get('neurodata_type_def')}")
                lines.append(f"mapper spec datasets={declared_datasets}")
                lines.append(f"mapper spec get_dataset('source_software')={spec.get_dataset('source_software')}")
            traceback = traceback.tb_next

        from pynwb import get_type_map

        catalog = get_type_map(copy=False).namespace_catalog
        lines.append(f"global namespaces={sorted(catalog.namespaces)}")
        if "ndx-pose" in catalog.namespaces:
            global_spec = catalog.get_spec("ndx-pose", "PoseEstimation")
            lines.append(f"global spec id={id(global_spec)}")
            lines.append(f"global get_dataset('source_software')={global_spec.get_dataset('source_software')}")
            lines.append(f"global ndx-pose version={catalog.get_namespace('ndx-pose').get('version')}")
        lines.append(f"ndx_pose module={getattr(sys.modules.get('ndx_pose'), '__file__', None)}")
    except Exception as dump_failure:  # noqa: BLE001 - a diagnostic must never mask the real failure
        lines.append(f"dump failed: {dump_failure!r}")

    report.sections.append(("ndx-pose flake dump", "\n".join(lines)))
    return report
