import shutil
from datetime import datetime
from pathlib import Path

from pytz import timezone

from neuroconv.datainterfaces import MedPCInterface


def main():
    data_dir_path = Path("/Volumes/T7/CatalystNeuro/NWB/Lerner/raw_data")
    output_dir_path = Path("/Volumes/T7/CatalystNeuro/NWB/Lerner/conversion_nwb")
    if output_dir_path.exists():
        shutil.rmtree(output_dir_path, ignore_errors=True)
    output_dir_path.mkdir(parents=True, exist_ok=True)
    experiment_type = "FP"
    experimental_group = "RR20"
    subject_id = "95.259"
    start_datetime = datetime(2019, 4, 18, 10, 41, 42)
    session_conditions = {
        "Start Date": start_datetime.strftime("%m/%d/%y"),
        "Start Time": start_datetime.strftime("%H:%M:%S"),
    }
    start_variable = "Start Date"
    file_path = str(
        data_dir_path
        / f"{experiment_type} Experiments"
        / "Behavior"
        / f"{experimental_group}"
        / f"{subject_id}"
        / f"{subject_id}"
    )
    metadata_medpc_name_to_info_dict = {
        "Start Date": {"name": "start_date", "is_array": False},
        "Subject": {"name": "subject", "is_array": False},
        "Box": {"name": "box", "is_array": False},
        "Start Time": {"name": "start_time", "is_array": False},
        "MSN": {"name": "MSN", "is_array": False},
    }

    interface = MedPCInterface(
        file_path=file_path,
        session_conditions=session_conditions,
        start_variable=start_variable,
        metadata_medpc_name_to_info_dict=metadata_medpc_name_to_info_dict,
        verbose=True,
    )
    metadata = interface.get_metadata()
    start_date = datetime.strptime(metadata["MedPC"]["start_date"], "%m/%d/%y").date()
    start_time = datetime.strptime(metadata["MedPC"]["start_time"], "%H:%M:%S").time()
    session_start_time = datetime.combine(start_date, start_time)
    cst = timezone("US/Central")
    metadata["NWBFile"]["session_start_time"] = session_start_time.replace(tzinfo=cst)
    metadata["MedPC"]["medpc_name_to_info_dict"] = {
        "A": {"name": "left_nose_poke_times", "is_array": True},
        "B": {"name": "left_reward_times", "is_array": True},
        "C": {"name": "right_nose_poke_times", "is_array": True},
        "D": {"name": "right_reward_times", "is_array": True},
        "E": {"name": "duration_of_port_entry", "is_array": True},
        "G": {"name": "port_entry_times", "is_array": True},
        "H": {"name": "footshock_times", "is_array": True},
    }
    metadata["MedPC"]["Events"] = [
        {
            "name": "left_nose_poke_times",
            "description": "Left nose poke times",
        },
        {
            "name": "left_reward_times",
            "description": "Left reward times",
        },
        {
            "name": "right_nose_poke_times",
            "description": "Right nose poke times",
        },
        {
            "name": "right_reward_times",
            "description": "Right reward times",
        },
        {
            "name": "footshock_times",
            "description": "Footshock times",
        },
    ]
    metadata["MedPC"]["IntervalSeries"] = [
        {
            "name": "reward_port_intervals",
            "description": "Interval of time spent in reward port (1 is entry, -1 is exit)",
            "onset_name": "port_entry_times",
            "duration_name": "duration_of_port_entry",
        },
    ]
    nwbfile_path = output_dir_path / "test_medpc.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)


if __name__ == "__main__":
    main()
