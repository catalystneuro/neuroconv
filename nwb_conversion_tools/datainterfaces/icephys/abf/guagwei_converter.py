from nwb_conversion_tools import AbfNeoDataInterface, NWBConverter


class GuagweiConverter(NWBConverter):
    data_interface_classes = dict(AbfNeoDataInterface=AbfNeoDataInterface)
