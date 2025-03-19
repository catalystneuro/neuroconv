from pydantic.json_schema import GenerateJsonSchema, JsonSchemaValue
from pydantic_core import PydanticOmit
from pydantic_core.core_schema import CoreSchema


class PureJSONSchemaGenerator(GenerateJsonSchema):
    """
    Sometimes our Pydantic models include valid Pythonic types, such as `IsInstance[SomeGenericClass]`.

    However, these cases have no valid JSON equivalent as they are purely for programmatic usage.
    Thus, we exclude them from the schema generation.
    """

    def handle_invalid_for_json_schema(self, schema: CoreSchema, error_info: str) -> JsonSchemaValue:
        raise PydanticOmit
