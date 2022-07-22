Style Guide and General Conventions
-----------------------------------

As a general rule we use `black <https://black.readthedocs.io/en/stable/>`_ formater which should take care of most of
the formating issues. To ensure that your commits are already formatted the repo already contains the machinery
for per-commit hooks. To enable black formating do the following:

1. Install pre-commit: :code:`pip install pre-commit``
2. Execute :code:`pre-commit install`` to install git hooks in your .git/ directory.

For what is not covered by black, this project follows some of the conventions to `scikit-learn <https://scikit-learn.org/stable/>`_.

#. Use underscores to separate words in non class names: :code:`n_samples` rather than :code:`nsamples`.
#. Avoid multiple statements on one line. Prefer a line return after a control flow statement (if/for).
#. Use relative imports for references inside the source code :code:`src/neuroconv`.
#. Unit tests are an exception to the previous rule; they should use absolute imports, exactly as client code would.
#. A corollary is that, if :code:`neuroconv.foo`` exports a class or function that is implemented in :code:`neuroconv.foo.bar.baz`, the test should import it from :code:`neuroconv.foo`.
#. Please dont use :code:`import *` in any case. It is considered harmful by the official Python recommendations. It makes the code harder to read as the origin of symbols is no longer explicitly referenced, but most important, it prevents using a static analysis tool like pyflakes to automatically find bugs in scikit-learn.
#. Use the numpy `docstring standard <https://numpydoc.readthedocs.io/en/latest/format.html#numpydoc-docstring-guide>`_ in all your docstring.

Data interfaces conventions
^^^^^^^^^^^^^^^^^^^^^^^^^^^
#. Use :code:`file_path` and :code:`folder_path` as arguments for the location of input files and folder respectively.
#. In opposition to convention number 1 above, we use :code:`nwbfile` to refer to in-memory filesin the nwb format.

Other conventions
^^^^^^^^^^^^^^^^^
#. Whenever possible, use dictionary literals :code:`dictionary = dict(foo=bar)`  instead of constructors :code:`dictionary={foo=bar}`.
