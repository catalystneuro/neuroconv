"""Authors: Cody Baker, Alessio Buccino."""
import numpy as np
from pathlib import Path
from importlib import import_module
from itertools import chain
from jsonschema import validate, RefResolver

from .json_schema import dict_deep_update, load_dict_from_file, FilePathType, OptionalFolderPathType
from ..nwbconverter import NWBConverter


def check_regular_timestamps(ts):
    """Check whether rate should be used instead of timestamps."""
    time_tol_decimals = 9
    uniq_diff_ts = np.unique(np.diff(ts).round(decimals=time_tol_decimals))
    return len(uniq_diff_ts) == 1


def run_conversion_from_yaml(
    specification_file_path: FilePathType,
    data_folder: OptionalFolderPathType = None,
    output_folder: OptionalFolderPathType = None,
    overwrite: bool = False,
):
    """
    Run conversion to NWB given a yaml specification file.

    Parameters
    ----------
    specification_file_path : FilePathType
        File path leading to .yml specification file for NWB conversion.
    data_folder : FolderPathType, optional
        Folder path leading to root location of the data files.
        The default is the parent directory of the specification_file_path.
    output_folder : FolderPathType, optional
        Folder path leading to the desired output location of the .nwb files.
        The default is the parent directory of the specification_file_path.
    overwrite : bool, optional
        If True, replaces any existing NWBFile at the nwbfile_path location, if save_to_file is True.
        If False, appends the existing NWBFile at the nwbfile_path location, if save_to_file is True.
        The default is False.
    """
    if data_folder is None:
        data_folder = Path(specification_file_path).parent
    if output_folder is None:
        output_folder = Path(specification_file_path).parent

    specification = load_dict_from_file(file_path=specification_file_path)
    schema_folder = Path(__file__).parent.parent / "schemas"
    specification_schema = load_dict_from_file(file_path=schema_folder / "yaml_specification_schema.json")
    validate(
        instance=specification,
        schema=specification_schema,
        resolver=RefResolver(base_uri="file://" + str(schema_folder) + "/", referrer=specification_schema),
    )

    global_metadata = specification.get("metadata", dict())
    global_data_interfaces = specification.get("data_interfaces")
    nwb_conversion_tools = import_module(
        name=".",
        package="nwb_conversion_tools",  # relative import, but named and referenced as if it were absolute
    )
    for experiment in specification["experiments"].values():
        experiment_metadata = experiment.get("metadata", dict())
        experiment_data_interfaces = experiment.get("data_interfaces")
        for session in experiment["sessions"]:
            session_data_interfaces = session.get("data_interfaces")
            data_interface_classes = dict()
            data_interfaces_names_chain = chain(
                *[
                    data_interfaces
                    for data_interfaces in [global_data_interfaces, experiment_data_interfaces, session_data_interfaces]
                    if data_interfaces is not None
                ]
            )
            for data_interface_name in data_interfaces_names_chain:
                data_interface_classes.update({data_interface_name: getattr(nwb_conversion_tools, data_interface_name)})

            CustomNWBConverter = type(
                "CustomNWBConverter", (NWBConverter,), dict(data_interface_classes=data_interface_classes)
            )

            source_data = session["source_data"]
            for interface_name, interface_source_data in session["source_data"].items():
                for key, value in interface_source_data.items():
                    source_data[interface_name].update({key: str(Path(data_folder) / value)})

            converter = CustomNWBConverter(source_data=source_data)
            metadata = converter.get_metadata()
            for metadata_source in [global_metadata, experiment_metadata, session.get("metadata", dict())]:
                metadata = dict_deep_update(metadata, metadata_source)
            converter.run_conversion(
                nwbfile_path=Path(output_folder) / f"{session['nwbfile_name']}.nwb",
                metadata=metadata,
                overwrite=overwrite,
                conversion_options=session.get("conversion_options", dict()),
            )
