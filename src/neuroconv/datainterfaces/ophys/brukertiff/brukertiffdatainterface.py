import warnings
from pathlib import Path
from typing import Literal

import numpy as np
from dateutil.parser import parse as dateparse
from pydantic import DirectoryPath, validate_call

from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils import DeepDict


class BrukerTiffImagingInterface(BaseImagingExtractorInterface):
    """Interface for Bruker Prairie View OME-TIFF imaging data.

    This interface uses the unified ``BrukerTiffImagingExtractor`` from roiextractors,
    which handles single-plane, volumetric, and multi-channel data through a single class.
    Volumetric data is exposed as a 4D series.

    Channels are identified by name (e.g. ``"Ch1"``, ``"Ch2"``); use
    :meth:`get_available_channels` to list them. When the data contains multiple channels,
    ``channel_name`` is required.

    The interface emits metadata in the new dict-based format keyed by ``metadata_key``,
    populating ``Devices``, ``Ophys.ImagingPlanes``, and ``Ophys.MicroscopySeries``.
    """

    display_name = "Bruker TIFF Imaging"
    associated_suffixes = (".ome", ".tif", ".xml", ".env")
    info = "Interface for Bruker Prairie View OME-TIFF imaging data."

    @classmethod
    def get_extractor_class(cls):
        from roiextractors import BrukerTiffImagingExtractor

        return BrukerTiffImagingExtractor

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["folder_path"][
            "description"
        ] = "Folder containing Bruker .ome.tif files and the matching configuration .xml."
        return source_schema

    def get_metadata_schema(self) -> dict:
        """Return a schema compatible with the new dict-based Ophys metadata format.

        The base imaging schema requires legacy ``Ophys.Device`` / ``Ophys.ImagingPlane`` /
        ``Ophys.TwoPhotonSeries`` lists, which this interface does not produce. We bypass those
        requirements and only validate ``NWBFile`` baseline metadata.
        """
        from ....basedatainterface import BaseDataInterface

        return BaseDataInterface.get_metadata_schema(self)

    @classmethod
    def get_available_channels(cls, folder_path: DirectoryPath) -> list[str]:
        """Return the channel names available in the Bruker dataset, in acquisition order.

        Channel names are read from the Bruker configuration ``.xml`` (the ``channelName``
        attribute of each ``<File>`` element), which is authoritative and present for every
        PrairieView version. This mirrors ``BrukerTiffImagingExtractor`` and avoids the OME-XML
        path, which fails on PrairieView 5.8+ ``BinaryOnly`` packaging where the ``.ome.tif``
        files carry no ``<Pixels>`` block.

        Parameters
        ----------
        folder_path : DirectoryPath
            Folder containing Bruker .ome.tif files and the matching configuration .xml.

        Returns
        -------
        list[str]
            Channel labels in acquisition order (e.g. ``["Ch1", "Ch2"]``).
        """
        from xml.etree import ElementTree

        folder_path = Path(folder_path)
        xml_file_path = folder_path / f"{folder_path.name}.xml"
        if not xml_file_path.is_file():
            raise FileNotFoundError(f"Bruker XML configuration file not found at '{xml_file_path}'.")

        xml_root = ElementTree.parse(xml_file_path).getroot()
        channel_number_to_name = {
            int(elem.attrib["channel"]): elem.attrib["channelName"] for elem in xml_root.iter("File")
        }
        return [channel_number_to_name[number] for number in sorted(channel_number_to_name)]

    @validate_call
    def __init__(
        self,
        folder_path: DirectoryPath,
        *,
        channel_name: str | None = None,
        plane_index: int | None = None,
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """
        Parameters
        ----------
        folder_path : DirectoryPath
            Folder containing Bruker .ome.tif files and the matching configuration .xml.
        channel_name : str, optional
            Channel name (e.g. ``"Ch1"``, ``"Ch2"``). Required when the data has more than one
            channel. Use :meth:`get_available_channels` to see what is available.
        plane_index : int, optional
            Select a single depth plane of a volumetric acquisition and write it as a 2D
            ``TwoPhotonSeries`` (the "disjoint" layout, one series and one imaging plane per
            depth). When ``None`` (default), volumetric data is written as a single 4D series.
        metadata_key : str, optional
            Metadata key for this interface. When ``None``, defaults to ``"bruker_tiff_imaging"``,
            with a channel suffix when ``channel_name`` is provided and a plane suffix when
            ``plane_index`` is provided (e.g. ``"bruker_tiff_imaging_Ch1_plane0"``).
        verbose : bool, default: False
        """
        if metadata_key is None:
            metadata_key = "bruker_tiff_imaging"
            if channel_name is not None:
                metadata_key = f"{metadata_key}_{channel_name}"
            if plane_index is not None:
                metadata_key = f"{metadata_key}_plane{plane_index}"

        self.channel_name = channel_name
        self.plane_index = plane_index
        super().__init__(
            folder_path=folder_path,
            channel_name=channel_name,
            verbose=verbose,
            metadata_key=metadata_key,
        )

        # The base builds the full extractor. Keep a reference to it for Bruker XML metadata, and
        # expose only the selected plane's pixel data via ``select_plane`` (roiextractors>=0.9.0).
        # The single-plane view does not carry the Bruker-specific attributes ``_bruker_xml_metadata``
        # / ``_xml_root`` that ``get_metadata`` reads, so those go through ``self._bruker_extractor``.
        # TODO(roiextractors#578): once the extractor exposes a public per-plane ``metadata``
        # attribute, drop this reference and read plane metadata directly off ``self.imaging_extractor``.
        self._full_imaging_extractor = self.imaging_extractor
        if plane_index is not None:
            self.imaging_extractor = self.imaging_extractor.select_plane(plane_index)

    @property
    def _bruker_extractor(self):
        """Extractor carrying the Bruker configuration XML.

        Always the full (unsliced) extractor: the ``select_plane`` view does not proxy
        ``_bruker_xml_metadata`` / ``_xml_root``. Collapses to ``self.imaging_extractor`` once
        roiextractors exposes per-plane metadata (roiextractors#578).
        """
        return self._full_imaging_extractor

    def get_metadata(self) -> DeepDict:
        """Return metadata in the new dict-based format only.

        Populates ``Devices``, ``Ophys.ImagingPlanes`` and ``Ophys.MicroscopySeries`` keyed by
        ``self.metadata_key``. Cross-references are wired via ``device_metadata_key`` and
        ``imaging_plane_metadata_key``.
        """
        metadata = super().get_metadata(use_new_metadata_format=True)

        bruker_xml_metadata = self._bruker_extractor._bruker_xml_metadata

        if "date" in bruker_xml_metadata:
            metadata["NWBFile"]["session_start_time"] = dateparse(bruker_xml_metadata["date"])

        device_name = "BrukerFluorescenceMicroscope"
        device_description = f"Version {bruker_xml_metadata['version']}" if "version" in bruker_xml_metadata else None
        device_entry = {"name": device_name}
        if device_description is not None:
            device_entry["description"] = device_description
        metadata["Devices"] = {self.metadata_key: device_entry}

        name_suffix = self.channel_name if self.channel_name is not None else ""
        if self.plane_index is not None:
            name_suffix = f"{name_suffix}Plane{self.plane_index}"
        imaging_plane_name = f"ImagingPlane{name_suffix}"
        photon_series_name = f"TwoPhotonSeries{name_suffix}"
        is_volumetric = self.imaging_extractor.is_volumetric

        sampling_frequency = float(self.imaging_extractor.get_sampling_frequency())
        frame_shape = self.imaging_extractor.get_frame_shape()  # (num_rows, num_columns)
        grid_spacing, origin_coords, field_of_view = self._extract_spatial_metadata(
            frame_shape=frame_shape, is_volumetric=is_volumetric
        )

        imaging_plane_entry = {
            "name": imaging_plane_name,
            "description": "The imaging plane origin_coords units are in the microscope reference frame.",
            "device_metadata_key": self.metadata_key,
            "imaging_rate": sampling_frequency,
            "excitation_lambda": np.nan,
            "indicator": "unknown",
            "location": "unknown",
            "optical_channel": [
                {
                    "name": "OpticalChannel",
                    "description": "An optical channel of the microscope.",
                    "emission_lambda": np.nan,
                }
            ],
            "grid_spacing": grid_spacing,
            "grid_spacing_unit": "meters",
            "origin_coords": origin_coords,
            "origin_coords_unit": "micrometers",
        }

        microscopy_series_entry = {
            "name": photon_series_name,
            "unit": "n.a.",
            "imaging_plane_metadata_key": self.metadata_key,
            "description": (
                "The volumetric imaging data acquired from the Bruker Two-Photon Microscope."
                if is_volumetric
                else "Imaging data acquired from the Bruker Two-Photon Microscope."
            ),
            "field_of_view": field_of_view,
        }
        if "scanLinePeriod" in bruker_xml_metadata:
            microscopy_series_entry["scan_line_rate"] = 1 / float(bruker_xml_metadata["scanLinePeriod"])

        metadata["Ophys"] = {
            "ImagingPlanes": {self.metadata_key: imaging_plane_entry},
            "MicroscopySeries": {self.metadata_key: microscopy_series_entry},
        }

        return metadata

    def _extract_spatial_metadata(
        self, frame_shape: tuple[int, int], is_volumetric: bool
    ) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
        """Compute grid_spacing, origin_coords, and field_of_view from the Bruker XML.

        Returns tuples (not lists) because ``dict_deep_update`` collapses repeated
        values in primitive lists (e.g. ``[7.09e-05, 7.09e-05]`` -> ``[7.09e-05]``)
        when NWBConverter merges per-interface metadata.
        """
        bruker_xml_metadata = self._bruker_extractor._bruker_xml_metadata
        microns_per_pixel = bruker_xml_metadata["micronsPerPixel"]
        x_size_meters = float(microns_per_pixel[0]["XAxis"]) / 1e6
        y_size_meters = float(microns_per_pixel[1]["YAxis"]) / 1e6

        origin_coords = self._determine_position_current(is_volumetric=is_volumetric)

        grid_spacing: tuple[float, ...] = (y_size_meters, x_size_meters)
        field_of_view: tuple[float, ...] = (y_size_meters * frame_shape[1], x_size_meters * frame_shape[0])
        if is_volumetric:
            depths = self._determine_plane_depths(xml_root=self._bruker_extractor._xml_root)
            if len(depths) >= 2:
                # grid_spacing z is the inter-plane step; field_of_view z is the total depth extent.
                step_meters = abs(depths[1] - depths[0]) / 1e6
                extent_meters = abs(depths[-1] - depths[0]) / 1e6
                grid_spacing = grid_spacing + (step_meters,)
                field_of_view = field_of_view + (extent_meters,)

        return grid_spacing, tuple(origin_coords), field_of_view

    def _determine_position_current(self, is_volumetric: bool) -> list[float]:
        """Return [y, x] (planar) or [y, x, z] (volumetric) microscope-frame positions in micrometers.

        When this interface is pinned to a single depth plane (``plane_index`` is set), the z value
        is that plane's own focal position, so each disjoint ``ImagingPlane`` gets its true depth.
        """
        xml_root = self._bruker_extractor._xml_root
        default_position_element = xml_root.find(".//PVStateValue[@key='positionCurrent']")
        if default_position_element is None:
            return [0.0, 0.0]

        position_values: list[float] = []
        for axis in ["YAxis", "XAxis"]:
            sub_indexed_values = default_position_element.find(f"./SubindexedValues[@index='{axis}']")
            if sub_indexed_values is None:
                position_values.append(0.0)
                continue
            for sub_indexed_value in sub_indexed_values:
                position_values.append(float(sub_indexed_value.attrib["value"]))

        if self.plane_index is not None:
            depths = self._determine_plane_depths(xml_root=xml_root)
            if self.plane_index < len(depths):
                position_values.append(depths[self.plane_index])
            return position_values

        if not is_volumetric:
            return position_values

        # Volumetric (contiguous): the imaging plane's origin z is the first plane's focal depth.
        depths = self._determine_plane_depths(xml_root=xml_root)
        if depths:
            position_values.append(depths[0])
        return position_values

    def _determine_plane_depths(self, xml_root) -> list[float]:
        """Return the ordered, unique focal depths (micrometers) of the acquisition's z-planes.

        The active z device is read from ``zDevice`` (a piezo stage, an electrically tunable lens,
        etc.); its ``positionCurrent`` is collected across frames and the distinct depths are
        returned in acquisition order, matching ``select_plane``'s plane ordering. When ``zDevice``
        is absent, falls back to the z sub-device whose value moves away from the reference.
        """
        z_device_element = xml_root.find(".//PVStateValue[@key='zDevice']")
        z_device_index = int(z_device_element.attrib["value"]) if z_device_element is not None else None

        default_z_element = xml_root.find(".//PVStateValue[@key='positionCurrent']/SubindexedValues[@index='ZAxis']")
        default_z_values = (
            [float(v.attrib["value"]) for v in default_z_element] if default_z_element is not None else []
        )

        ordered_depths: list[float] = []
        for frame in xml_root.findall(".//Frame"):
            z_values_element = frame.find(".//PVStateValue[@key='positionCurrent']/SubindexedValues[@index='ZAxis']")
            if z_values_element is None:
                continue
            z_values = [float(v.attrib["value"]) for v in z_values_element]
            if z_device_index is not None and z_device_index < len(z_values):
                depth = z_values[z_device_index]
            else:
                moving = [
                    z
                    for index, z in enumerate(z_values)
                    if index >= len(default_z_values) or default_z_values[index] != z
                ]
                if not moving:
                    continue
                depth = moving[0]
            if depth not in ordered_depths:
                ordered_depths.append(depth)

        return ordered_depths


# ---------------------------------------------------------------------------
# Deprecated interfaces. Will be removed on or after December 2026.
# Use BrukerTiffImagingInterface instead.
# ---------------------------------------------------------------------------


class BrukerTiffMultiPlaneImagingInterface(BaseImagingExtractorInterface):
    """Deprecated. Use ``BrukerTiffImagingInterface`` instead.

    Interface for Bruker multi-plane TIFF files using ``BrukerTiffMultiPlaneImagingExtractor``
    from roiextractors.
    """

    display_name = "Bruker TIFF Imaging (single channel, multiple planes)"
    associated_suffixes = (".ome", ".tif", ".xml", ".env")
    info = "Interface for a single channel of multi-plane Bruker TIFF imaging data."

    @classmethod
    def get_source_schema(cls) -> dict:
        """
        Get the source schema for the Bruker TIFF imaging data.

        Returns
        -------
        dict
            The JSON schema for the Bruker TIFF imaging data source.
        """
        source_schema = super().get_source_schema()
        source_schema["properties"]["folder_path"][
            "description"
        ] = "The folder that contains the Bruker TIF image files (.ome.tif) and configuration files (.xml, .env)."
        return source_schema

    @classmethod
    def get_streams(
        cls,
        folder_path: DirectoryPath,
        plane_separation_type: Literal["contiguous", "disjoint"] = None,
    ) -> dict:
        """
        Get streams for the Bruker TIFF imaging data.

        Parameters
        ----------
        folder_path : DirectoryPath
            Path to the folder containing the Bruker TIFF files.
        plane_separation_type : Literal["contiguous", "disjoint"], optional
            Type of plane separation to apply. If "contiguous", only the first plane stream for each channel is retained.

        Returns
        -------
        dict
            A dictionary containing the streams for the Bruker TIFF imaging data. The dictionary has the following keys:
            - "channel_streams": List of channel stream names.
            - "plane_streams": Dictionary where keys are channel stream names and values are lists of plane streams.
        """
        from roiextractors import BrukerTiffMultiPlaneImagingExtractor

        streams = BrukerTiffMultiPlaneImagingExtractor.get_streams(folder_path=folder_path)
        for channel_stream_name in streams["channel_streams"]:
            if plane_separation_type == "contiguous":
                streams["plane_streams"].update(
                    {channel_stream_name: [streams["plane_streams"][channel_stream_name][0]]}
                )
        return streams

    @classmethod
    def get_extractor_class(cls):
        from roiextractors import BrukerTiffMultiPlaneImagingExtractor

        return BrukerTiffMultiPlaneImagingExtractor

    def __init__(
        self,
        folder_path: DirectoryPath,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        stream_name: str | None = None,
        verbose: bool = False,
    ):
        """
        Initialize reading of TIFF files.

        Parameters
        ----------
        folder_path : DirectoryPath
            The path to the folder that contains the Bruker TIF image files (.ome.tif) and configuration files (.xml, .env).
        stream_name : str, optional
            The name of the recording stream (e.g. 'Ch2').
        verbose : bool, default: False
        """
        warnings.warn(
            "BrukerTiffMultiPlaneImagingInterface is deprecated and will be removed on or after December 2026. "
            "Use BrukerTiffImagingInterface instead.",
            FutureWarning,
            stacklevel=2,
        )

        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "stream_name",
                "verbose",
            ]
            num_positional_args_before_args = 1  # folder_path
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
                f"Passing arguments positionally to BrukerTiffMultiPlaneImagingInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            stream_name = positional_values.get("stream_name", stream_name)
            verbose = positional_values.get("verbose", verbose)

        self.folder_path = folder_path
        super().__init__(
            folder_path=folder_path,
            stream_name=stream_name,
            verbose=verbose,
        )
        self._stream_name = self.imaging_extractor.stream_name.replace("_", "")
        self._frame_shape = self.imaging_extractor.get_frame_shape()

    def _determine_position_current(self) -> list[float]:
        """
        Returns y, x, and z position values. The unit of values is in the microscope reference frame.
        """
        from roiextractors.extractors.tiffimagingextractors.brukertiffimagingextractor import (
            _parse_xml,
        )

        streams = self.get_streams(folder_path=self.folder_path)
        channel_stream_name = streams["channel_streams"][0]
        plane_streams_per_channel = streams["plane_streams"][channel_stream_name]

        # general positionCurrent
        position_values = []
        xml_root_element = _parse_xml(folder_path=self.folder_path)
        default_position_element = xml_root_element.find(".//PVStateValue[@key='positionCurrent']")

        for index_value in ["YAxis", "XAxis"]:
            position_sub_indexed_values = default_position_element.find(f"./SubindexedValues[@index='{index_value}']")
            for position_sub_indexed_value in position_sub_indexed_values:
                position_values.append(float(position_sub_indexed_value.attrib["value"]))

        z_plane_values = []
        for plane_stream in plane_streams_per_channel:
            frames_per_stream = [
                frame
                for frame in xml_root_element.findall(".//Frame")
                for file in frame.findall("File")
                if plane_stream in file.attrib["filename"]
            ]

            # The frames for each plane will have the same positionCurrent values
            position_element = frames_per_stream[0].find(".//PVStateValue[@key='positionCurrent']")
            default_z_position_values = default_position_element.find("./SubindexedValues[@index='ZAxis']")
            z_positions = []
            for z_sub_indexed_value in default_z_position_values:
                z_value = float(z_sub_indexed_value.attrib["value"])
                z_positions.append(z_value)

            z_position_values = position_element.find("./SubindexedValues[@index='ZAxis']")
            for z_device_ind, z_position_value in enumerate(z_position_values):
                z_value = float(z_position_value.attrib["value"])
                # find the changing z position value
                if z_positions[z_device_ind] != z_value:
                    z_plane_values.append(z_value)

        # difference between start position and end position of the z scan
        if len(z_plane_values) > 1:
            z_value = abs(z_plane_values[0] - z_plane_values[-1])
        position_values.append(z_value)
        return position_values

    def get_metadata(self) -> DeepDict:
        """
        Get metadata for the Bruker TIFF imaging data.

        Returns
        -------
        DeepDict
            The metadata dictionary containing imaging metadata from the Bruker TIFF files.
        """
        metadata = super().get_metadata()

        xml_metadata = self.imaging_extractor.xml_metadata
        session_start_time = dateparse(xml_metadata["date"])
        metadata["NWBFile"].update(session_start_time=session_start_time)

        description = f"Version {xml_metadata['version']}"
        device_name = "BrukerFluorescenceMicroscope"
        metadata["Ophys"]["Device"][0].update(
            name=device_name,
            description=description,
        )

        imaging_plane_metadata = metadata["Ophys"]["ImagingPlane"][0]
        imaging_plane_metadata.update(
            device=device_name,
            imaging_rate=self.imaging_extractor.get_sampling_frequency(),
        )
        two_photon_series_metadata = metadata["Ophys"]["TwoPhotonSeries"][0]
        two_photon_series_metadata.update(
            description="The volumetric imaging data acquired from the Bruker Two-Photon Microscope.",
            scan_line_rate=1 / float(xml_metadata["scanLinePeriod"]),
        )

        streams = self.get_streams(folder_path=self.folder_path, plane_separation_type="contiguous")
        if len(streams["channel_streams"]) > 1:
            imaging_plane_name = f"ImagingPlane{self._stream_name}"
            imaging_plane_metadata.update(name=imaging_plane_name)
            two_photon_series_metadata.update(
                name=f"TwoPhotonSeries{self._stream_name}",
                imaging_plane=imaging_plane_name,
            )

        microns_per_pixel = xml_metadata["micronsPerPixel"]
        x_position_in_meters = float(microns_per_pixel[0]["XAxis"]) / 1e6
        y_position_in_meters = float(microns_per_pixel[1]["YAxis"]) / 1e6

        origin_coords = self._determine_position_current()
        z_plane_current_position_in_meters = abs(origin_coords[-1]) / 1e6
        grid_spacing = [y_position_in_meters, x_position_in_meters, z_plane_current_position_in_meters]
        field_of_view = [
            y_position_in_meters * self._frame_shape[1],
            x_position_in_meters * self._frame_shape[0],
            z_plane_current_position_in_meters,
        ]

        imaging_plane_metadata.update(
            grid_spacing=grid_spacing,
            origin_coords=origin_coords,
            description="The imaging plane origin_coords units are in the microscope reference frame.",
        )

        two_photon_series_metadata.update(field_of_view=field_of_view)

        return metadata


