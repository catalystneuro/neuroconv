import collections.abc
import inspect


def get_schema_data(in_data, data_schema):
    """Output the parts of the input dictionary in_data that are within the json schema properties of data_schema."""
    return {k: in_data[k] for k in data_schema['properties'] if k in in_data}


def dict_deep_update(d, u):
    """Perform an update to all nested keys of dictionary d from dictionary u."""
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = dict_deep_update(d.get(k, {}), v)
        elif isinstance(v, list):
            d[k] = d.get(k, []) + v
            # Remove repeated items if they exist
            if len(v) > 0 and not isinstance(v[0], dict):
                d[k] = list(set(d[k]))
        else:
            d[k] = v
    return d


def get_base_schema(tag=None):
    base_schema = dict(
        required=[],
        properties={},
        type='object',
        additionalProperties=False
    )
    if tag is not None:
        base_schema.update(tag=tag)
    return base_schema


def get_root_schema():
    root_schema = get_base_schema()
    root_schema.update({
        "$schema": "http://json-schema.org/draft-07/schema#",
    })
    return root_schema


def get_schema_from_method_signature(class_method, exclude=None):
    if exclude is None:
        exclude = []
    input_schema = get_base_schema()
    for param in inspect.signature(class_method).parameters.values():
        if param.name not in exclude + ['self']:
            arg_spec = {
                param.name: dict(
                    type='string'
                )
            }
            if param.default is param.empty:
                input_schema['required'].append(param.name)
            elif param.default is not None:
                arg_spec[param.name].update(default=param.default)
            input_schema['properties'].update(arg_spec)
        input_schema['additionalProperties'] = param.kind == inspect.Parameter.VAR_KEYWORD

    return input_schema
