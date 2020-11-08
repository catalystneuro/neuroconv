"""Authors: Cody Baker and Ben Dichter."""
import spikeextractors as se
from pyintan.intan import read_rhd

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface


class IntanRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting a IntanRecordingExtractor."""

    RX = se.IntanRecordingExtractor

    def get_metadata(self):
        """Retrieve Ecephys metadata specific to the Intan format."""
        intan_file_metadata = read_rhd(self.input_args['file_path'])[1]
        exclude_chan_types = ['AUX', 'ADC', 'VDD']

        group_names = [x['native_channel_name'].split('-')[0] for x in intan_file_metadata
                       if not any([y in x['native_channel_name'] for y in exclude_chan_types])]
        unique_group_names = set(group_names)

        group_electrode_number = [
            [
                int(y[1]) for group_name in unique_group_names for x in intan_file_metadata
                for y in [x['native_channel_name'].split('-')] if y[0] == group_name
                and not any([y in x['native_channel_name'] for y in exclude_chan_types])
            ]
        ]

        re_metadata = dict(
            Ecephys=dict(
                Device=[dict()],
                ElectrodeGroup=[
                    dict(
                        name=f'Group {group_name}',
                        description=f"Group {group_name} electrodes."
                    )
                    for group_name in unique_group_names
                ],
                Electrodes=[
                    dict(
                        name='group_name',
                        description="The name of the ElectrodeGroup this electrode is a part of.",
                        data=[f"Group {x}" for x in group_names]
                    )
                ],
                ElectricalSeries=dict(
                    name='ElectricalSeries',
                    description="Raw acquisition traces."
                )
            )
        )

        if len(unique_group_names) > 1:
            re_metadata['Ecephys']['Electrodes'].append(
                dict(
                    name='group_electrode_number',
                    description="0-indexed channel within a group.",
                    data=group_electrode_number
                )
            )

        any_custom_names = any(
            [
                x['native_channel_name'] != x['custom_channel_name'] for x in intan_file_metadata
                if 'custom_channel_name' in x and not any([y in x['native_channel_name'] for y in exclude_chan_types])
            ]
        )
        if any_custom_names:
            re_metadata['Ecephys']['Electrodes'].append(
                dict(
                    name='custom_channel_name',
                    description="Custom channel name assigned in Intan.",
                    data=[
                            x['custom_channel_name'] for x in intan_file_metadata if 'custom_channel_name' in x
                            and not any([y in x['native_channel_name'] for y in exclude_chan_types])
                    ]
                )
            )

        return re_metadata
