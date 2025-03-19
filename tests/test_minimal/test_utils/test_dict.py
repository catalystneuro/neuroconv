import unittest
from copy import deepcopy

from neuroconv.utils.dict import DeepDict


class TestDeepDict(unittest.TestCase):
    def setUp(self):
        self.dd = DeepDict()
        self.dd["a"]["b"]["c"] = 42
        self.data = {"a": {"b": {"c": 42}}}

    def test_getitem(self):
        self.assertEqual(self.dd["a"]["b"]["c"], 42)

    def test_getitem_hashable(self):
        dd = DeepDict()
        dd["key1"][1][(3,)] = 42
        self.assertEqual(dd["key1"][1][(3,)], 42)

    def test_missing_key(self):
        dd = DeepDict()
        self.assertIsInstance(dd["non_existent"], DeepDict)

    def test_to_dict(self):
        expected = self.data
        self.assertEqual(self.dd.to_dict(), expected)

    def test_dict_magic(self):
        expected = self.data
        self.assertEqual(dict(self.dd), expected)

    def test_recursive_conversion(self):
        dd = DeepDict(self.data)
        self.assertIsInstance(dd["a"], DeepDict)
        self.assertIsInstance(dd["a"]["b"], DeepDict)

    def test_repr(self):
        expected_repr = "DeepDict: {'a': {'b': {'c': 42}}}"
        self.assertEqual(repr(self.dd), expected_repr)

    def test_deep_update(self):
        update_data = {"a": {"b": {"d": 55}, "e": {"f": 66}}, "g": {"h": 77}}
        self.dd.deep_update(update_data)
        expected = {"a": {"b": {"c": 42, "d": 55}, "e": {"f": 66}}, "g": {"h": 77}}
        self.assertEqual(dict(self.dd), expected)

    def test_deep_update_kwargs_input(self):
        update_data = {"a": {"b": {"d": 55}, "e": {"f": 66}}, "g": {"h": 77}}
        self.dd.deep_update(**update_data)
        expected = {"a": {"b": {"c": 42, "d": 55}, "e": {"f": 66}}, "g": {"h": 77}}
        self.assertEqual(dict(self.dd), expected)

    def test_deepcopy(self):
        dd2 = deepcopy(self.dd)
        dd2["a"]["b"]["c"] = 0
        self.assertEqual(dd2["a"]["b"]["c"], 0)
        self.assertEqual(self.dd["a"]["b"]["c"], 42)
