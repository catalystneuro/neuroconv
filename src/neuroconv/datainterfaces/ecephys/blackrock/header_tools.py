from __future__ import division  # for those using Python 2.6+

from collections import namedtuple
from datetime import datetime
from struct import calcsize, unpack


def _processheaders(curr_file, packet_fields):
    """
    :param curr_file:      {file} the current BR datafile to be processed
    :param packet_fields : {named tuple} the specific binary fields for the given header
    :return:               a fully unpacked and formatted tuple set of header information

    Read a packet from a binary data file and return a list of fields
    The amount and format of data read will be specified by the
    packet_fields container
    """

    # This is a lot in one line.  First I pull out all the format strings from
    # the basic_header_fields named tuple, then concatenate them into a string
    # with '<' at the front (for little endian format)
    packet_format_str = "<" + "".join([fmt for name, fmt, fun in packet_fields])

    # Calculate how many bytes to read based on the format strings of the header fields
    bytes_in_packet = calcsize(packet_format_str)
    packet_binary = curr_file.read(bytes_in_packet)

    # unpack the binary data from the header based on the format strings of each field.
    # This returns a list of data, but it's not always correctly formatted (eg, FileSpec
    # is read as ints 2 and 3, but I want it as '2.3'
    packet_unpacked = unpack(packet_format_str, packet_binary)

    # Create an iterator from the data list.  This allows a formatting function
    # to use more than one item from the list if needed, and the next formatting
    # function can pick up on the correct item in the list
    data_iter = iter(packet_unpacked)

    # create an empty dictionary from the name field of the packet_fields.
    # The loop below will fill in the values with formatted data by calling
    # each field's formatting function
    packet_formatted = dict.fromkeys([name for name, fmt, fun in packet_fields])
    for name, fmt, fun in packet_fields:
        packet_formatted[name] = fun(data_iter)
    curr_file.close()
    return packet_formatted


def _format_filespec(header_list):
    return str(next(header_list)) + "." + str(next(header_list))  # eg 2.3


def _format_timeorigin(header_list):
    year = next(header_list)
    month = next(header_list)
    _ = next(header_list)
    day = next(header_list)
    hour = next(header_list)
    minute = next(header_list)
    second = next(header_list)
    millisecond = next(header_list)
    return datetime(year, month, day, hour, minute, second, millisecond * 1000)


def _format_stripstring(header_list):
    string = bytes.decode(next(header_list), "latin-1")
    return string.split(STRING_TERMINUS, 1)[0]


def _format_none(header_list):
    return next(header_list)


FieldDef = namedtuple("FieldDef", ["name", "formatStr", "formatFnc"])
STRING_TERMINUS = "\x00"


def _parse_nsx_basic_header(nsx_file):
    nsx_basic_dict = [
        FieldDef("FileSpec", "2B", _format_filespec),  # 2 bytes   - 2 unsigned char
        FieldDef("BytesInHeader", "I", _format_none),  # 4 bytes   - uint32
        FieldDef("Label", "16s", _format_stripstring),  # 16 bytes  - 16 char array
        FieldDef("Comment", "256s", _format_stripstring),  # 256 bytes - 256 char array
        FieldDef("Period", "I", _format_none),  # 4 bytes   - uint32
        FieldDef("TimeStampResolution", "I", _format_none),  # 4 bytes   - uint32
        FieldDef("TimeOrigin", "8H", _format_timeorigin),  # 16 bytes  - 8 uint16
        FieldDef("ChannelCount", "I", _format_none),
    ]  # 4 bytes   - uint32
    datafile = open(nsx_file, "rb")
    filetype_id = bytes.decode(datafile.read(8), "latin-1")
    if filetype_id == "NEURALSG":
        # this won't contain fields that can be added to NWBFile metadata
        return dict()
    return _processheaders(datafile, nsx_basic_dict)


def _parse_nev_basic_header(nev_file):
    nev_basic_dict = [
        FieldDef("FileTypeID", "8s", _format_stripstring),  # 8 bytes   - 8 char array
        FieldDef("FileSpec", "2B", _format_filespec),  # 2 bytes   - 2 unsigned char
        FieldDef("AddFlags", "H", _format_none),  # 2 bytes   - uint16
        FieldDef("BytesInHeader", "I", _format_none),  # 4 bytes   - uint32
        FieldDef("BytesInDataPackets", "I", _format_none),  # 4 bytes   - uint32
        FieldDef("TimeStampResolution", "I", _format_none),  # 4 bytes   - uint32
        FieldDef("SampleTimeResolution", "I", _format_none),  # 4 bytes   - uint32
        FieldDef("TimeOrigin", "8H", _format_timeorigin),  # 16 bytes  - 8 x uint16
        FieldDef("CreatingApplication", "32s", _format_stripstring),  # 32 bytes  - 32 char array
        FieldDef("Comment", "256s", _format_stripstring),  # 256 bytes - 256 char array
        FieldDef("NumExtendedHeaders", "I", _format_none),
    ]
    datafile = open(nev_file, "rb")
    return _processheaders(datafile, nev_basic_dict)
