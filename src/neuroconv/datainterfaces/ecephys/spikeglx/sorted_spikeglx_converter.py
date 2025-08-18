"""Converter for handling multiple SpikeGLX streams with their corresponding sorting data."""

from .spikeglxconverter import SpikeGLXConverterPipe
from ..sorted_converter import _SortedConverterPipe


class SortedSpikeGLXConverter(_SortedConverterPipe):
    """
    Converter for handling multiple SpikeGLX streams with their corresponding sorting data.

    This converter handles the challenge of maintaining proper linkage between sorted units
    and their recording channels when dealing with multiple SpikeGLX streams (e.g., multiple
    Neuropixels probes). It ensures that units from each sorting interface are correctly
    associated with electrodes from their corresponding recording stream.

    For SpikeGLX data, interface names correspond to recording streams which combine
    probe and band information (e.g., "imec0.ap" = probe 0 + action potential band,
    "imec1.lf" = probe 1 + local field potential band).

    **Automatic Unit ID Conflict Resolution:**
    When unit IDs conflict across different sorting interfaces (e.g., multiple sorters producing
    units with the same IDs like "0", "1", etc.), this converter automatically generates unique
    unit names using the pattern "{interface_name}_unit_{original_id}" (e.g., "imec0_ap_unit_0").
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
            - interface_name: str
                The interface identifier (e.g., "imec0.ap")
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
        ...         "interface_name": "imec0.ap",
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
        ...         "interface_name": "imec1.ap",
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
        # Store reference to original spikeglx_converter for potential access
        self.spikeglx_converter = spikeglx_converter

        # Validate that all sorted interfaces are AP streams (SpikeGLX-specific requirement)
        available_streams = spikeglx_converter._stream_ids
        for config in sorting_configuration:
            interface_name = config["interface_name"]
            if interface_name not in available_streams:
                raise ValueError(
                    f"Interface '{interface_name}' not found in SpikeGLXConverterPipe. "
                    f"Available interfaces: {available_streams}"
                )
            if not interface_name.endswith(".ap"):
                raise ValueError(
                    f"Interface '{interface_name}' is not an AP stream. Only AP streams can have sorting data."
                )

        # Add device information to sorting interfaces (SpikeGLX-specific feature)
        for config in sorting_configuration:
            interface_name = config["interface_name"]
            sorting_interface = config["sorting_interface"]
            recording_interface = spikeglx_converter.data_interface_objects[interface_name]

            # Add device information based on the recording interface's device metadata
            # Extract device name from the recording interface's metadata following SpikeGLX conventions
            recording_interface_metadata = recording_interface.get_metadata()
            device_name = recording_interface_metadata["Ecephys"]["Device"][0]["name"]  # e.g., "NeuropixelsImec0"
            device_values = [device_name] * len(sorting_interface.units_ids)
            sorting_interface.sorting_extractor.set_property(key="device", values=device_values)

        # Initialize parent class with the converter
        super().__init__(
            converter=spikeglx_converter,
            sorting_configuration=sorting_configuration,
            verbose=verbose,
        )
