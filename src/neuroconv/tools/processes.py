"""Collection of helper functions for managing processes."""

import subprocess
from typing import Optional

import psutil


def _kill_process(proc):
    """Private helper for ensuring a process and any subprocesses are properly terminated after a timeout period."""
    try:
        process = psutil.Process(proc.pid)
        for proc in process.children(recursive=True):
            proc.kill()
        process.kill()
    except psutil.NoSuchProcess:  # good process cleaned itself up
        pass


def deploy_process(command, catch_output: bool = False, timeout: Optional[float] = None):
    """Private helper for efficient submission and cleanup of shell processes."""
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True, text=True)
    output = proc.communicate()[0].strip() if catch_output else None
    proc.wait(timeout=timeout)
    _kill_process(proc=proc)
    return output
