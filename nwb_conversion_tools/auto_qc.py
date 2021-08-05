import numpy as np
from pynwb import NWBHDF5IO


def check_sorted(data):
    dd = data[:]
    if not np.all(dd == np.sort(dd)):
        print(data.name + " is not ordered")


def check_binary(data):
    if len(np.unique(data[:])) == 2:
        print(data.name + " is binary. Consider making it boolean.")


def check_time_dim(time_series):
    if hasattr(time_series, "timestamps") and time_series.timestamps is not None:
        if not len(time_series.data) == len(time_series.timestamps):
            print(time_series.name + "data and timestamp length mismatch")
    else:
        shape = time_series.data.shape
        if len(shape) > 1:
            if not shape[0] == max(shape):
                print(time_series.name + " time is not the longest dimension")


def check_constant_rate(time_series):
    if hasattr(time_series, "timestamps") and time_series.timestamps is not None:
        if len(np.unique(np.diff(time_series.timestamps))) == 1:
            print(time_series.name + " sampling rate is constant. " "Consider using rate instead of timestamps")


def auto_qc(fpath):
    io = NWBHDF5IO(fpath, "r", load_namespaces=True)
    nwb = io.read()

    # trials
    print("trials:")
    check_sorted(nwb.trials["start_time"])
    check_sorted(nwb.trials["stop_time"])

    for col in nwb.trials.columns:
        if col.data.dtype == np.dtype("O"):
            check_binary(col)
