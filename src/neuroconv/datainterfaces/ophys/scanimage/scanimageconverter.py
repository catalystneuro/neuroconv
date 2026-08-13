from pydantic import FilePath, validate_call

from .scanimageimaginginterfaces import ScanImageImagingInterface
from ....nwbconverter import ConverterPipe
from ....tools.nwb_helpers import get_default_nwbfile_metadata
from ....utils import DeepDict, dict_deep_update, get_json_schema_from_method_signature


class ScanImageConverter(ConverterPipe):
    """Convert a ScanImage acquisition.

    Point this at a ScanImage TIFF file and every channel it holds is written: one ``ImagingPlane``
    and one ``TwoPhotonSeries`` per channel. A multi-file acquisition is followed from its first
    file, the way :class:`~neuroconv.datainterfaces.ScanImageImagingInterface` does, and a
    single-channel acquisition needs no extra arguments.

    Volumetric data is written as one 4D ``TwoPhotonSeries`` per channel. To write each depth plane
    separately, or to select a subset of the channels, build the interfaces yourself with
    ``plane_index`` and combine them in a :class:`~neuroconv.nwbconverter.ConverterPipe`.
    """

    display_name = "ScanImage Imaging"
    keywords = ScanImageImagingInterface.keywords
    associated_suffixes = ScanImageImagingInterface.associated_suffixes
    info = "Auto-channel-enumerated converter for ScanImage TIFF data."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = get_json_schema_from_method_signature(method=cls.__init__)
        source_schema["properties"]["file_path"][
            "description"
        ] = "Path to the ScanImage TIFF file. If this is part of a multi-file series, this should be the first file."
        return source_schema

    @validate_call
    def __init__(
        self,
        file_path: FilePath | None = None,
        *,
        file_paths: list[FilePath] | None = None,
        slice_sample: int | None = None,
        interleave_slice_samples: bool | None = None,
        verbose: bool = False,
    ):
        """
        Parameters
        ----------
        file_path : FilePath, optional
            Path to the ScanImage TIFF file. If this is part of a multi-file series, this should be the
            first file. Either `file_path` or `file_paths` must be provided.
        file_paths : list of FilePath, optional
            The files to read, in the temporal order of their frames. This is an escape value for when
            the automatic multi-file detection does not find the right set.
        slice_sample : int, optional
            Which frame to take from each slice when the acquisition holds several frames per slice.
            Has no effect when `frames_per_slice = 1`.
        interleave_slice_samples : bool, optional
            Write every frame of a slice as its own sample instead of selecting one with `slice_sample`.
            Has no effect when `frames_per_slice = 1` or when `slice_sample` is given.
        verbose : bool, default: False
            Controls verbosity.
        """
        first_file_path = file_path if file_path is not None else (file_paths[0] if file_paths else None)
        if first_file_path is None:
            raise ValueError("Either 'file_path' or 'file_paths' must be provided.")

        channel_names = ScanImageImagingInterface.get_available_channels(file_path=first_file_path)
        single_channel = len(channel_names) == 1

        data_interfaces = {}
        for channel_name in channel_names:
            interface_name = (
                "ScanImageImaging" if single_channel else f"ScanImageImaging_{channel_name.replace(' ', '_')}"
            )
            data_interfaces[interface_name] = ScanImageImagingInterface(
                file_path=file_path,
                file_paths=file_paths,
                # The interface takes the only channel by itself, and naming it changes the metadata key.
                channel_name=None if single_channel else channel_name,
                slice_sample=slice_sample,
                interleave_slice_samples=interleave_slice_samples,
                verbose=verbose,
            )

        super().__init__(data_interfaces=data_interfaces, verbose=verbose)

    def get_metadata(self) -> DeepDict:
        """
        Get metadata for every channel of the acquisition.

        Returns
        -------
        DeepDict
            The metadata of every channel, merged.
        """
        metadata = get_default_nwbfile_metadata()
        for interface in self.data_interface_objects.values():
            # The channel interfaces still default to the old list-based format, which addresses a photon
            # series by its position in a list and so cannot name one entry per channel unambiguously.
            # This converter is new and has only ever spoken the dict-based format, so it asks for it.
            interface_metadata = self._get_interface_metadata(interface=interface, use_new_metadata_format=True)
            # Entries are keyed per channel, so a list inside one of them describes that channel and is
            # not something to merge across interfaces. Appending would also dedupe the repeated values
            # of a symmetric field, and a square field of view's [x, x] would reach the file as [x].
            metadata = dict_deep_update(metadata, interface_metadata, append_list=False)
        return metadata
