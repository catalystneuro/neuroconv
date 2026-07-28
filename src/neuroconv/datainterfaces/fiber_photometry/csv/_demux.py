"""Demux configs for :class:`.CSVFiberPhotometryInterface`.

An interleaved CSV multiplexes the excitation channels frame-by-frame down the rows; a demux config
selects the one channel a single interface reads, either by a label column or by row parity. These
are validation-only value objects: a caller passes a plain ``dict`` and the interface coerces it.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator


class ColumnDemux(BaseModel):
    """Demultiplex an interleaved file by a label column: read the rows whose ``column`` matches ``values``.

    For a file whose excitation channels are multiplexed frame-by-frame down the rows with a column
    naming each row's channel (e.g. a Neurophotometrics ``LedState``), this selects one channel.
    ``values`` is a single label value or a list of them, in which case the rows whose ``column``
    equals *any* of the listed values are read -- used when several distinct label values denote the
    same channel (e.g. NPM ``LedState`` codes that share an excitation LED but differ in their
    digital-line bits).

    A startup frame carrying a label of its own is excluded for free, by not matching any interface's
    ``values``. ``skip_rows`` is for the case where that is not enough: it drops leading rows before
    the label is consulted, for a startup frame whose label *does* match (e.g. an NPM initialization
    frame written with every excitation bit set, which matches every wavelength).
    """

    by: Literal["column"] = "column"
    column: str | int
    values: str | int | list[str | int]
    skip_rows: int = Field(default=0, ge=0)


class StrideDemux(BaseModel):
    """Demultiplex an interleaved file by row parity: after dropping ``skip_rows`` leading rows, read
    rows ``index, index + channels, index + 2 * channels, ...`` (0-based).

    For a header-less file whose channels cycle in a fixed order with no label column. ``skip_rows``
    drops leading calibration frame(s) so the cyclic alignment lands on the right channel.
    """

    by: Literal["stride"] = "stride"
    channels: int = Field(gt=0)
    index: int = Field(ge=0)
    skip_rows: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _index_within_channels(self) -> "StrideDemux":
        if self.index >= self.channels:
            raise ValueError(f"stride demux index ({self.index}) must be < channels ({self.channels}).")
        return self


# One interface reads one channel; the demux config says which, by a label column or by row parity.
DemuxConfig = Annotated[ColumnDemux | StrideDemux, Field(discriminator="by")]
