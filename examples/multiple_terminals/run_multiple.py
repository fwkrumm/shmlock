"""
This script can be used to test lock mechanism called from multiple terminals.

So open as many consoles as you want and run this script via
python run.py (or python3 run.py on unix systems)
you do not need to time the startup, each script will check the current shm value to be
incremented at start up.

if the script finishes to quickly, you can increase the number of runs (RUNS) or
the delay for locks (DELAY_FOR_LOCKS) below

to test the lock mechanism, set USE_LOCK to True, otherwise it will run without locks.
if you set USE_LOCK=False you will get assertion errors in a non-deterministic manner because of
race conditions (which is expected). Of course if you use locks the code will run slower.

A analysis of the performance is located elsewhere in the repository. However for the sake
of completeness, there is a measurement of the overall time for the code execution.
"""

import time
import struct
import sys
import os
from multiprocessing import shared_memory

try:
    import shmlock
except ImportError:
    print("trying to import from root directory")
    current_dir = os.path.dirname(os.path.abspath(__file__))
    new_path = os.path.join(current_dir, "..", "..")
    sys.path.append(new_path)
    import shmlock # pylint:disable=(wrong-import-position)

#
# change this value to run case with or without locking
#
USE_LOCK = True # significantly faster without lock but access not synchronized



LOCK_NAME = "lock_shared_memory"
RESULT_SHM_NAME = "result_shared_memory"

RUNS = 10000
DELAY_FOR_LOCKS = 0 # used to "fake" delay to simulate some work

if not USE_LOCK:
    # extend run time so that the script does not finish too quickly
    DELAY_FOR_LOCKS = 0.01

if __name__ == "__main__":


    print("Starting example for", RUNS, "runs.")
    start = time.perf_counter()

    lock = shmlock.ShmLock(LOCK_NAME, poll_interval=0.01)
    result = None
    try:
        try:
            # first console in which this script runs will create the shared memory
            result = shared_memory.SharedMemory(name=RESULT_SHM_NAME, create=True, size=8)
        except FileExistsError:
            # all other consoles will just attach to the shared memory
            result = shared_memory.SharedMemory(name=RESULT_SHM_NAME)

        def run():
            """simple run function to increment the value within shared memory"""
            current_value = struct.unpack_from("Q", result.buf, 0)[0]
            if DELAY_FOR_LOCKS:
                time.sleep(DELAY_FOR_LOCKS)
            struct.pack_into("Q", result.buf, 0, current_value + 1)

            check_buf = struct.unpack_from("Q", result.buf, 0)[0]
            assert check_buf == current_value + 1, \
                f"result {check_buf} not as expected being {current_value + 1}; "

        for _ in range(RUNS):
            if USE_LOCK:
                with lock:
                    run()
            else:
                run()
    finally:
        if result is not None:
            result.close()
            # the last console should also call unlink to remove the shared memory
    end = time.perf_counter()

    print("no errors occurred. Overall run time: ", end - start)
