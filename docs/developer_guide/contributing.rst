## Contributing to the project

We welcome any suggestions to this project! We've done our best to make this as easy as possible for developers to propose new checks.

Begin by raising a ['New Check' issue](https://github.com/NeurodataWithoutBorders/nwbinspector/issues/new/choose) to discuss it with the rest of the team. __Please wait for approval on the Issue before beginning the PR process.__

Once approved, follow these steps to add the new check function to the core registry. We ask that you keep Pull Requests as small as possible to facilitate review; if suggesting the addition of multiple checks, please make a separate Pull Request for each individual check.

1) Use the `register_check` decorator to wrap your new check function. The decorator takes two keyword arguments, the `importance` level and `neurodata_type`.
    Importance level may be one of...

    `Importance.CRITICAL`: Something about the object (usually its `data`) has a high likelihood of being incorrect, but in a way that can't be detected via PyNWB validation.

    `Importance.BEST_PRACTICE_VIOLATION`: The object contains a major violation of something from the [Best Practices](https://www.nwb.org/best-practices/) list.

    `Importance.BEST_PRACTICE_SUGGESTION`: The object contains a minor violation of something from the [Best Practices](https://www.nwb.org/best-practices/) list. Typically used in cases where an informative metadata field is missing.

    The `neurodata_type` is the most general type of object in PyNWB that meets the criteria imposed by the check logic.

2) Begin your function name with `check_`.
3) Write a one-line docstring briefly describing the check and its intention.
4) Use the simplest possible logic for detecting the issue. If the applied logic is general to arbitrary Python data types (_e.g._, any numpy array), consider including it in the `utils`.
5) `if` the issue is detected, `return` an `InspectorMessage` object with an informative `message` detailing what was expected.
6) Inside one of the `tests/unit_tests/` files include tests of both a passing check (where `None` is returned) and a failing check (an `InspectorMessage` is returned).

A good example for reference is

```python
@register_check(importance=Importance.BEST_PRACTICE_SUGGESTION, neurodata_type=NWBFile)
def check_experimenter(nwbfile: NWBFile):
    """Check if an experimenter has been added for the session."""
    if not nwbfile.experimenter:
        return InspectorMessage(message="Experimenter is missing.")
```

with tests

```python
def test_check_experimenter_pass():
    assert check_experimenter(nwbfile=NWBFile(..., experimenter="test_experimenter")) is None

def test_check_experimenter_fail():
    assert check_experimenter(nwbfile=make_minimal_nwbfile()) == InspectorMessage(message="Experimenter is missing.")
```
