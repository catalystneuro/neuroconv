import json
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

_continuity_description = """
Describe the continuity of the data: can be 'continuous', 'instantaneous', or 'step'.

Some examples of each are:
- A voltage trace would be 'continuous', because samples are recorded from a continuous process.
- An array of lick times would be 'instantaneous', because the data represents distinct moments in time.
- Times of image presentations would be  'step' because the picture remains the same until the next time-point.

This field is optional, but is useful in providing information about the underlying data.
It may inform the way this data is interpreted, the way it is visualized, and what analysis methods are applicable.
"""


class TimeSeriesBaseModel(BaseModel):
    name: str = Field(description="The name of this TimeSeries dataset.")
    description: str = Field(default="No description.", description="Description of this TimeSeries dataset.")
    unit: str = Field(description="The base unit of measurement (should be SI unit).")
    resolution: float = Field(
        default=-1.0, description="The smallest meaningful difference (in specified unit) between values in data."
    )
    comments: str = Field(default="No comments.", description="Human-readable comments about this TimeSeries dataset.")
    continuity: Optional[Literal["continuous", "instantaneous", "step"]] = Field(
        default=None, description=_continuity_description
    )
    # TODO - should we add user metadata control over remaining fields? 'control' and 'control_description'

    # Other fields explicitly excluded from metadata control are:
    #   - data
    #   - rate
    #   - starting_time
    # Since these are all set by internal NeuroConv operations


if __name__ == "__main__":
    with open(file=Path(__file__).parent / "time_series_schema.json", mode="w") as fp:
        json.dump(obj=json.loads(TimeSeriesBaseModel.schema_json()), fp=fp, indent=4)
