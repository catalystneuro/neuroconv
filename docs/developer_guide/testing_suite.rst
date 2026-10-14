.. _testing_suite:

Testing Suite
=============

NeuroConv verifies the integrity of all code changes by running a full test suite on short examples of real data from
the formats we support. The testing suite is broken up into sub-folders based on the scope of functionalities and
dependencies you wish to test. We recommend always running tests in a fresh environment to ensure errors are not the
result of contaminated dependencies.

There are several categories of tests in the NeuroConv codebase:

1. **Minimal Tests**: Core functionality tests. These tests should work only with base dependencies.
2. **Modality Tests**: Tests for machinery of the different data modalities (ecephys, ophys, etc.).
3. **Example Data Tests**: Tests that run on real data examples. This needs the full dependencies and data downloaded from gin.
4. **Remote Transfer Services**: Tests for external cloud service integrations
5. **Import Structure Tests**: Tests that verify the import structure of the package and ensure that top level packages can be imported with minimal installation.

For details on how these test categories map to CI/CD workflows that run automatically on pull
requests, daily schedules, and releases, see :ref:`ci_workflows`.

Run all tests
-------------
To run all tests, first clone the repo and ``cd`` into it.

.. code:: bash

  git clone https://github.com/catalystneuro/neuroconv.git
  cd neuroconv


Then install all required and optional dependencies in a fresh environment.

.. code:: bash

  pip install --editable ".[full]"
  pip install --group test


Then simply run all tests with pytest

.. code:: bash

  pytest

.. note::

  You will likely observe many failed tests if the test data is not available. See the section 'Testing on Example Data' for instructions on how to download the test data.


Minimal Tests
-------------

These test internal functionality using only minimal dependencies or pre-downloaded data.

Sub-folders: `tests/test_minimal <https://github.com/catalystneuro/neuroconv/tree/main/tests/test_minimal>`_

These can be run using only ``pip install --editable "."``, ``pip install --group test`` and calling ``pytest tests/test_minimal``


Modality Tests
--------------

These test the functionality of our write tools tailored to specific modalities such as electrophysiology, optical physiology, behavior, etc.
The tests are broken up into sub-folders based on the modality being tested.

Modalities:

* `ophys <https://github.com/catalystneuro/neuroconv/tree/main/tests/test_modalities/test_ophys>`_
* `fiber_photometry <https://github.com/catalystneuro/neuroconv/tree/main/tests/test_modalities/test_fiber_photometry>`_
* `image <https://github.com/catalystneuro/neuroconv/tree/main/tests/test_modalities/test_image>`_
* `ecephys <https://github.com/catalystneuro/neuroconv/tree/main/tests/test_modalities/test_ecephys>`_
* `behavior <https://github.com/catalystneuro/neuroconv/tree/main/tests/test_modalities/test_behavior>`_
* `text <https://github.com/catalystneuro/neuroconv/tree/main/tests/test_modalities/test_text>`_

These can be run in isolation using ``pip install --editable ".[<modality>]"``, ``pip install --group test`` and calling
``pytest tests/test_modalities/test_<modality>`` where ``<modality>`` can be any of ``ophys``, ``fiber_photometry``, ``ecephys``, ``image``, ``text``, or ``behavior``.

Ideally, these tests should not require data and run in mock testing interfaces but there are exceptions.

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
locally, so all you need to do ensure the path is correct in your specific system.

The output of these tests is, by default, stored in a temporary directory that is then cleaned after the tests finish
running. To examine these files for quality assessment purposes, set the flag ``SAVE_OUTPUTS=true`` in the
``gin_test_config.json`` file and modify the variable ``OUTPUT_PATH`` in the respective test if necessary.

Sub-folders: `tests/test_on_data <https://github.com/catalystneuro/neuroconv/tree/main/tests/test_on_data>`_

These can be run in total using ``pip install --editable ".[full]"``, ``pip install --group test`` and calling ``pytest tests/test_on_data`` or
in isolation by installing the required ``<modality>`` as in the previous section and calling
``pytest tests/test_on_data/<modality>``.


