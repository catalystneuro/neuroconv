Building the Documentation
==========================

For building the documentation locally, the following procedure can be followed.

Create a clean environment and type the following commands in your terminal

.. code:
  git clone https://github.com/catalystneuro/neuroconv
  cd neuroconv
  pip install -e .[docs]

These commands install both the latest version of the repo and the dependencies necessary to build the documentation.

.. note:
  The argument ``-e`` makes you install `editable <https://pip.pypa.io/en/stable/cli/pip_install/#editable-installs>`_

Now, to build the documention issue the following command in your terminal

.. code:
  sphinx-build -b html docs ./docs/_build/

This builds the html under ``/docs/_build/`` (from your root directory, where you have installed ``neuroconv``).

This allows you to review the outcome of the process localy before commiting code.
