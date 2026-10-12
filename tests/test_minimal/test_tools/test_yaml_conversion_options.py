from neuroconv.tools.yaml_conversion_specification._yaml_conversion_specification import (
    _resolve_conversion_options,
)


def test_global_conversion_options_reach_every_interface():
    conversion_options = _resolve_conversion_options(
        interface_names=["ap", "lf"],
        global_conversion_options=dict(stub_test=True),
        session_conversion_options=dict(),
    )
    assert conversion_options == dict(ap=dict(stub_test=True), lf=dict(stub_test=True))


def test_session_conversion_options_override_global_ones():
    # The more specific level wins, as it does for metadata: the session turns stub_test off for one interface
    # and adds an option of its own, and the other interface keeps the global value.
    conversion_options = _resolve_conversion_options(
        interface_names=["ap", "lf"],
        global_conversion_options=dict(stub_test=True),
        session_conversion_options=dict(ap=dict(stub_test=False, iterator_type=None)),
    )
    assert conversion_options == dict(ap=dict(stub_test=False, iterator_type=None), lf=dict(stub_test=True))


def test_session_conversion_options_for_an_absent_interface_are_ignored():
    conversion_options = _resolve_conversion_options(
        interface_names=["ap"],
        global_conversion_options=dict(),
        session_conversion_options=dict(phy=dict(stub_test=True)),
    )
    assert conversion_options == dict(ap=dict())
