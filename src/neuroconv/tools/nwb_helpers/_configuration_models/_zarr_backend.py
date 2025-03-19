"""Base Pydantic models for the ZarrDatasetConfiguration."""

from typing import ClassVar, Literal, Type

import psutil
from hdmf_zarr import ZarrDataIO
from pydantic import Field

from ._base_backend import BackendConfiguration
from ._zarr_dataset_io import ZarrDatasetIOConfiguration


class ZarrBackendConfiguration(BackendConfiguration):
    """A model for matching collections of DatasetConfigurations specific to the Zarr backend."""

    backend: ClassVar[Literal["zarr"]] = "zarr"
    pretty_backend_name: ClassVar[Literal["Zarr"]] = "Zarr"
    data_io_class: ClassVar[Type[ZarrDataIO]] = ZarrDataIO

    dataset_configurations: dict[str, ZarrDatasetIOConfiguration] = Field(
        description=(
            "A mapping from object locations to their ZarrDatasetConfiguration specification that contains all "
            "information for writing the datasets to disk using the Zarr backend."
        )
    )
    number_of_jobs: int = Field(
        description=(
            "Number of jobs to use in parallel during write. Negative values, starting from -1, "
            "will use all the available CPUs (including logical), -2 is all except one, etc. "
            "This is equivalent to the pattern of indexing of "
            " `list(range(total_number_of_cpu))[number_of_jobs]`; for example, `-1` uses all available CPU, `-2` "
            "uses all except one, etc."
        ),
        ge=-psutil.cpu_count(),  # TODO: should we specify logical=False in cpu_count?
        le=psutil.cpu_count(),
        default=psutil.cpu_count() - 1,
    )
