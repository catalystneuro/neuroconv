"""Private converter for handling multiple recording interfaces with their corresponding sorting data."""

from ...nwbconverter import ConverterPipe


class _SortedConverterPipe(ConverterPipe):
    """
    Private converter for handling multiple recording interfaces with their corresponding sorting data.

    This converter handles the challenge of maintaining proper linkage between sorted units
    and their recording channels when dealing with multiple recording interfaces from a base converter.
    It ensures that units from each sorting interface are correctly associated with electrodes from
    their corresponding recording interface.

    **Automatic Unit ID Conflict Resolution:**
    When unit IDs conflict across different sorting interfaces (e.g., multiple sorters producing
    units with the same IDs like "0", "1", etc.), this converter automatically generates unique
    unit names using the pattern "{interface_name}_unit_{original_id}" (e.g., "imec0_ap_unit_0").
    If unit IDs are already unique across all sorters, original unit names are preserved.

    """

    display_name = "Sorted Converter Pipe"
    keywords = ("electrophysiology", "spike sorting")
    associated_suffixes = ("None",)
    info = "Private converter for handling multiple recording interfaces with corresponding sorting data."

    def __init__(
        self,
        converter: ConverterPipe,
        sorting_configuration: list[dict],
        verbose: bool = False,
    ):
        """
        Initialize the _SortedConverterPipe.

        Parameters
        ----------
        converter : ConverterPipe
            The converter containing recording interfaces to be enhanced with sorting data.
        sorting_configuration : list[dict]
            List of configuration dictionaries, each containing:
            - interface_name: str
                The interface identifier (key in converter.data_interface_objects)
            - sorting_interface: BaseSortingExtractorInterface
                The sorting interface for this recording interface
            - unit_ids_to_channel_ids: dict[str | int, list[str | int]]
                Mapping from unit IDs to their associated channel IDs

        verbose : bool, default: False
            Whether to output verbose text.
        """
        self.converter = converter
        self.sorting_configuration = sorting_configuration
        self.verbose = verbose

        # Get recording interfaces from the converter
        recording_interfaces = converter.data_interface_objects

        # Validate that sorting configuration is not empty
        if not sorting_configuration:
            raise ValueError("_SortedConverterPipe requires at least one sorting configuration.")

        # Create mapping of interface_names that have sorting data
        self._sorted_interface_names = {config["interface_name"] for config in sorting_configuration}

        # Validate that all sorted interfaces exist in recording_interfaces
        available_interfaces = set(recording_interfaces.keys())
        for interface_name in self._sorted_interface_names:
            if interface_name not in available_interfaces:
                raise ValueError(
                    f"Interface '{interface_name}' not found in recording_interfaces. "
                    f"Available interfaces: {available_interfaces}"
                )

        # Check for unit ID conflicts across all sorting interfaces
        all_unit_ids = []
        for config in sorting_configuration:
            sorting_interface = config["sorting_interface"]
            all_unit_ids.extend(sorting_interface.units_ids)

        # Detect if there are duplicate unit IDs across sorters
        unique_unit_ids = set(all_unit_ids)
        non_unique_sorting_ids = len(unique_unit_ids) != len(all_unit_ids)

        # Create SortedRecordingConverter instances for each sorted interface
        # This will handle validation of unit_ids_to_channel_ids automatically
        self._sorted_converters = {}
        for config in sorting_configuration:
            interface_name = config["interface_name"]
            recording_interface = recording_interfaces[interface_name]
            sorting_interface = config["sorting_interface"]
            unit_ids_to_channel_ids = config["unit_ids_to_channel_ids"]

            # Only add unique unit names if there are conflicts between different sorters
            if non_unique_sorting_ids:
                # Generate unique unit names for this interface using the interface identifier
                interface_prefix = interface_name.replace(".", "_")  # Replace dots to make valid identifiers
                unique_unit_names = [f"{interface_prefix}_unit_{unit_id}" for unit_id in sorting_interface.units_ids]
                sorting_interface.sorting_extractor.set_property(key="unit_name", values=unique_unit_names)

            # Import here to avoid circular imports
            from .sortedrecordinginterface import SortedRecordingConverter

            self._sorted_converters[interface_name] = SortedRecordingConverter(
                recording_interface=recording_interface,
                sorting_interface=sorting_interface,
                unit_ids_to_channel_ids=unit_ids_to_channel_ids,
            )

        # Include all non-sorted interfaces and sorted converters
        data_interfaces = {}

        # Sort interface names to ensure deterministic ordering for consistent electrode table indices
        sorted_interface_names = sorted(recording_interfaces.keys())
        for interface_name in sorted_interface_names:
            interface = recording_interfaces[interface_name]
            if interface_name not in self._sorted_interface_names:
                # Non-sorted interface
                data_interfaces[interface_name] = interface

        # Add sorted converters with unique names in sorted order
        for interface_name in sorted(self._sorted_converters.keys()):
            sorted_converter = self._sorted_converters[interface_name]
            data_interfaces[f"{interface_name}_sorted"] = sorted_converter

        super().__init__(data_interfaces=data_interfaces, verbose=verbose)
