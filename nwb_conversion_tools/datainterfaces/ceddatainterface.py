"""Authors: Luiz Tauffer"""
import spikeextractors as se

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface


class CEDRecordingInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting a CEDRecordingExtractor."""

    RX = se.CEDRecordingExtractor

    def get_metadata(self):
        """"""
        raise NotImplementedError('TODO')
        metadata = dict(
            Ecephys=dict(
                Device=dict(),
                # ElectrodeGroup=[
                #     dict(
                #         name=f'Group{group_name}',
                #         description=f"Group {group_name} electrodes."
                #     )
                #     for group_name in unique_group_names
                # ],
                # Electrodes=[
                #     dict(
                #         name='group_name',
                #         description="The name of the ElectrodeGroup this electrode is a part of.",
                #         data=[f"Group{x}" for x in group_names]
                #     )
                # ],
                # ElectricalSeries=dict(
                #     name='ElectricalSeries',
                #     description="Raw acquisition traces."
                # )
            )
        )

        return metadata
