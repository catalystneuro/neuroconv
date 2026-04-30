import numpy as np
import pytest

from neuroconv.datainterfaces.behavior.medpc.medpc_helpers import (
    _get_session_lines,
    get_medpc_variables,
    read_medpc_file,
)


@pytest.fixture(scope="function")
def medpc_file_path(tmp_path):
    content = """
Start Date: 04/09/19
End Date: 04/09/19
Subject: 95.259
Experiment:
\\ This line is a comment
Group:
Box: 1
Start Time: 10:34:30
End Time: 11:35:53
MSN: FOOD_FR1 TTL Left
A:
     0:      175.150      270.750      762.050      762.900     1042.600
     5:     1567.800     1774.950     2448.450     2454.050     2552.800
    10:     2620.550     2726.250     0.000000     0.000000     0.000000
B:
     0:      175.150      270.750      762.050     1042.600     1567.800
     5:     1774.950     2448.450     2552.800     2620.550     2726.250
    10:        0.000        0.000        0.000        0.000        0.000
C:
     0:      330.050      362.500      947.200     1232.100     1233.400
     5:     1255.200     1309.200     1430.300     1460.500     1466.850
    10:     1468.800     1967.450     2537.950     2542.250     2614.850
    15:     2707.350     2717.700     2801.050     2818.450     3324.450
    20:     3384.750     3538.250								someGarbage-9172937 more garbage


Start Date: 04/11/19
End Date: 04/11/19
Subject: 95.259
Experiment:
Group:
Box: 1
Start Time: 09:41:34
End Time: 10:41:38
MSN: FOOD_FR1 TTL Left
A:
     0:       37.000      155.800      246.600      286.350      301.150
     5:      378.650      455.600      480.250      501.500      634.550
    10:      639.050      656.050      656.400      658.400      660.900
    15:      663.300      664.200      666.600      668.150      677.650
B:
     0:       37.000      155.800      246.600      286.350      301.150
     5:      378.650      455.600      480.250      501.500      639.050
    10:      677.650      695.650      747.250      820.550      973.000
    15:      992.050     1031.700     1110.050     1446.750     1480.950
C:
     0:      626.250      626.500      691.250     1098.900     1202.150
     5:     1813.750     2718.550     3264.450     3413.600     3473.300


Start Date: 04/12/19
End Date: 04/12/19
Subject: 95.259
Experiment:
Group:
Box: 1
Start Time: 12:40:18
End Time: 13:18:18
MSN: RR10_Left_AHJS
A:
     0:       52.300       72.050      101.300      106.200      106.600
     5:      133.200      135.350      152.550      153.000      155.300
    10:      166.100      166.700      177.550      184.300      184.950
    15:      188.300      188.800      191.150      191.550      218.450
B:
C:
     0:       99.200      215.500      278.600      283.850      311.450
     5:      314.500      438.950      480.650      503.500      521.300
    10:      573.150      579.100      616.350      649.100      665.150
    15:      666.150      702.550      703.350      703.850      706.300
"""
    medpc_file_path = tmp_path / "medpc_file.txt"
    medpc_file_path.write_text(content)
    return medpc_file_path


def test_get_medpc_variables(medpc_file_path):
    variables = get_medpc_variables(medpc_file_path, ["Start Date", "End Date", "Subject"])
    assert variables == {
        "Start Date": ["04/09/19", "04/11/19", "04/12/19"],
        "End Date": ["04/09/19", "04/11/19", "04/12/19"],
        "Subject": ["95.259", "95.259", "95.259"],
    }


@pytest.mark.parametrize(
    "session_conditions, start_variable, expected_slice",
    [
        ({"Start Date": "04/09/19", "Start Time": "10:34:30"}, "Start Date", slice(1, 25)),
        ({"Start Date": "04/11/19", "Start Time": "09:41:34"}, "Start Date", slice(27, 49)),
        ({"Start Date": "04/12/19", "Start Time": "12:40:18"}, "Start Date", slice(51, 73)),
    ],
)
def test_get_session_lines(medpc_file_path, session_conditions, start_variable, expected_slice):
    with open(medpc_file_path, "r") as f:
        lines = f.readlines()
    session_lines = _get_session_lines(lines, session_conditions, start_variable)
    expected_session_lines = lines[expected_slice]
    assert session_lines == expected_session_lines


def test_get_session_lines_invalid_session_conditions(medpc_file_path):
    with open(medpc_file_path, "r") as f:
        lines = f.readlines()
    session_conditions = {"Invalid": "session condition"}
    start_variable = "Start Date"
    with pytest.raises(ValueError) as exc_info:
        _get_session_lines(lines, session_conditions, start_variable)
    assert str(exc_info.value) == f"Could not find the session with conditions {session_conditions}"