Update existing test data
"""""""""""""""""""""""""
If you have downloaded these data repositories previously and want to update them, ``cd`` into the directory you want
to update and run

.. code:: bash

    datalad update --how=ff-only --reobtain-data

To update GIN data, run the command above within the repository you would like to update.

Remote Transfer Services
------------------------

These tests verify the functionality of tools that interact with external cloud services for data transfer and storage operations. They require actual credentials and API keys to communicate with live services such as AWS, DANDI, and Globus.

**Important**: These tests are not automatically collected by pytest's default collection mechanism because they don't follow the "test_" naming convention in their filenames. This is intentional to prevent them from running during regular test runs, as they require specific credentials and can take longer to execute.

Sub-folders: `tests/remote_transfer_services <https://github.com/catalystneuro/neuroconv/tree/main/tests/remote_transfer_services>`_

External Contributors
"""""""""""""""""""""

**If you are an external contributor**, live service tests will fail in your fork with clear error messages. This is expected behavior.

**This only matters if your PR modifies live service testing code.** If your changes are unrelated to remote transfer services (DANDI, EMBER, AWS, Globus), you can safely ignore these test failures.

These tests require repository secrets (API keys and AWS credentials) that are only available to maintainers.
External contributors cannot run these tests in their own forks due to GitHub's security model, which does not expose secrets to forks.

**Workflow for external contributors:**

1. Develop your changes and ensure all other tests pass (minimal, modality, and example data tests)
2. Submit your pull request
3. When your PR is ready for final review and all non-live-service tests are passing, notify a maintainer
4. A maintainer will fork your PR into the main repository to run the live service tests
5. If the live service tests pass, the maintainer will merge your changes

This workflow ensures that:

* Your development process is not blocked by lack of credentials
* The integrity of live service tests is maintained
* Security credentials remain protected

If you see live service test failures in your PR, this is normal and expected. Focus on ensuring that all other test categories pass.

Required credentials
""""""""""""""""""""
To run these tests, you need to set up the following environment variables:

* For DANDI tests: ``DANDI_API_KEY``
* For EMBER tests: ``EMBER_API_KEY``
* For AWS tests: ``AWS_ACCESS_KEY_ID``, ``AWS_SECRET_ACCESS_KEY``, and ``S3_GIN_BUCKET``
* For Globus tests: Globus CLI must be installed and you must be logged in (``globus login``)

Running remote transfer tests
"""""""""""""""""""""""""""""
Since these tests are not automatically collected, you need to run them explicitly:

.. code:: bash

    # Install required dependencies
    pip install --editable ".[dandi,aws,spikeglx,phy]"
    pip install --group test

    # Run specific service tests (requires appropriate credentials)
    pytest tests/remote_transfer_services/dandi_transfer_tools.py
    pytest tests/remote_transfer_services/ember_transfer_tools.py
    pytest tests/remote_transfer_services/yaml_dandi_transfer_tools.py
    pytest tests/remote_transfer_services/globus_transfer_tools.py
    pytest tests/remote_transfer_services/aws_tools_tests.py
    pytest tests/remote_transfer_services/yaml_aws_tools_tests.py
    pytest tests/remote_transfer_services/neuroconv_deployment_aws_tools_tests.py

Import Structure Tests
----------------------

The `tests/imports.py` file contains tests that verify the import structure of the NeuroConv package. These tests ensure that the package can be imported correctly and that all expected modules and attributes are available in the correct namespaces.

These tests are particularly important for ensuring that the package's public API remains stable and that dependencies are correctly managed. They verify that:

1. The top-level package imports expose the expected classes and functions
2. The tools submodule contains all required utilities
3. The datainterfaces submodule correctly exposes all interface classes

To run these tests specifically:

.. code:: bash

    pytest tests/imports.py::TestImportStructure::test_top_level
    pytest tests/imports.py::TestImportStructure::test_tools
    pytest tests/imports.py::TestImportStructure::test_datainterfaces
