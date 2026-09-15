"""Guard the ordering of the `EncodingWarning` filters in `pyproject.toml`.

`PYTHONWARNDEFAULTENCODING` is process wide, so the category has to be ignored by default and
re-raised for the code we own. pytest gives later `filterwarnings` entries higher precedence, so
moving the `ignore` after the two `error` entries would silently retire the PEP 597 policy without
failing anything.
"""

import warnings

import pytest


def _emit_encoding_warning_from(module_name: str) -> None:
    """Emit an `EncodingWarning` attributed to `module_name`, the way `open()` would."""
    warnings.warn_explicit(
        message="'encoding' argument not specified",
        category=EncodingWarning,
        filename=f"{module_name.replace('.', '/')}.py",
        lineno=1,
        module=module_name,
        registry={},
    )


def test_dependency_encoding_warning_is_ignored():
    _emit_encoding_warning_from("some_dependency.reader")


def test_neuroconv_encoding_warning_is_an_error():
    with pytest.raises(EncodingWarning):
        _emit_encoding_warning_from("neuroconv.datainterfaces.something")


def test_tests_encoding_warning_is_an_error():
    with pytest.raises(EncodingWarning):
        _emit_encoding_warning_from("tests.something")
