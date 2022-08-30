from hdmf.testing import TestCase

from neuroconv.utils import decompose_f_string, parse_f_string


class TestGlobbingAssertions(TestCase):
    def test_decompose_f_string_assertion(self):
        with self.assertRaisesWith(
            exc_type=AssertionError,
            exc_msg=(
                "Empty variable name detected in f-string! Please ensure there is text between all "
                "enclosing '{' and '}'."
            ),
        ):
            decompose_f_string(f_string="a/{x}b{y}/c{z}d{}")

        def test_decompose_f_string_separators_assertion(self):
            with self.assertWarnsWith(
                warn_type=UserWarning,
                exc_msg=(
                    "There is an empty separator between two variables in the f-string! "
                    "The f-string will not be uniquely invertible."
                ),
            ):
                decompose_f_string(f_string="a/{x}{y}/c{z}")

    def test_parse_f_string_non_invertible_assertion(self):
        with self.assertRaisesWith(
            exc_type=AssertionError,
            exc_msg=(
                "Adjacent variable values contain the separator character! The f-string is not uniquely invertible."
            ),
        ):
            parse_f_string(string="a/foobbar/cthat", f_string="a/{x}b{y}/c{z}")

    def test_parse_f_string_bad_structure_assertion(self):
        with self.assertRaisesWith(
            exc_type=AssertionError,
            exc_msg="Unable to match f-string pattern to string! Please double check both structures.",
        ):
            parse_f_string(string="just/plain/wrong", f_string="a/{x}b{y}/c{z}")

    def test_parse_f_string_duplicated_mismatch_assertion(self):
        with self.assertRaisesWith(
            exc_type=ValueError,
            exc_msg=(
                "Duplicated variable placements for 'x' in f-string do not match in instance! "
                "Expected 'foo' but found 'wrong'."
            ),
        ):
            parse_f_string(string="a/foobthat/cbar/sub-wrong", f_string="a/{x}b{y}/c{z}/sub-{x}")


def test_decompose_f_string():
    variable_names, _ = decompose_f_string(f_string="a/{x}b{y}/c{z}")
    assert variable_names == ["x", "y", "z"]


def test_decompose_f_string_separators():
    _, separators = decompose_f_string(f_string="a/{x}b{y}/c")
    assert separators == ["a/", "b", "/c"]


def test_decompose_f_string_separators_leading():
    _, separators = decompose_f_string(f_string="{start}a/{x}b{y}/c")
    assert separators == ["", "a/", "b", "/c"]


def test_decompose_f_string_separators_trailing():
    _, separators = decompose_f_string(f_string="a/{x}b{y}/c{end}")
    assert separators == ["a/", "b", "/c", ""]


def test_parse_f_string():
    f_string_values = parse_f_string(string="a/foobthat/cbar", f_string="a/{x}b{y}/c{z}")
    assert f_string_values == dict(x="foo", y="that", z="bar")


def test_parse_f_string_leading_value():
    f_string_values = parse_f_string(string="123a/foobthat/cbar", f_string="{start}a/{x}b{y}/c{z}")
    assert f_string_values == dict(start="123", x="foo", y="that", z="bar")


def test_parse_f_string_no_trailing_value():
    f_string_values = parse_f_string(string="a/foobthat/c", f_string="a/{x}b{y}/c")
    assert f_string_values == dict(x="foo", y="that")


def test_parse_f_string_duplicates():
    f_string_values = parse_f_string(string="a/foobthat/cbar/sub-foo", f_string="a/{x}b{y}/c{z}/sub-{x}")
    assert f_string_values == dict(x="foo", y="that", z="bar")
