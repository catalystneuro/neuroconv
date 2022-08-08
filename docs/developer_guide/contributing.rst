How to contribute to NeuroConv software and documents
=====================================================

.. _sec-code-of-conduct:

Code of Conduct
---------------

This project and everyone participating in it is governed by our `code of conduct guidelines <https://github.com/catalystneuro/neuroconv/blob/main/.github/CODE_OF_CONDUCT.rst>`_. By participating, you are expected to uphold this code. Please report unacceptable behavior.

.. _sec-contribution-types:

Types of Contributions
----------------------

Did you find a bug? or Do you intend to add a new feature or change an existing one?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* **Identify the appropriate repository** for the change you are suggesting:

   * Use `nwb-schema <https://github.com/NeurodataWithoutBorders/nwb-schema/>`_ for any changes to the NWB format schema, schema language, storage, and other NWB related documents
   * Use `PyNWB <https://github.com/NeurodataWithoutBorders/pynwb>`_  for any changes regarding the PyNWB API and the corresponding documentation
   * Use `MatNWB <https://github.com/NeurodataWithoutBorders/matnwb>`_  for any changes regarding the MatNWB API and the corresponding documentation

* **Ensure the feature or change was not already reported** by searching on GitHub under `NeuroConv Issues <https://github.com/catalystneuro/neuroconv/issues>`_ and `NeuroConv Pull Requests <https://github.com/catalystneuro/neuroconv/pulls>`_.

* If you are unable to find an open issue addressing the problem then open a new issue on the respective repository. Be sure to include:

    * **brief and descriptive title**
    * **clear description of the problem you are trying to solve**. Describing the use case is often more important than proposing a specific solution. By describing the use case and problem you are trying to solve gives the development team and ultimately the NWB community a better understanding for the reasons of changes and enables others to suggest solutions.
    * **context** providing as much relevant information as possible and if available a **code sample** or an **executable test case** demonstrating the expected behavior and/or problem.

* Both NeuroConv and NWB are currently being developed primarily by staff at scientific research institutions and industry, most of which work on many different research projects. Please be patient, if our development team is not able to respond immediately to your issues. In particular issues that belong to later project milestones may not be reviewed or processed until work on that milestone begins.

Did you write a patch that fixes a bug or implements a new feature?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
See the :ref:`sec-contributing` section below for details.

Do you have questions about the NWB format?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Ask questions on our `NWB helpdesk <https://github.com/NeurodataWithoutBorders/helpdesk/discussions>`_ or sign up for our
`NWB mailing list <http://visitor.r20.constantcontact.com/manage/optin?v=001nQUq2GTjwCjZxK_V2-6RLElLJO1HMVtoNLJ-wGyDCukZQZxu2AFJmNh6NS0_lGMsWc2w9hZpeNn74HuWdv5RtLX9qX0o0Hy1P0hOgMrkm2NoGAX3VoY25wx8HAtIZwredcCuM0nCUGodpvoaue3SzQ%3D%3D>`_ for updates.

Informal discussions between developers and users?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The https://nwb-users.slack.com slack is currently used mainly for informal discussions between developers and users.

.. _sec-contributing:

Contributing Patches and Changes
--------------------------------

The ``main`` branch of `NeuroConv <https://github.com/catalystneuro/neuroconv>`_ is protected; you cannot push to it directly. You must upload your changes by pushing a new branch, then submit your changes to the ``main`` branch via a `Pull Request <https://help.github.com/articles/creating-a-pull-request>`_. This allows us to conduct automated testing of your contribution, and gives us a space for developers to discuss the contribution and request changes. If you decide to tackle an issue, please make yourself an assignee on the issue to communicate this to the team. Don't worry - this does not commit you to solving this issue. It just lets others know who they should talk to about it.

From your local copy directory, use the following commands.

If you have not already, you will need to clone the repo:

.. code-block:: bash

    $ git clone https://github.com/catalystneuro/neuroconv

1) First create a new branch to work on

.. code-block:: bash

    $ git checkout -b <new_branch>

2) Make your changes.

3) We will automatically run tests to ensure that your contributions didn't break anything and that they follow our style guide. You can speed up the testing cycle by running these tests locally on your own computer by calling ``pytest`` from the top-level directory.

4) Push your feature branch to origin (*i.e.* GitHub)

.. code-block:: bash

    $ git push origin <new_branch>

5) Once you have tested and finalized your changes, create a pull request (PR) targeting ``dev`` as the base branch:

    * Ensure the PR description clearly describes the problem and solution.
    * Include the relevant issue number if applicable. TIP: Writing e.g. "fix #613" will automatically close issue #613 when this PR is merged.
    * Before submitting, please ensure that the code follows the standard coding style of the respective repository.
    * If you would like help with your contribution, or would like to communicate contributions that are not ready to merge, submit a PR where the title begins with "[WIP]."
    * **NOTE:** Contributed branches will be removed by the development team after the merge is complete and should, hence, not be used after the pull request is complete.
