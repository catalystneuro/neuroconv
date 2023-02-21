Building the Documentation
==========================

Follow this procedure to build the documentation locally.  This will allow you to review the outcome of the process
locally before committing code.

First, create a clean environment and type the following commands in your terminal.

.. code-block:: bash

  git clone https://github.com/catalystneuro/neuroconv
  cd neuroconv
  pip install -e .[docs]

These commands install both the latest version of the repo and the dependencies necessary to build the documentation.

.. note::

  The argument ``-e`` makes you install `editable <https://pip.pypa.io/en/stable/cli/pip_install/#editable-installs>`_

Use the following command to build the documentation locally.

.. code-block:: bash

  sphinx-build -b html docs ./docs/_build/

This builds the html under ``/docs/_build/`` (from your root directory, where you have installed ``neuroconv``).
