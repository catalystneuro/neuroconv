"""Tests to enforce keyword-only argument conventions for add_to_nwbfile methods.

These tests ensure that all interface add_to_nwbfile methods enforce keyword-only arguments
after nwbfile and metadata. Only nwbfile and metadata should be positional.

During the deprecation period (before August 2026), methods use *args with FutureWarning.
After the deprecation period, methods should use bare * for keyword-only enforcement.

See the developer style guide for details on the convention.
"""

import inspect

import pytest

from neuroconv.datainterfaces import interface_list


@pytest.mark.parametrize(
    "interface_class",
    interface_list,
    ids=lambda cls: cls.__name__,
)
def test_add_to_nwbfile_only_nwbfile_metadata_positional(interface_class):
    """Only nwbfile and metadata should be positional in add_to_nwbfile."""
    if "add_to_nwbfile" not in interface_class.__dict__:
        pytest.skip(f"{interface_class.__name__} does not override add_to_nwbfile")

    add_to_nwbfile_method = getattr(interface_class, "add_to_nwbfile")
    sig = inspect.signature(add_to_nwbfile_method)

    # No add_to_nwbfile uses POSITIONAL_ONLY (/), so POSITIONAL_OR_KEYWORD means "can be passed positionally"
    can_be_passed_positionally = lambda param: param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
    positional_params = {name for name, param in sig.parameters.items() if can_be_passed_positionally(param)}

    allowed_positional_params = {"self", "nwbfile", "metadata"}
    assert positional_params == allowed_positional_params, (
        f"{interface_class.__name__}.add_to_nwbfile() positional parameters are {positional_params}, "
        f"expected {allowed_positional_params}. "
        f"All other parameters should be keyword-only (use * or *args)."
    )
