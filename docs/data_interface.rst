Build a DataInterface
------------------------------------------

Building a new :code:`DataInterface` for a specific file format is as simple as creating a new
subclass based on the predefined base classes provided in the
`nwb-conversion-tools <https://github.com/catalystneuro/nwb-conversion-tools>`_ package.

To enable standardization among subclasses, the :code:`BaseDataInterface` is an abstract base class which require a new
subclass to **override all methods which are decorated with @abstractmethod**. The :code:`BaseDataInterface` class has several abstract methods: :code:`get_source_schema()`, :code:`get_metadata_schema()`, :code:`get_metadata()`, and most importantly :code:`run_conversion()`. So all you need to do is create a class that inherits from :code:`:code:`BaseDataInterface`` and implements these two methods.

Along with these two methods, you can also optionally override the :code:`__init__()` function as needed to instantiate additional data.

The contributed extractors are in the **nwb-conversion-tools/datainterfaces** folder. You can fork the repo and create a new file
**myformatdatainterface** there. In the folder, create a new file named **myformatdatainterface.py**.

.. code-block:: python
        ...


When you are done we recommend you write a test in the **tests/test_interfaces.py** to ensure it works as expected.

Finally, make a pull request to the `nwb-conversion-tools <https://github.com/catalystneuro/nwb-conversion-tools>`_ repo, so we can review the code and merge it to the NWB conversion tools!