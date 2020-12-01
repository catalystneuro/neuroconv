"""Authors: Luiz Tauffer, Cody Baker, and Ben Dichter."""
import collections.abc
import inspect
import numpy as np


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


def get_base_schema(tag=None, root=False, id_=None, **kwargs):
    """Return the base schema used for all other schemas."""
    base_schema = dict(
        required=[],
        properties={},
        type='object',
        additionalProperties=False
    )
    if tag is not None:
        base_schema.update(tag=tag)
    if root:
        base_schema.update({
            "$schema": "http://json-schema.org/draft-07/schema#"
        })
    if id_:
        base_schema.update({"$id": id_})
    base_schema.update(**kwargs)
    return base_schema


def get_schema_from_method_signature(class_method, exclude=None):
    """
    Take a class method and return a jsonschema of the input args.

    Parameters
    ----------
    class_method: function
    exclude: list, optional

    Returns
    -------
    dict

    """
    if exclude is None:
        exclude = ['self']
    else:
        exclude = exclude + ['self']
    input_schema = get_base_schema()
    annotation_json_type_map = {
        bool: "boolean",
        str: "string",
        int: "number",
        float: "number",
        dict: "object",
        list: "array"
    }

    for param_name, param in inspect.signature(class_method).parameters.items():
        if param_name not in exclude:
            if param.annotation:
                if hasattr(param.annotation, "__args__"):
                    args = param.annotation.__args__
                else:
                    args = [param.annotation]

                valid_args = [x in annotation_json_type_map for x in args]
                if any(valid_args):
                    param_type = [annotation_json_type_map[x] for x in np.array(args)[valid_args]]
                else:
                    raise ValueError("There must be only one valid annotation type that maps to json! "
                                     f"{param.annotation.__args__} found.")

                if len(set(param_type)) > 1:
                    raise ValueError("Conflicting json parameter types were detected from the annotation! "
                                     f"{param.annotation.__args__} found.")
            else:
                raise NotImplementedError(f"The annotation type of '{param}' in function '{class_method}' "
                                          "is not implemented! Please request it to be added at github.com/"
                                          "catalystneuro/nwb-conversion-tools/issues or create the json-schema"
                                          "for this method manually.")
            arg_spec = {
                param_name: dict(
                    type=param_type[0]
                )
            }
            if param.default is param.empty:
                input_schema['required'].append(param_name)
            elif param.default is not None:
                arg_spec[param_name].update(default=param.default)
            input_schema['properties'].update(arg_spec)
        input_schema['additionalProperties'] = param.kind == inspect.Parameter.VAR_KEYWORD
    return input_schema


def fill_defaults(schema: dict, defaults: dict, overwrite: bool = True):
    """
    Insert the values of the defaults dict as default values in the schema in place.

    Parameters
    ----------
    schema: dict
    defaults: dict
    overwrite: bool
    """
    for key, val in schema['properties'].items():
        if key in defaults:
            if val['type'] == 'object':
                fill_defaults(val, defaults[key], overwrite=overwrite)
            else:
                if overwrite or ('default' not in val):
                    val['default'] = defaults[key]


def unroot_schema(schema: dict):
    """Modifies a json-schema dictionary to make it not root

    Parameters
    ----------
    schema: dict
    """

    terms = ('required', 'properties', 'type', 'additionalProperties',
             'title', 'description')
    return {k: v for k, v in schema.items() if k in terms}
