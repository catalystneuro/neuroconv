import inspect


def get_schema_from_method_signature(class_method):
    input_schema = dict(
        required=[],
        properties=[],
        type='object',
        additionalProperties='false')

    for param in inspect.signature(class_method.__init__).parameters.values():
        if param.name is not 'self':
            arg_spec = dict(name=param.name, type='string')
            if param.default is param.empty:
                input_schema['required'].append(param.name)
            elif param.default is not None:
                arg_spec.update(default=param.default)
            input_schema['properties'].append(arg_spec)
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            input_schema['additionalProperties'] = 'true'

    return input_schema
