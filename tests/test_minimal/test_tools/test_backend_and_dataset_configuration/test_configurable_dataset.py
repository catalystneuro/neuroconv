"""Unit tests for the ConfigurableDataset Pydantic model."""
from io import StringIO
from unittest.mock import patch

from neuroconv.tools.nwb_helpers import ConfigurableDataset


# def test_configurable_dataset_print():
#     """Test the printout display of a Dataset modellooks nice."""
#     test_dataset = ConfigurableDataset(
#         object_id="abc123",
#         object_name="TestObject",
#         parent="TestParent",
#         field="data",
#         maxshape=(2, 4),
#         dtype="int16",
#     )

#     with patch("sys.stdout", new=StringIO()) as out:
#         print(test_dataset)

#     expected_print = """TestObject of TestParent
# ------------------------
#   data
#     maxshape: (2, 4)
#     dtype: int16
# """
#     assert out.getvalue() == expected_print


# def test_configurable_dataset_repr():
#     """Test the programmatic repr of a Dataset model is more dataclass-like."""
#     test_dataset = ConfigurableDataset(
#         object_id="abc123",
#         object_name="TestObject",
#         parent="TestParent",
#         field="data",
#         maxshape=(2, 4),
#         dtype="int16",
#     )

#     # Important to keep the `repr` unmodified for appearance inside lists of Datasets
#     expected_repr = (
#         "ConfigurableDataset(object_id='abc123', object_name='TestObject', parent='TestParent', "
#         "field='data', maxshape=(2, 4), dtype='int16')"
#     )
#     assert repr(test_dataset) == expected_repr
