from pynwb import NWBFile
from pynwb.behavior import BehavioralEvents
from nwbn_conversion_tools.converter import NWBConverter

from pathlib import Path
from datetime import datetime
from scipy.io import loadmat
import pandas as pd
import numpy as np
import uuid


class Bpod2NWB(NWBConverter):
    def __init__(self, nwbfile=None, metadata=None, source_paths=None):
        """
        Reads behavioral data from bpod files and adds it to nwbfile.

        Parameters
        ----------
        nwbfile: pynwb.NWBFile
        metadata: dict
        source_paths: dict
        """
        super().__init__(nwbfile=nwbfile, metadata=metadata, source_paths=source_paths)

    def create_nwbfile(self, metadata_nwbfile):
        """
        Overriding method to get session_start_time form bpod files.
        """
        nwbfile_args = dict(identifier=str(uuid.uuid4()),)
        nwbfile_args.update(**metadata_nwbfile)
        session_start_time = self.get_session_start_time(self.source_paths['file_behavior_bpod']['path'])
        nwbfile_args.update(**session_start_time)
        self.nwbfile = NWBFile(**nwbfile_args)

    def get_session_start_time(self, file_behavior_bpod):
        """
        Gets session_start_time from bpod file.

        Parameters
        ----------
        file_behavior_bpod: string or Path

        Returns
        -------
        dict
        """
        file_behavior_bpod = Path(file_behavior_bpod)
        # Opens -.mat file and extracts data
        fdata = loadmat(file_behavior_bpod, struct_as_record=False, squeeze_me=True)
        session_start_date = fdata['SessionData'].Info.SessionDate
        session_start_time = fdata['SessionData'].Info.SessionStartTime_UTC
        date_time_string = session_start_date + ' ' + session_start_time
        date_time_obj = datetime.strptime(date_time_string, '%d-%b-%Y %H:%M:%S')
        return {'session_start_time': date_time_obj}

    def add_behavior_timeseries(self, file_behavior_bpod):
        """
        Adds behavioral timeseries from bpod file to nwbfile.
        Parameters
        ----------
        file_behavior_bpod: string or Path
        """
        file_behavior_bpod = Path(file_behavior_bpod)
        # Opens -.mat file and extracts data
        fdata = loadmat(file_behavior_bpod, struct_as_record=False, squeeze_me=True)

        # Summarized trials data
        n_trials = fdata['SessionData'].nTrials
        trials_start_times = fdata['SessionData'].TrialStartTimestamp
        trials_end_times = fdata['SessionData'].TrialEndTimestamp
        trials_types = fdata['SessionData'].TrialTypes
        trials_led_types = fdata['SessionData'].LEDTypes
        trials_reaching = fdata['SessionData'].Reaching
        trials_outcome = fdata['SessionData'].Outcome

        # Raw data - states
        trials_states_names_by_number = fdata['SessionData'].RawData.OriginalStateNamesByNumber
        all_trials_states_names = np.unique(np.concatenate(trials_states_names_by_number, axis=0))
        trials_states_numbers = fdata['SessionData'].RawData.OriginalStateData
        trials_states_timestamps = fdata['SessionData'].RawData.OriginalStateTimestamps
        trials_states_durations = [np.diff(dur) for dur in trials_states_timestamps]

        # # Add trials columns
        self.nwbfile.add_trial_column(name='trial_type', description='no description')
        self.nwbfile.add_trial_column(name='led_type', description='no description')
        self.nwbfile.add_trial_column(name='reaching', description='no description')
        self.nwbfile.add_trial_column(name='outcome', description='no description')
        self.nwbfile.add_trial_column(name='states', description='no description', index=True)

        # Trials table structure:
        # trial_number | start | end | trial_type | led_type | reaching | outcome | states (list)
        trials_states_names = []
        tup_ts = np.array([])
        port_1_in_ts = np.array([])
        port_1_out_ts = np.array([])
        port_2_in_ts = np.array([])
        port_2_out_ts = np.array([])
        for tr in range(n_trials):
            trials_states_names.append([trials_states_names_by_number[tr][number - 1]
                                        for number in trials_states_numbers[tr]])
            self.nwbfile.add_trial(
                start_time=trials_start_times[tr],
                stop_time=trials_end_times[tr],
                trial_type=trials_types[tr],
                led_type=trials_led_types[tr],
                reaching=trials_reaching[tr],
                outcome=trials_outcome[tr],
                states=trials_states_names[tr],
            )

            # Events names: ['Tup', 'Port2In', 'Port2Out', 'Port1In', 'Port1Out']
            trial_events_names = fdata['SessionData'].RawEvents.Trial[tr].Events._fieldnames
            t0 = trials_start_times[tr]
            if 'Port1In' in trial_events_names:
                timestamps = fdata['SessionData'].RawEvents.Trial[tr].Events.Port1In + t0
                port_1_in_ts = np.append(port_1_in_ts, timestamps)
            if 'Port1Out' in trial_events_names:
                timestamps = fdata['SessionData'].RawEvents.Trial[tr].Events.Port1Out + t0
                port_1_out_ts = np.append(port_1_out_ts, timestamps)
            if 'Port2In' in trial_events_names:
                timestamps = fdata['SessionData'].RawEvents.Trial[tr].Events.Port2In + t0
                port_2_in_ts = np.append(port_2_in_ts, timestamps)
            if 'Port2Out' in trial_events_names:
                timestamps = fdata['SessionData'].RawEvents.Trial[tr].Events.Port2Out + t0
                port_2_out_ts = np.append(port_2_out_ts, timestamps)
            if 'Tup' in trial_events_names:
                timestamps = fdata['SessionData'].RawEvents.Trial[tr].Events.Tup + t0
                tup_ts = np.append(tup_ts, timestamps)

        # Add states and durations
        # trial_number | ... | state1 | state1_dur | state2 | state2_dur ...
        for state in all_trials_states_names:
            state_data = []
            state_dur = []
            for tr in range(n_trials):
                if state in trials_states_names[tr]:
                    state_data.append(True)
                    dur = trials_states_durations[tr][trials_states_names[tr].index(state)]
                    state_dur.append(dur)
                else:
                    state_data.append(False)
                    state_dur.append(np.nan)
            self.nwbfile.add_trial_column(
                name=state,
                description='no description',
                data=state_data,
            )
            self.nwbfile.add_trial_column(
                name=state + '_dur',
                description='no description',
                data=state_dur,
            )

        # Add events
        behavioral_events = BehavioralEvents()
        behavioral_events.create_timeseries(name='port_1_in', timestamps=port_1_in_ts)
        behavioral_events.create_timeseries(name='port_1_out', timestamps=port_1_out_ts)
        behavioral_events.create_timeseries(name='port_2_in', timestamps=port_2_in_ts)
        behavioral_events.create_timeseries(name='port_2_out', timestamps=port_2_out_ts)
        behavioral_events.create_timeseries(name='tup', timestamps=tup_ts)

        self.nwbfile.add_acquisition(behavioral_events)
