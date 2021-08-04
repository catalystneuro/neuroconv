from pathlib import Path
import yaml
import json


class NoDatesSafeLoader(yaml.SafeLoader):
    @classmethod
    def remove_implicit_resolver(cls, tag_to_remove):
        """
        Solution from here: https://stackoverflow.com/a/37958106/11483674
        Remove implicit resolvers for a particular tag

        Takes care not to modify resolvers in super classes.

        We want to load datetimes as strings, not dates, because we
        go on to serialise as json which doesn't have the advanced types
        of yaml, and leads to incompatibilities down the track.
        """
        if not "yaml_implicit_resolvers" in cls.__dict__:
            cls.yaml_implicit_resolvers = cls.yaml_implicit_resolvers.copy()

        for first_letter, mappings in cls.yaml_implicit_resolvers.items():
            cls.yaml_implicit_resolvers[first_letter] = [
                (tag, regexp) for tag, regexp in mappings if tag != tag_to_remove
            ]


NoDatesSafeLoader.remove_implicit_resolver("tag:yaml.org,2002:timestamp")


def load_metadata_from_file(file) -> dict:
    """
    Function to safely load metadata from YAML and JSON files.
    """
    assert Path(file).is_file(), f"{file} is not a file."
    assert Path(file).suffix in [".yml", ".json"], f"{file} is not a valid .yml or .json file."

    if Path(file).suffix == ".yml":
        with open(file, "r") as f:
            metadata = yaml.load(f, Loader=NoDatesSafeLoader)
    elif Path(file).suffix == ".json":
        with open(file, "r") as f:
            metadata = json.load(f)

    return metadata
