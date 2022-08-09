Style Guide and General Conventions
===================================

We automatically reformat all contributions using the `black <https://black.readthedocs.io/en/stable/>`_
pre-commit hook formatter. Black enforces strict rules about spacing to produce minimal diffs. To enable black
formatting on your own machine, do the following:

1. Install pre-commit: :code:`pip install pre-commit`
2. Execute :code:`pre-commit install` to install git hooks in your .git/ directory.

Scikit-learn style
------------------
Beyond using black, this project follows some of the conventions from
`scikit-learn <https://scikit-learn.org/stable/>`_.

#. Use underscores to separate words in non class names: :code:`n_samples` rather than :code:`nsamples`.
#. Avoid multiple statements on one line. Prefer a line return after a control flow statement (if/for).
   Note that this does not apply to `conditional expressions <https://docs.python.org/3.10/reference/expressions.html?highlight=ternary#conditional-expressions>`_
#. Use relative imports for references inside the source code :code:`src/neuroconv`.
#. Unit tests are an exception to the previous rule; they should use absolute imports, exactly as client code would.
#. A corollary is that, if :code:`neuroconv.foo` exports a class or function that is implemented in
   :code:`neuroconv.foo.bar.baz`, the test should import it from :code:`neuroconv.foo`.
#. Please dont use :code:`import *` in any case. It is considered harmful by the official Python recommendations. It
   makes the code harder to read as the origin of symbols is no longer explicitly referenced, but most important, it
   prevents using a static analysis tool like pyflakes to automatically find bugs in the code.
#. Use the `numpy docstring standard <https://numpydoc.readthedocs.io/en/latest/format.html#numpydoc-docstring-guide>`_
   in all the docstrings.

DataInterface conventions
---------------------------
#. Use :code:`file_path` and :code:`folder_path` as arguments for the location of input files and folders/directories respectively.
#. As an exception to convention to separte words for underscores, we use :code:`nwbfile` to refer to an instance
   of :py:class:`~pynwb.file.NWBFile`.

Other conventions
-----------------
#. Whenever possible, use the type dictionary constructor :code:`dictionary = dict(foo=bar)`  instead of the brace
   notation :code:`dictionary={foo: bar}`. Notable exceptions that do not led themselves to this constructor are the
   use of  non-valid python expressions as keys (e.g :code:`1key` can not be used as a key because of the number at the beginning)
   or and the use of non-mutable objects as keys.
