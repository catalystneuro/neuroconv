Running GIN tests locally
=========================

NeuroConv verifies the integrity of all code changes by running a full test suite on short examples of real data from the formats we support.

The testing suite is broken up into sub-folders based on the scope of functionalities and dependencies you wish to test.

We recommend always running tests in a fresh environment to ensure errors are not the result of contaminated dependencies.

There are three broad classes of tests in this regard...



Minimal
-------

These test internal functionality using only minimal dependencies or pre-downloaded data.

Subfolders: `tests/test_minimal <https://github.com/catalystneuro/neuroconv/tree/main/tests/test_minimal>`_ and `tests/test_internals <https://github.com/catalystneuro/neuroconv/tree/main/tests/test_internals>`_

These can be run using only ``pip install -e neuroconv[test]`` and calling ``pytest tests/test_minimal`` or ``pytest tests/test_internal``.



Modality
--------

These test the functionality of our write tools tailored to certain external dependencies.

Subfolders: `tests/test_ophys <https://github.com/catalystneuro/neuroconv/tree/main/tests/test_ophys>`_, `tests/test_ecephys <https://github.com/catalystneuro/neuroconv/tree/main/tests/test_ecephys>`_, `tests/test_behavior <https://github.com/catalystneuro/neuroconv/tree/main/tests/test_behavior>`_, and `tests/test_text <https://github.com/catalystneuro/neuroconv/tree/main/tests/test_text>`_

These can be run in isolation using ``pip install -e neuroconv[test,<modality>]`` and calling ``pytest tests/test_<modality>`` where ``<modality>`` can be any of ``ophys``, ``ecephys``, ``text``, or ``behavior``.



On Data
-------

For proprietary formats, we like to be able to regularly test our conversions against small snnippets of real data.

To reduce the complexity of the testing suite, the tests simply assume that the example datasets exist somewhere on your system.

These can each by downloaded using [Datalad](https://www.datalad.org/) and the example datasets can be found at

For electrophysiology data
""""""""""""""""""""""""""
``datalad install -rg https://gin.g-node.org/NeuralEnsemble/ephy_testing_data``

For optical physiology data
"""""""""""""""""""""""""""
``datalad install -rg https://gin.g-node.org/CatalystNeuro/ophys_testing_data``

For behavioral data
"""""""""""""""""""
``datalad install -rg https://gin.g-node.org/CatalystNeuro/behavior_testing_data``

Once the data is downloaded to your system, you must manually modify the config file ([example](https://github.com/catalystneuro/neuroconv/blob/main/base_gin_test_config.json)) located in `tests/test_on_data/gin_test_config.json` (a file automatically generated whenever you install `neuroconv` in editable `-e` mode). The `LOCAL_PATH` field points to the folder on your system that contains the dataset folder (_e.g._, `ephy_testing_data` for testing `ecephys`). The code will automatically detect that the tests are being run locally, so all you need to do ensure the path is correct to your specific system.

The output of these tests is, by default, stored in a temporary directory that is then cleaned after the tests finish running. To examine these files for quality assessment purposes, set the flag `SAVE_OUTPUTS=true` in the `gin_test_config.json` file and modify the variable `OUTPUT_PATH` in the respective test if necessary.

Subfolders: `tests/test_on_data <https://github.com/catalystneuro/neuroconv/tree/main/tests/test_on_data>`_

These can be run in total using ``pip install -e neuroconv[test,full]`` and calling ``pytest tests/test_on_data`` or in isolation by installing the required ``<modality>`` as in the previous section and calling ``pytest tests/test_on_data/test_gin_<modality>``.
