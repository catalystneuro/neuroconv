from neuroconv.utils import get_json_schema_from_method_signature


def test_get_schema_from_method_signature_basic():
    def test1(integer: int, string: str, boolean: bool, number: float):
        pass

    json_schema = get_json_schema_from_method_signature(method=test1)

    assert json_schema == {
        "properties": {
            "boolean": {"title": "Boolean", "type": "boolean"},
            "integer": {"title": "Integer", "type": "integer"},
            "number": {"title": "Number", "type": "number"},
            "string": {"title": "String", "type": "string"},
        },
        "title": "_TempModel",
        "type": "object",
    }


# def test_get_schema_from_method_signature_exclude():
#     def test1():
#         pass
#
#     json_schema = get_schema_from_method_signature(method=test1)
#
#     assert json_schema == {}
#
#
# def test_get_schema_from_method_signature_init():
#     class SomeInterface:
#         def __init__(self, file_path: FilePath, folder_path: DirectoryPath, old_annotation_1: str, old_annotation_2: pathlib.Path, old_annotation_3: Union[str, pathlib.Path]):
#             pass
#
#     json_schema = get_schema_from_method_signature(method=SomeInterface.__init__)
#
#     assert json_schema == {}
#
# def test_get_schema_from_method_signature_class_static():
#     class SomeInterface:
#
#         @staticmethod
#         def some_static_method(integer: int, string: str, boolean: bool, number: float):
#             pass
#     json_schema = get_schema_from_method_signature(method=test1)
#
#     assert json_schema == {}
#
# def test_get_schema_from_method_signature_class_method():
#     class SomeInterface:
#
#         @classmethod
#         def some_static_method(cls, integer: int, string: str, boolean: bool, number: float):
#             pass
#
#     json_schema = get_schema_from_method_signature(method=test1)
#
#     assert json_schema == {}
