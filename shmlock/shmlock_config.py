"""
config dataclass for the shared memory lock
"""

import multiprocessing
import multiprocessing.synchronize
import threading
from dataclasses import dataclass
from typing import Union

from shmlock.shmlock_uuid import ShmUuid

@dataclass
class ShmLockConfig(): # pylint: disable=(too-many-instance-attributes)
    """
    data class to store the configuration parameters of the lock

    TODO we could include a type check in this dataclass

    Attributes
    ----------
    name : str
        name of the lock i.e. the shared memory block
    poll_interval : float
        time delay in seconds after a failed acquire try after which it will be tried
        again to acquire the lock
    exit_event : multiprocessing.synchronize.Event | threading.Event
        if None is provided a new one will be initialized. if event is set to true
        -> acquirement will stop and it will not be possible to acquire a lock until event is
        unset/cleared
    track : bool
        set to False if you do want the shared memory block been tracked.
        This is parameter only supported for python >= 3,13 in SharedMemory
        class
    timeout : float
        max timeout in seconds until lock acquirement is aborted
    uuid : ShmUuid
        uuid of the lock
    description : str, optional
        custom description of the lock which can be set as property setter, by default ""
    """
    name: str
    poll_interval: Union[float, int]
    exit_event: Union[multiprocessing.synchronize.Event, threading.Event]
    track: bool
    timeout: float
    uuid: ShmUuid
    pid: int # process id of the lock instance (should stay the same as
             # long as the user does not share the lock via forking which is
             # STRONGLY DISCOURAGED!)
    description: str = "" # custom description
