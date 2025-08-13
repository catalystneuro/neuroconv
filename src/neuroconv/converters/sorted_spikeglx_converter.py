"""Converter for handling multiple SpikeGLX streams with their corresponding sorting data."""

from ..datainterfaces.ecephys.spikeglx.spikeglxconverter import SpikeGLXConverterPipe
from ..nwbconverter import ConverterPipe


class SortedSpikeGLXConverter(ConverterPipe):
    """
    Converter for handling multiple SpikeGLX streams with their corresponding sorting data.

    This converter handles the challenge of maintaining proper linkage between sorted units
    and their recording channels when dealing with multiple SpikeGLX streams (e.g., multiple
    Neuropixels probes). It ensures that units from each sorting interface are correctly
    associated with electrodes from their corresponding recording stream.

    **Automatic Unit ID Conflict Resolution:**
    When unit IDs conflict across different sorting interfaces (e.g., multiple sorters producing
    units with the same IDs like "0", "1", etc.), this converter automatically generates unique
    unit names using the pattern "{stream_id}_unit_{original_id}" (e.g., "imec0_ap_unit_0").
    If unit IDs are already unique across all sorters, original unit names are preserved.

    **Device Information:**
    The converter automatically adds device information to each unit based on the corresponding
    SpikeGLX recording stream, enabling identification of which probe/device each unit came from.

    **Notes:**
    For more advanced control over unit naming and identification in multi-sorter scenarios,
    see the :doc:`adding_multiple_sorting_interfaces` guide which provides detailed strategies
    for handling complex sorting workflows.
    """

    display_name = "Sorted SpikeGLX Converter"
    keywords = ("electrophysiology", "spike sorting", "spikeglx", "neuropixels")
    associated_suffixes = ("None",)
    info = "Converter for handling multiple SpikeGLX streams with corresponding sorting data."

    def __init__(
        self,
        spikeglx_converter: SpikeGLXConverterPipe,
        sorting_configuration: list[dict],
        verbose: bool = False,
    ):
        """
        Initialize the SortedSpikeGLXConverter.

        Parameters
        ----------
        spikeglx_converter : SpikeGLXConverterPipe
            The converter handling all SpikeGLX streams.
        sorting_configuration : list[dict]
            List of configuration dictionaries, each containing:
            - stream_id: str
                The stream identifier (e.g., "imec0.ap")
            - sorting_interface: BaseSortingExtractorInterface
                The sorting interface for this stream
            - unit_ids_to_channel_ids: dict[str | int, list[str | int]]
                Mapping from unit IDs to their associated channel IDs

        verbose : bool, default: False
            Whether to output verbose text.

        Examples
        --------
        >>> from neuroconv.converters import SpikeGLXConverterPipe, SortedSpikeGLXConverter
        >>> from neuroconv.datainterfaces import KiloSortSortingInterface
        >>>
        >>> # Initialize the SpikeGLX converter
        >>> spikeglx_converter = SpikeGLXConverterPipe(folder_path="path/to/spikeglx_data")
        >>>
        >>> # Create sorting configuration for multiple probes
        >>> sorting_configuration = [
        ...     {
        ...         "stream_id": "imec0.ap",
        ...         "sorting_interface": KiloSortSortingInterface(
        ...             folder_path="path/to/imec0_kilosort_output"
        ...         ),
        ...         "unit_ids_to_channel_ids": {
        ...             "0": ["imec0.ap#AP0", "imec0.ap#AP1", "imec0.ap#AP2"],
        ...             "1": ["imec0.ap#AP3", "imec0.ap#AP4"],
        ...             "2": ["imec0.ap#AP5", "imec0.ap#AP6", "imec0.ap#AP7", "imec0.ap#AP8"]
        ...         }
        ...     },
        ...     {
        ...         "stream_id": "imec1.ap",
        ...         "sorting_interface": KiloSortSortingInterface(
        ...             folder_path="path/to/imec1_kilosort_output"
        ...         ),
        ...         "unit_ids_to_channel_ids": {
        ...             "0": ["imec1.ap#AP0", "imec1.ap#AP1"],
        ...             "1": ["imec1.ap#AP2", "imec1.ap#AP3", "imec1.ap#AP4"]
        ...         }
        ...     }
        ... ]
        >>>
        >>> # Create the converter
        >>> converter = SortedSpikeGLXConverter(
        ...     spikeglx_converter=spikeglx_converter,
        ...     sorting_configuration=sorting_configuration
        ... )
        >>>
        >>> # Run the conversion
        >>> converter.run_conversion(nwbfile_path="output.nwb")
        """
        self.spikeglx_converter = spikeglx_converter
        self.sorting_configuration = sorting_configuration
        self.verbose = verbose

        # Validate that sorting configuration is not empty
        if not sorting_configuration:
            raise ValueError(
                "SortedSpikeGLXConverter requires at least one sorting configuration. "
                "Use SpikeGLXConverterPipe directly if no sorting data is available."
            )

        # Create mapping of stream_ids that have sorting data
        self._sorted_stream_ids = {config["stream_id"] for config in sorting_configuration}

        # Validate that all sorted streams are AP streams
        available_streams = self.spikeglx_converter._stream_ids
        for stream_id in self._sorted_stream_ids:
            if stream_id not in available_streams:
                raise ValueError(
                    f"Stream '{stream_id}' not found in SpikeGLXConverterPipe. "
                    f"Available streams: {available_streams}"
                )
            if not stream_id.endswith(".ap"):
                raise ValueError(f"Stream '{stream_id}' is not an AP stream. Only AP streams can have sorting data.")

        # Check for unit ID conflicts across all sorting interfaces
        all_unit_ids = []
        for config in sorting_configuration:
            sorting_interface = config["sorting_interface"]
            all_unit_ids.extend(sorting_interface.units_ids)

        # Detect if there are duplicate unit IDs across sorters
        unique_unit_ids = set(all_unit_ids)
        non_unique_sorting_ids = len(unique_unit_ids) != len(all_unit_ids)

        # Create SortedRecordingConverter instances for each sorted stream
        # This will handle validation of unit_ids_to_channel_ids automatically
        self._sorted_converters = {}
        for config in sorting_configuration:
            stream_id = config["stream_id"]
            recording_interface = self.spikeglx_converter.data_interface_objects[stream_id]
            sorting_interface = config["sorting_interface"]
            unit_ids_to_channel_ids = config["unit_ids_to_channel_ids"]

            # Only add unique unit names if there are conflicts between different sorters
            if non_unique_sorting_ids:
                # Generate unique unit names for this stream using the stream identifier
                stream_prefix = stream_id.replace(".", "_")  # Replace dots to make valid identifiers
                unique_unit_names = [f"{stream_prefix}_unit_{unit_id}" for unit_id in sorting_interface.units_ids]
                sorting_interface.sorting_extractor.set_property(key="unit_name", values=unique_unit_names)

            # Add device information based on the recording interface's device metadata
            # Extract device name from the recording interface's metadata following SpikeGLX conventions
            recording_interface_metadata = recording_interface.get_metadata()
            device_name = recording_interface_metadata["Ecephys"]["Device"][0]["name"]  # e.g., "NeuropixelsImec0"
            device_values = [device_name] * len(sorting_interface.units_ids)
            sorting_interface.sorting_extractor.set_property(key="device", values=device_values)

            # Import here to avoid circular imports
            from ..datainterfaces.ecephys.sortedrecordinginterface import (
                SortedRecordingConverter,
            )

            self._sorted_converters[stream_id] = SortedRecordingConverter(
                recording_interface=recording_interface,
                sorting_interface=sorting_interface,
                unit_ids_to_channel_ids=unit_ids_to_channel_ids,
            )

        # Include all non-sorted streams and sorted converters
        data_interfaces = {}

        # Sort stream IDs to ensure deterministic ordering for consistent electrode table indices
        sorted_stream_ids = sorted(self.spikeglx_converter.data_interface_objects.keys())
        for stream_id in sorted_stream_ids:
            interface = self.spikeglx_converter.data_interface_objects[stream_id]
            if stream_id not in self._sorted_stream_ids:
                # Non-sorted stream (could be AP without sorting, LF, or NIDQ)
                data_interfaces[stream_id] = interface

        # Add sorted converters with unique names in sorted order
        for stream_id in sorted(self._sorted_converters.keys()):
            sorted_converter = self._sorted_converters[stream_id]
            data_interfaces[f"{stream_id}_sorted"] = sorted_converter

        super().__init__(data_interfaces=data_interfaces, verbose=verbose)
