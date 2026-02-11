import json
import unittest
from copy import deepcopy

import yaml

from neuroconv.utils.dict import DeepDict, load_dict_from_file


def test_load_yaml_with_utf8_characters(tmp_path):
    """Test loading YAML file with UTF-8 characters."""
    test_data = {
        "metadata": {
            "subject": "Test Subject",
            "description": "Testing UTF-8: é ñ ü ™ ©",
            "special_chars": "€ £ ¥ • ✓",
            "emoji": "🎉 🔬 🧠",
        }
    }

    # Write YAML file with UTF-8 encoding
    yaml_file = tmp_path / "test_utf8.yaml"
    with open(yaml_file, "w", encoding="utf-8") as f:
        yaml.dump(test_data, f, allow_unicode=True)

    # Load and verify
    loaded_data = load_dict_from_file(yaml_file)
    assert loaded_data == test_data
    assert loaded_data["metadata"]["description"] == "Testing UTF-8: é ñ ü ™ ©"
    assert loaded_data["metadata"]["emoji"] == "🎉 🔬 🧠"


def test_load_json_with_utf8_characters(tmp_path):
    """Test loading JSON file with UTF-8 characters."""
    test_data = {
        "metadata": {
            "subject": "Test Subject",
            "description": "Testing UTF-8: é ñ ü ™ ©",
            "special_chars": "€ £ ¥ • ✓",
            "emoji": "🎉 🔬 🧠",
        }
    }

    # Write JSON file with UTF-8 encoding
    json_file = tmp_path / "test_utf8.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(test_data, f, ensure_ascii=False)

    # Load and verify
    loaded_data = load_dict_from_file(json_file)
    assert loaded_data == test_data
    assert loaded_data["metadata"]["description"] == "Testing UTF-8: é ñ ü ™ ©"
    assert loaded_data["metadata"]["emoji"] == "🎉 🔬 🧠"


def test_load_yml_extension(tmp_path):
    """Test loading .yml file (alternative YAML extension)."""
    test_data = {"key": "value with UTF-8: café"}

    yml_file = tmp_path / "test.yml"
    with open(yml_file, "w", encoding="utf-8") as f:
        yaml.dump(test_data, f, allow_unicode=True)

    loaded_data = load_dict_from_file(yml_file)
    assert loaded_data == test_data


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
        expected_repr = "DeepDict({'a': {'b': {'c': 42}}})"
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
