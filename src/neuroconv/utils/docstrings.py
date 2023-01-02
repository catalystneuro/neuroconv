"""Utility functions related to docstrings."""


def format_docstring(function: callable, tab_level: int = 1, **format_kwargs):
    """
    A simple utility function to dynamically format the docstring of a function in-place.

    By default, Python docstrings cannot be dynamically formatted at time of the function definition.
    Instead, the placeholders must be first set as raw strings and then the __doc__ value is overloaded by this utiliy
    after the function is defined.

    An example usage would be

    from somewhere_upstream.docstrings import repeated_docstring

    def some_function(repeated_kwarg: type):
        '''
        ...

        Parameters
        ----------
        {repeated_docstring}
        '''

    format_docstring(function=some_function, repeated_kwarg=repeated_kwarg)

    Parameters
    ----------
    function : callable
        The function whose docstring contains format placeholders ({} characters)
    tab_level : int, optional
        If the function is within a class, set this option to 2 to align it to the rest of the elements.
        The default is 1.
    **format_kwargs : dict
        The mapping from placeholder references to the actual string to format.
        These are the same keyword arguments you might pass into `some_string_to_format.format(**format_kwargs)`.
    """
    for format_kwarg_name, format_kwarg in format_kwargs.items():
        format_kwargs.update(
            {format_kwarg_name: format_kwarg.lstrip("\n").rstrip("\n").replace("\n", "\n" + "    " * tab_level)}
        )
    function.__doc__ = function.__doc__.format(**format_kwargs)
