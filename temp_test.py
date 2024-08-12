import shutil
from datetime import datetime
from pathlib import Path

from lerner_lab_to_nwb.seiler_2024.seiler_2024_convert_session import session_to_nwb


def main():
    # Parameters for conversion
    data_dir_path = Path("/Volumes/T7/CatalystNeuro/Lerner/raw_data")
    output_dir_path = Path("/Volumes/T7/CatalystNeuro/Lerner/conversion_nwb")
    stub_test = False

    if output_dir_path.exists():
        shutil.rmtree(
            output_dir_path, ignore_errors=True
        )  # ignore errors due to MacOS race condition (https://github.com/python/cpython/issues/81441)

    # Fiber Photometry session
    experiment_type = "FP"
    experimental_group = "PS"
    subject_id = "112.283"
    start_datetime = datetime(2019, 6, 20, 9, 32, 4)
    session_conditions = {
        "Start Date": start_datetime.strftime("%m/%d/%y"),
        "Start Time": start_datetime.strftime("%H:%M:%S"),
    }
    start_variable = "Start Date"
    behavior_file_path = (
        data_dir_path
        / f"{experiment_type} Experiments"
        / "Behavior"
        / f"{experimental_group}"
        / f"{subject_id}"
        / f"{subject_id}"
    )
    fiber_photometry_folder_path = (
        data_dir_path
        / f"{experiment_type} Experiments"
        / "Photometry"
        / f"Punishment Sensitive"
        / f"Early RI60"
        / f"Photo_{subject_id.split('.')[0]}_{subject_id.split('.')[1]}-190620-093542"
    )
    session_to_nwb(
        data_dir_path=data_dir_path,
        output_dir_path=output_dir_path,
        behavior_file_path=behavior_file_path,
        fiber_photometry_folder_path=fiber_photometry_folder_path,
        has_demodulated_commanded_voltages=False,
        subject_id=subject_id,
        session_conditions=session_conditions,
        start_variable=start_variable,
        experiment_type=experiment_type,
        experimental_group=experimental_group,
        stub_test=stub_test,
    )


if __name__ == "__main__":
    main()
