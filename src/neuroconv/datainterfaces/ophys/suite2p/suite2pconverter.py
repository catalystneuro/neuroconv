from pathlib import Path

from pydantic import DirectoryPath, validate_call

from .suite2pdatainterface import Suite2pSegmentationInterface
from ....nwbconverter import ConverterPipe
from ....utils import get_json_schema_from_method_signature


def _get_available_channels_in_plane(*, folder_path: DirectoryPath, plane_name: str) -> list[str]:
    """Get the channels Suite2p wrote for one plane.

    ``Suite2pSegmentationInterface.get_available_channels`` answers for the folder as a whole by
    looking inside the first plane only, so a session where the red channel was segmented for some
    planes and not others reports ``chan2`` for all of them. Asking each plane for itself is what
    keeps the converter from building an interface over trace files that are not there.
    """
    plane_folder_path = Path(folder_path) / plane_name

    channel_names = ["chan1"]
    if (plane_folder_path / "F_chan2.npy").exists():
        channel_names.append("chan2")

    return channel_names


class Suite2pConverter(ConverterPipe):
    """Convert a whole Suite2p output folder.

    Point this at the folder holding the ``plane#`` sub-folders and every plane and channel in it is
    written: one ``PlaneSegmentation``, one ``ImagingPlane`` and one set of traces per plane and
    channel. A single-plane single-channel session needs no extra arguments and produces the same
    file as :class:`~neuroconv.datainterfaces.Suite2pSegmentationInterface` on its own.

    The ``combined`` folder that Suite2p writes for multi-plane sessions is skipped, since its ROIs
    are the per-plane ones concatenated and writing both would duplicate every ROI.
    """

    display_name = "Suite2p Segmentation"
    keywords = Suite2pSegmentationInterface.keywords
    associated_suffixes = Suite2pSegmentationInterface.associated_suffixes
    info = "Converter for all planes and channels of a Suite2p segmentation output folder."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_json_schema_from_method_signature(method=cls.__init__)
        source_schema["properties"]["folder_path"][
            "description"
        ] = "Path to the folder containing Suite2p segmentation data. Should contain 'plane#' subfolder(s)."
        return source_schema

    @validate_call
    def __init__(
        self,
        folder_path: DirectoryPath,
        *,
        verbose: bool = False,
    ):
        """
        Parameters
        ----------
        folder_path : DirectoryPath
            Path to the folder containing Suite2p segmentation data. Should contain 'plane#' sub-folders.
        verbose : bool, default: False
            Controls verbosity.
        """
        plane_names = Suite2pSegmentationInterface.get_available_planes(folder_path=folder_path)

        data_interfaces = {}
        for plane_name in plane_names:
            channel_names = _get_available_channels_in_plane(folder_path=folder_path, plane_name=plane_name)
            for channel_name in channel_names:
                interface_name = f"Suite2pSegmentation_{channel_name}_{plane_name}"
                data_interfaces[interface_name] = Suite2pSegmentationInterface(
                    folder_path=folder_path,
                    channel_name=channel_name,
                    plane_name=plane_name,
                    verbose=verbose,
                )

        super().__init__(data_interfaces=data_interfaces, verbose=verbose)
