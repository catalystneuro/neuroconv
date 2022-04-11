from hdmf.testing import TestCase

from nwb_conversion_tools.utils import get_fstring_variable_names, get_fstring_values_from_filename


class TestEmptyFStringAssertion(TestCase):
    def test_get_fstring_variable_names_assertion(self):
        with self.assertRaisesWith(
            exc_type=AssertionError,
            exc_msg=(
                "Empty variable name detected in f-string! Please ensure there is text between all "
                "enclosing '{' and '}'."
            ),
        ):
            get_fstring_variable_names(fstring="a/{x}b{y}/c{z}d{}")


def test_get_fstring_variable_names():
    variable_names, _ = get_fstring_variable_names(fstring="a/{x}b{y}/c{z}")
    assert variable_names == ["x", "y", "z"]


class TestBadSeparatorAssertion(TestCase):
    def test_get_fstring_separators_assertion(self):
        with self.assertWarnsWith(
            warn_type=UserWarning,
            exc_msg=(
                "There is an empty separator between two variables in the f-string! "
                "The f-string will not be invertible."
            ),
        ):
            get_fstring_variable_names(fstring="a/{x}{y}/c{z}")


def test_get_fstring_separators():
    _, separators = get_fstring_variable_names(fstring="a/{x}b{y}/c{z}")
    assert separators == ["a/", "b", "/c"]


def test_get_fstring_values_from_filename():
    fstring_values = get_fstring_values_from_filename(filename="a/foobthat/cbar", fstring="a/{x}b{y}/c{z}")
    assert fstring_values == dict(x="foo", y="that", z="bar")
