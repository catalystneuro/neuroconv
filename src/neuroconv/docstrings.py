compression_options_docstring = """
compression_options : dictionary, optional
    Type of compression to use. Should follow the structure

    dict(
        method="name_of_compression_method",
        method_options=dict(...),
    )

    Valid 'method' values are any accepted by the `:py:class:~pynwb.H5DataIO`, such as "gzip" and "lzf".

    Not all methods have additional 'method_options' - in those cases, do not need to specify that field.

    The default method is "gzip" with 'extra_options=dict(level=4)'.
    Set 'method' to `None` to disable all compression.
"""

iterator_options_docstring = """
iterator_options : dictionary, optional
    The type of DataChunkIterator to use. Should follow the structure

    dict(
        method="v1_or_v2",
        method_options=dict(...),
    )

    'v1' is the original DataChunkIterator of the hdmf data_utils.
    'v2' is the locally developed RecordingExtractorDataChunkIterator, which offers full control over chunking.
    The default method is "v2".

    Some 'method_options' for the "v2" iterator are
        buffer_gb : float, optional
            Automatically calculates suitable buffer shape. Recommended to be as much free RAM as available.
            The default is 1 GB.
        chunk_mb : float, optional
            Automatically calculates suitable chunk shape. Should be at or below 1 MB.
            The default is 1 MB.
    If manual specification of buffer_shape and chunk_shape are desired, these may be specified as well.
"""
