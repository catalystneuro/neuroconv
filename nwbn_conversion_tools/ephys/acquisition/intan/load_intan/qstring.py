#! /bin/env python
#
# Michael Gibson 23 April 2015


import sys, struct, os

def read_qstring(fid):
    """Read Qt style QString.  

    The first 32-bit unsigned number indicates the length of the string (in bytes).  
    If this number equals 0xFFFFFFFF, the string is null.

    Strings are stored as unicode.
    """

    length, = struct.unpack('<I', fid.read(4))
    if length == int('ffffffff', 16): return ""

    if length > (os.fstat(fid.fileno()).st_size - fid.tell() + 1) :
        print(length)
        raise Exception('Length too long.')

    # convert length from bytes to 16-bit Unicode words
    length = int(length / 2)

    data = []
    for i in range(0, length):
        c, = struct.unpack('<H', fid.read(2))
        data.append(c)

    if sys.version_info >= (3,0):
        a = ''.join([chr(c) for c in data])
    else:
        a = ''.join([unichr(c) for c in data])
    
    return a
  
if __name__ == '__main__':
    a=read_qstring(open(sys.argv[1], 'rb'))
    print(a)