class BrukerTiffSinglePlaneImagingInterface(BaseImagingExtractorInterface):
    """Deprecated. Use ``BrukerTiffImagingInterface`` instead.

    Data Interface for ``BrukerTiffSinglePlaneImagingExtractor``.
    """

    display_name = "Bruker TIFF Imaging (single channel, single plane)"
    associated_suffixes = BrukerTiffMultiPlaneImagingInterface.associated_suffixes
    info = "Interface for handling a single channel and a single plane of Bruker TIFF imaging data."

    @classmethod
    def get_source_schema(cls) -> dict:
        """
        Get the source schema for the Bruker TIFF imaging data.

        Returns
        -------
        dict
            The JSON schema for the Bruker TIFF imaging data source.
        """
        source_schema = super().get_source_schema()
        source_schema["properties"]["folder_path"][
            "description"
        ] = "The folder containing the Bruker TIF image files and configuration files."
        return source_schema

    @classmethod
    def get_streams(cls, folder_path: DirectoryPath) -> dict:
        """
        Get streams for the Bruker TIFF imaging data.

        Parameters
        ----------
        folder_path : DirectoryPath
            Path to the folder containing the Bruker TIFF files.

        Returns
        -------
        dict
            A dictionary containing the streams extracted from the Bruker TIFF files.
        """
        from roiextractors import BrukerTiffMultiPlaneImagingExtractor

        streams = BrukerTiffMultiPlaneImagingExtractor.get_streams(folder_path=folder_path)
        return streams

    @classmethod
    def get_extractor_class(cls):
        from roiextractors import BrukerTiffSinglePlaneImagingExtractor

        return BrukerTiffSinglePlaneImagingExtractor

    def __init__(
        self,
        folder_path: DirectoryPath,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        stream_name: str | None = None,
        verbose: bool = False,
    ):
        """
        Initialize reading of TIFF files.

        Parameters
        ----------
        folder_path : DirectoryPath
            The path to the folder that contains the Bruker TIF image files (.ome.tif) and configuration files (.xml, .env).
        stream_name : str, optional
            The name of the recording stream (e.g. 'Ch2').
        verbose : bool, default: False
        """
        warnings.warn(
            "BrukerTiffSinglePlaneImagingInterface is deprecated and will be removed on or after December 2026. "
            "Use BrukerTiffImagingInterface instead.",
            FutureWarning,
            stacklevel=2,
        )

        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "stream_name",
                "verbose",
            ]
            num_positional_args_before_args = 1  # folder_path
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
                f"Passing arguments positionally to BrukerTiffSinglePlaneImagingInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            stream_name = positional_values.get("stream_name", stream_name)
            verbose = positional_values.get("verbose", verbose)

        super().__init__(
            folder_path=folder_path,
            stream_name=stream_name,
            verbose=verbose,
        )
        self.folder_path = folder_path
        self._stream_name = self.imaging_extractor.stream_name.replace("_", "")
        self._frame_shape = self.imaging_extractor.get_frame_shape()

    def _determine_position_current(self) -> list[float]:
        """
        Returns y, x, and z position values. The unit of values is in the microscope reference frame.
        """
        stream_name = self.imaging_extractor.stream_name
        frames_per_stream = [
            frame
            for frame in self.imaging_extractor._xml_root.findall(".//Frame")
            for file in frame.findall("File")
            if stream_name == file.attrib["channelName"]
        ]

        if len(frames_per_stream) == 0:
            # If no frames, fall back to the old logic which matches by file name
            # At the moment this is used because the stream name is not only for channels
            # But also for planes in the case of multi-plane imaging with disjoint planes
            # For this case, the stream name for the plane is made-up from the file name
            # And we need to match the stream (e.g.  "Ch2_000001") to the file name instead.
            frames_per_stream = [
                frame
                for frame in self.imaging_extractor._xml_root.findall(".//Frame")
                for file in frame.findall("File")
                if stream_name in file.attrib["filename"]
            ]

        # general positionCurrent
        position_values = []
        default_position_element = self.imaging_extractor._xml_root.find(".//PVStateValue[@key='positionCurrent']")

        for index_value in ["YAxis", "XAxis"]:
            position_sub_indexed_values = default_position_element.find(f"./SubindexedValues[@index='{index_value}']")
            for position_sub_indexed_value in position_sub_indexed_values:
                position_values.append(float(position_sub_indexed_value.attrib["value"]))

        # The frames for each plane will have the same positionCurrent values
        position_element = frames_per_stream[0].find(".//PVStateValue[@key='positionCurrent']")
        if position_element is None:
            return position_values

        default_z_position_values = default_position_element.find("./SubindexedValues[@index='ZAxis']")
        z_positions = []
        for z_sub_indexed_value in default_z_position_values:
            z_positions.append(float(z_sub_indexed_value.attrib["value"]))

        z_position_values = position_element.find("./SubindexedValues[@index='ZAxis']")
        for z_device_ind, z_position_value in enumerate(z_position_values):
            z_value = float(z_position_value.attrib["value"])
            # find the changing z position value
            if z_positions[z_device_ind] != z_value:
                position_values.append(z_value)

        return position_values

    def get_metadata(self) -> DeepDict:
        """
        Get metadata for the Bruker TIFF imaging data.

        Returns
        -------
        DeepDict
            The metadata dictionary containing imaging metadata from the Bruker TIFF files.
        """
        metadata = super().get_metadata()

        xml_metadata = self.imaging_extractor.xml_metadata
        session_start_time = dateparse(xml_metadata["date"])
        metadata["NWBFile"].update(session_start_time=session_start_time)

        description = f"Version {xml_metadata['version']}"
        device_name = "BrukerFluorescenceMicroscope"
        metadata["Ophys"]["Device"][0].update(
            name=device_name,
            description=description,
        )

        imaging_plane_metadata = metadata["Ophys"]["ImagingPlane"][0]
        imaging_plane_metadata.update(
            device=device_name,
            imaging_rate=self.imaging_extractor.get_sampling_frequency(),
        )
        two_photon_series_metadata = metadata["Ophys"]["TwoPhotonSeries"][0]

        two_photon_series_metadata.update(
            description="Imaging data acquired from the Bruker Two-Photon Microscope.",
            scan_line_rate=1 / float(xml_metadata["scanLinePeriod"]),
        )

        streams = self.get_streams(folder_path=self.folder_path)
        if len(streams["channel_streams"]) > 1 or len(streams["plane_streams"]):
            imaging_plane_name = f"ImagingPlane{self._stream_name}"
            imaging_plane_metadata.update(name=imaging_plane_name)
            two_photon_series_metadata.update(
                name=f"TwoPhotonSeries{self._stream_name}",
                imaging_plane=imaging_plane_name,
            )

        microns_per_pixel = xml_metadata["micronsPerPixel"]
        x_position_in_meters = float(microns_per_pixel[0]["XAxis"]) / 1e6
        y_position_in_meters = float(microns_per_pixel[1]["YAxis"]) / 1e6
        grid_spacing = [y_position_in_meters, x_position_in_meters]
        origin_coords = self._determine_position_current()
        field_of_view = [
            y_position_in_meters * self._frame_shape[1],
            x_position_in_meters * self._frame_shape[0],
        ]

        if len(streams["plane_streams"]) and len(origin_coords) == 3:
            z_plane_current_position_in_meters = abs(origin_coords[-1]) / 1e6
            grid_spacing.append(z_plane_current_position_in_meters)
            field_of_view.append(z_plane_current_position_in_meters)

        imaging_plane_metadata.update(
            grid_spacing=grid_spacing,
            origin_coords=origin_coords,
            description="The imaging plane origin_coords units are in the microscope reference frame.",
        )
        two_photon_series_metadata.update(field_of_view=field_of_view)

        return metadata