def test_get_session_lines_invalid_start_variable(medpc_file_path):
    with open(medpc_file_path, "r") as f:
        lines = f.readlines()
    session_conditions = {"Start Date": "04/09/19", "Start Time": "10:34:30"}
    start_variable = "Invalid Start Variable"
    with pytest.raises(ValueError) as exc_info:
        _get_session_lines(lines, session_conditions, start_variable)
    assert (
        str(exc_info.value)
        == f"Could not find the start variable ({start_variable}) of the session with conditions {session_conditions}"
    )


def test_get_session_lines_ambiguous_session_conditions(medpc_file_path):
    with open(medpc_file_path, "r") as f:
        lines = f.readlines()
    session_conditions = {"Subject": "95.259"}
    start_variable = "Start Date"
    session_lines = _get_session_lines(lines, session_conditions, start_variable)
    expected_session_lines = lines[1:25]
    assert session_lines == expected_session_lines


def test_read_medpc_file(medpc_file_path):
    medpc_name_to_info_dict = {
        "Start Date": {"name": "start_date", "is_array": False},
        "End Date": {"name": "end_date", "is_array": False},
        "Subject": {"name": "subject", "is_array": False},
        "Experiment": {"name": "experiment", "is_array": False},
        "Group": {"name": "group", "is_array": False},
        "Box": {"name": "box", "is_array": False},
        "Start Time": {"name": "start_time", "is_array": False},
        "End Time": {"name": "end_time", "is_array": False},
        "MSN": {"name": "msn", "is_array": False},
        "A": {"name": "a", "is_array": True},
        "B": {"name": "b", "is_array": True},
        "C": {"name": "c", "is_array": True},
    }
    session_conditions = {"Start Date": "04/09/19", "Start Time": "10:34:30"}
    start_variable = "Start Date"
    session_dict = read_medpc_file(medpc_file_path, medpc_name_to_info_dict, session_conditions, start_variable)
    expected_session_dict = {
        "start_date": "04/09/19",
        "end_date": "04/09/19",
        "subject": "95.259",
        "experiment": "",
        "group": "",
        "box": "1",
        "start_time": "10:34:30",
        "end_time": "11:35:53",
        "msn": "FOOD_FR1 TTL Left",
        "a": np.array(
            [
                175.150,
                270.750,
                762.050,
                762.900,
                1042.600,
                1567.800,
                1774.950,
                2448.450,
                2454.050,
                2552.800,
                2620.550,
                2726.250,
            ]
        ),
        "b": np.array(
            [
                175.150,
                270.750,
                762.050,
                1042.600,
                1567.800,
                1774.950,
                2448.450,
                2552.800,
                2620.550,
                2726.250,
            ]
        ),
        "c": np.array(
            [
                330.050,
                362.500,
                947.200,
                1232.100,
                1233.400,
                1255.200,
                1309.200,
                1430.300,
                1460.500,
                1466.850,
                1468.800,
                1967.450,
                2537.950,
                2542.250,
                2614.850,
                2707.350,
                2717.700,
                2801.050,
                2818.450,
                3324.450,
                3384.750,
                3538.250,
            ]
        ),
    }
    assert session_dict["start_date"] == expected_session_dict["start_date"]
    assert session_dict["end_date"] == expected_session_dict["end_date"]
    assert session_dict["subject"] == expected_session_dict["subject"]
    assert session_dict["experiment"] == expected_session_dict["experiment"]
    assert session_dict["group"] == expected_session_dict["group"]
    assert session_dict["box"] == expected_session_dict["box"]
    assert session_dict["start_time"] == expected_session_dict["start_time"]
    assert session_dict["end_time"] == expected_session_dict["end_time"]
    assert session_dict["msn"] == expected_session_dict["msn"]
    assert np.array_equal(session_dict["a"], expected_session_dict["a"])
    assert np.array_equal(session_dict["b"], expected_session_dict["b"])
    assert np.array_equal(session_dict["c"], expected_session_dict["c"])


def test_read_medpc_file_invalid_multiline_variable(medpc_file_path):
    medpc_name_to_info_dict = {
        "Start Date": {"name": "start_date", "is_array": True},
    }
    session_conditions = {"Start Date": "04/09/19", "Start Time": "10:34:30"}
    start_variable = "Start Date"
    with pytest.raises(ValueError) as exc_info:
        session_dict = read_medpc_file(medpc_file_path, medpc_name_to_info_dict, session_conditions, start_variable)
    assert str(exc_info.value) == "Expected start_date to be a multiline variable, but found a single line variable."
