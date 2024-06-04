import pytest

from neuroconv.datainterfaces.behavior.medpc.medpc_helpers import (
    get_medpc_variables,
    get_session_lines,
    read_medpc_file,
)


@pytest.fixture(scope="module")
def medpc_file_contents():
    return """
Start Date: 04/09/19
End Date: 04/09/19
Subject: 95.259
Experiment:
Group:
Box: 1
Start Time: 10:34:30
End Time: 11:35:53
MSN: FOOD_FR1 TTL Left
A:
     0:      175.150      270.750      762.050      762.900     1042.600
     5:     1567.800     1774.950     2448.450     2454.050     2552.800
    10:     2620.550     2726.250
B:
     0:      175.150      270.750      762.050     1042.600     1567.800
     5:     1774.950     2448.450     2552.800     2620.550     2726.250
C:
     0:      330.050      362.500      947.200     1232.100     1233.400
     5:     1255.200     1309.200     1430.300     1460.500     1466.850
    10:     1468.800     1967.450     2537.950     2542.250     2614.850
    15:     2707.350     2717.700     2801.050     2818.450     3324.450
    20:     3384.750     3538.250


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


def test_get_medpc_variables(tmp_path, medpc_file_contents):
    medpc_file = tmp_path / "test_medpc_file.txt"
    medpc_file.write_text(medpc_file_contents)
    variables = get_medpc_variables(medpc_file, ["Start Date", "End Date", "Subject"])
    assert variables == {
        "Start Date": ["04/09/19", "04/11/19", "04/12/19"],
        "End Date": ["04/09/19", "04/11/19", "04/12/19"],
        "Subject": ["95.259", "95.259", "95.259"],
    }
