"""Unit tests for the shared signal-encoded events configuration grammar.

These cover ``detection_configuration`` itself, not any one format: no file is read, no signal is
discovered, and no event is written. ``available_signals`` stands in for whatever an interface's
discovery produced, since the validator only reads its keys. Format behaviour lives in the per-interface
tests on real data.
"""

import pytest

from neuroconv.tools.events import (
    resolve_detection_plan,
    validate_detection_configuration,
)

AVAILABLE_SIGNALS = {"DI/O-1": {"column": ("Digital I/O", "DI/O-1")}, "DI/O-2": {"column": ("Digital I/O", "DI/O-2")}}


class TestValidateDetectionConfiguration:
    """The construction-time checks: a spec is all-or-nothing and a signal's value is always a list."""

    def test_valid_configuration_passes(self):
        validate_detection_configuration(
            {"DI/O-1": [{"detection": "high_period"}], "DI/O-2": [{"detection": "rising", "event_name": "Lick"}]},
            AVAILABLE_SIGNALS,
        )

    def test_empty_configuration_raises(self):
        """``{}`` is distinct from ``None``: it selects nothing, which is always a mistake."""
        with pytest.raises(ValueError, match="detection_configuration is empty"):
            validate_detection_configuration({}, AVAILABLE_SIGNALS)

    def test_unknown_signal_raises(self):
        with pytest.raises(ValueError, match="not one of the file's signals"):
            validate_detection_configuration({"DI/O-9": [{"detection": "rising"}]}, AVAILABLE_SIGNALS)

    def test_bare_dict_instead_of_list_raises(self):
        """A signal's value is always a list, since a signal may yield several event types."""
        with pytest.raises(ValueError, match="must be a list of detection specs"):
            validate_detection_configuration({"DI/O-1": {"detection": "rising"}}, AVAILABLE_SIGNALS)

    def test_empty_spec_list_raises(self):
        """Drop the signal to skip it; an empty list says nothing."""
        with pytest.raises(ValueError, match="is an empty list"):
            validate_detection_configuration({"DI/O-1": []}, AVAILABLE_SIGNALS)

    def test_spec_without_detection_raises(self):
        """A half-filled spec is an error rather than a silent fallback to the default reading."""
        with pytest.raises(ValueError, match="does not set 'detection'"):
            validate_detection_configuration({"DI/O-1": [{}]}, AVAILABLE_SIGNALS)

    def test_unrecognized_spec_key_raises(self):
        """A stray or misspelled key fails loudly instead of being accepted and never read."""
        with pytest.raises(ValueError, match="unrecognized key"):
            validate_detection_configuration({"DI/O-1": [{"detection": "rising", "threshold": 0.4}]}, AVAILABLE_SIGNALS)

    def test_detection_value_is_not_checked_here(self):
        """``_detect_events`` owns the reading vocabulary and raises on an invalid one, so this does not."""
        validate_detection_configuration({"DI/O-1": [{"detection": "not_a_reading"}]}, AVAILABLE_SIGNALS)


class TestResolveDetectionPlan:
    """Identifier derivation: one spec keeps the signal's handle, several fan out."""

    def test_one_spec_keeps_the_signal_handle(self):
        """Rule 1 keeps a zero-configuration conversion's identifiers equal to the acquisition strings."""
        detection_plan = resolve_detection_plan({"DI/O-1": [{"detection": "high_period"}]})

        assert detection_plan == {"DI/O-1": [("DI/O-1", {"detection": "high_period"})]}

    def test_several_specs_fan_out_on_the_reading(self):
        detection_plan = resolve_detection_plan({"DI/O-1": [{"detection": "rising"}, {"detection": "falling"}]})

        assert detection_plan == {
            "DI/O-1": [
                ("DI/O-1_rising", {"detection": "rising"}),
                ("DI/O-1_falling", {"detection": "falling"}),
            ]
        }

    def test_event_name_replaces_the_derived_identifier(self):
        """Rule 3, which is also how a caller pins an identifier against later edits to that signal."""
        detection_configuration = {"DI/O-1": [{"detection": "rising", "event_name": "Lick"}, {"detection": "falling"}]}

        event_type_source_ids = [name for name, _ in resolve_detection_plan(detection_configuration)["DI/O-1"]]

        assert event_type_source_ids == ["Lick", "DI/O-1_falling"]

    def test_derivation_is_content_based_not_positional(self):
        """Reordering a signal's specs renames nothing, so a list is order-insensitive."""
        forward = resolve_detection_plan({"DI/O-1": [{"detection": "rising"}, {"detection": "falling"}]})
        reversed_order = resolve_detection_plan({"DI/O-1": [{"detection": "falling"}, {"detection": "rising"}]})

        assert {name for name, _ in forward["DI/O-1"]} == {name for name, _ in reversed_order["DI/O-1"]}

    def test_duplicate_identifiers_raise(self):
        """Rule 4 is cross-signal, which is why it lives here rather than in the per-signal validator."""
        with pytest.raises(ValueError, match="same identifier"):
            resolve_detection_plan(
                {
                    "DI/O-1": [{"detection": "rising", "event_name": "Pulse"}],
                    "DI/O-2": [{"detection": "rising", "event_name": "Pulse"}],
                }
            )
