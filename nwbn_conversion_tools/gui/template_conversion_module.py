

def conversion_function(f_source, f_nwb, metafile):
    """
    A template conversion function that can be executed from GUI.

    Parameters
    ----------
    f_source : list of str
        List of paths to source files, e.g. ['file1.npz', 'file2.npz', 'file3.npz'].
    f_nwb : str
        Path to output NWB file, e.g. 'my_file.nwb'.
    meta : str
        Path to .yml meta data file
    """
    print('Source files:')
    for f in f_source:
        print(f)
    print(' ')
    print('Output file:')
    print(f_nwb)
    print(' ')
    print('Metadata file:')
    print(metafile)
