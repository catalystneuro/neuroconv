Running GIN tests locally
=========================

NeuroConv verifies the integrity of all code changes by running a full test suite on short examples of real data from
the formats we support. The testing suite is broken up into sub-folders based on the scope of functionalities and
dependencies you wish to test. We recommend always running tests in a fresh environment to ensure errors are not the
result of contaminated dependencies. There are three broad classes of tests in this regard.

Run all tests
-------------
To run all tests, first clone the repo and ``cd`` into it.

.. code:: bash

  git clone https://github.com/catalystneuro/neuroconv.git
  cd neuroconv


Then install all required and optional dependencies in a fresh environment.

.. code:: bash

  pip install -e .[test,full]


Then simply run all tests with pytest

.. code:: bash

  pytest

.. note::

  You will likely observe many failed tests if the test data is not available. See the section 'Testing on Example Data' for instructions on how to download the test data.


Minimal
-------

These test internal functionality using only minimal dependencies or pre-downloaded data.

Sub-folders: `tests/test_minimal <https://github.com/catalystneuro/neuroconv/tree/main/tests/test_minimal>`

These can be run using only ``pip install -e neuroconv[test]`` and calling ``pytest tests/test_minimal``


Modality
--------

These test the functionality of our write tools tailored to certain external dependencies.

Sub-folders: `tests/test_ophys <https://github.com/catalystneuro/neuroconv/tree/main/tests/test_ophys>`_,
`tests/test_ecephys <https://github.com/catalystneuro/neuroconv/tree/main/tests/test_ecephys>`_,
`tests/test_behavior <https://github.com/catalystneuro/neuroconv/tree/main/tests/test_behavior>`_, and
`tests/test_text <https://github.com/catalystneuro/neuroconv/tree/main/tests/test_text>`_

These can be run in isolation using ``pip install -e neuroconv[test,<modality>]`` and calling
``pytest tests/test_<modality>`` where ``<modality>`` can be any of ``ophys``, ``ecephys``, ``text``, or ``behavior``.


.. _example_data:

Testing On Example Data
-----------------------

For proprietary formats, we regularly test our conversions against small snippets of real data, stored somewhere on
your local system. These can each by downloaded using `Datalad <https://www.datalad.org/>`_

For electrophysiology data
""""""""""""""""""""""""""
.. code:: bash

    datalad install -rg https://gin.g-node.org/NeuralEnsemble/ephy_testing_data

For optical physiology data
"""""""""""""""""""""""""""
.. code:: bash

    datalad install -rg https://gin.g-node.org/CatalystNeuro/ophys_testing_data


For behavioral data
"""""""""""""""""""
.. code:: bash

    datalad install -rg https://gin.g-node.org/CatalystNeuro/behavior_testing_data



Running the data tests
""""""""""""""""""""""

Once the data is downloaded to your system, you must manually modify the testing config file
(`example <https://github.com/catalystneuro/neuroconv/blob/main/base_gin_test_config.json>`_). This file should be
located and named as ``tests/test_on_data/gin_test_config.json`` whenever ``neuroconv`` is installed in editable
``-e`` mode). The ``LOCAL_PATH`` field points to the folder on your system that contains the dataset folder (*e.g.*,
``ephy_testing_data`` for testing ``ecephys``). The code will automatically detect that the tests are being run
locally, so all you need to do ensure the path is correct to your specific system.

The output of these tests is, by default, stored in a temporary directory that is then cleaned after the tests finish
running. To examine these files for quality assessment purposes, set the flag ``SAVE_OUTPUTS=true`` in the
``gin_test_config.json`` file and modify the variable ``OUTPUT_PATH`` in the respective test if necessary.

Sub-folders: `tests/test_on_data <https://github.com/catalystneuro/neuroconv/tree/main/tests/test_on_data>`_

These can be run in total using ``pip install -e neuroconv[test,full]`` and calling ``pytest tests/test_on_data`` or
in isolation by installing the required ``<modality>`` as in the previous section and calling
``pytest tests/test_on_data/test_gin_<modality>``.



Update existing test data
"""""""""""""""""""""""""
If you have downloaded these data repositories previously and want to update them, ``cd`` into the directory you want
to update and run

.. code:: bash

    datalad update --how=ff-only --reobtain-data

To update GIN data, run ``datalad update --how=ff-only --reobtain-data`` within the repository you would like to update.
