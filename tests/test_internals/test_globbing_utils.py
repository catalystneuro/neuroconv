from hdmf.testing import TestCase

from nwb_conversion_tools.utils import get_fstring_variable_names, get_fstring_values_from_filename


class TestEmptyFStringAssertion(TestCase):
    def test_get_fstring_variable_names(self):
        with self.assertRaisesWith(
            exc_type=AssertionError,
            exc_msg=(
                "Empty variable name detected in f-string! Please ensure there is text between all "
                "enclosing '{' and '}'."
            ),
        ):
            get_fstring_variable_names(fstring="a/{x}b{y}/c{z}d{}")


def test_get_fstring_variable_names():
    assert get_fstring_variable_names(fstring="a/{x}b{y}/c{z}") == ["x", "y", "z"]


def test_get_fstring_values_from_filename():
    assert get_fstring_values_from_filename(filename="a/foobthat/cbar", fstring="a/{x}b{y}/c{z}") == [
        "foo",
        "that",
        "bar",
    ]
