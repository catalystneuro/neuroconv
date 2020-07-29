import inspect
from copy import deepcopy

base_schema = dict(
        required=[],
        properties=[],
        type='object',
        additionalProperties=False)


def get_schema_from_method_signature(class_method):

    input_schema = deepcopy(base_schema)

    for param in inspect.signature(class_method.__init__).parameters.values():
        if param.name != 'self':
            arg_spec = dict(name=param.name, type='string')
            if param.default is param.empty:
                input_schema['required'].append(param.name)
            elif param.default is not None:
                arg_spec.update(default=param.default)
            input_schema['properties'].append(arg_spec)
        input_schema['additionalProperties'] = param.kind == inspect.Parameter.VAR_KEYWORD

    return input_schema


def get_schema_from_docval(docval):

    schema = deepcopy(base_schema)
    for docval_arg in docval['args']:
        if docval_arg['type'] is str or (isinstance(docval_arg['type'], tuple) and str in docval_arg['type']):
            schema_arg = dict(name=docval_arg['name'], type='string', description=docval_arg['doc'])
            if 'default' in docval_arg:
                if docval_arg['default'] is not None:
                    schema_arg.update(default=docval_arg['default'])
            else:
                schema['required'].append(docval_arg['name'])
            schema['properties'].append(schema_arg)

    if 'allow_extra' in docval:
        schema['additionalProperties'] = docval['allow_extra']

    return schema


def get_schema_from_hdmf_class(hdmf_class):
    return get_schema_from_docval(hdmf_class.__init__.__docval__)
