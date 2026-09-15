import warnings

import pandas as pd
from pydantic import FilePath, validate_call

from ..timeintervalsinterface import TimeIntervalsInterface


class ExcelTimeIntervalsInterface(TimeIntervalsInterface):
    """Interface for adding data from an Excel file to NWB as a TimeIntervals object."""

    display_name = "Excel time interval table"
    associated_suffixes = (".xlsx", ".xls", ".xlsm")
    info = "Interface for writing a time intervals table from an excel file."

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        read_kwargs: dict | None = None,
        verbose: bool = False,
    ):
        """
        Parameters
        ----------
        file_path : FilePath
        read_kwargs : dict, optional
            Passed to pandas.read_excel()
        verbose : bool, default: False
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "read_kwargs",
                "verbose",
            ]
            num_positional_args_before_args = 1  # file_path
            if len(args) > len(parameter_names):
                raise TypeError(
                    f"__init__() takes at most {len(parameter_names) + num_positional_args_before_args + 1} positional arguments but "
                    f"{len(args) + num_positional_args_before_args + 1} were given. "
                    "Note: Positional arguments are deprecated and will be removed on or after August 2026. "
                    "Please use keyword arguments."
                )
            positional_values = dict(zip(parameter_names, args))
            passed_as_positional = list(positional_values.keys())
            warnings.warn(
                f"Passing arguments positionally to ExcelTimeIntervalsInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            read_kwargs = positional_values.get("read_kwargs", read_kwargs)
            verbose = positional_values.get("verbose", verbose)

        super().__init__(file_path=file_path, read_kwargs=read_kwargs, verbose=verbose)

    def _read_file(self, file_path: FilePath, **read_kwargs):
        return pd.read_excel(file_path, **read_kwargs)
