"""
example script to run performance analysis for different poll intervals
"""
# pylint: disable=(duplicate-code)
import time
import sys
import os
import struct
import multiprocessing
import multiprocessing.synchronize
from multiprocessing import shared_memory
import logging


try:
    import shmlock
except ImportError:
    print("trying to import from root directory")
    current_dir = os.path.dirname(os.path.abspath(__file__))
    new_path = os.path.join(current_dir, "..", "..")
    sys.path.append(new_path)
    import shmlock # pylint:disable=(wrong-import-position)


# specify test parameters
NUM_RUNS = 1000
NUM_PROCESSES = 15

shmlock.enable_disable_warnings(False)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("LoggerExamplePollIntervalComparison")

# to prevent log spamming if process spawns
log_buffer = {"info": [], "error": []}

if os.name == "posix":
    shmlock.remove_shm_from_resource_tracker("", print_warning=False)
    log_buffer.get("info").append("Removed shared memory from resource tracker "\
                                  "for increased performance.\n\n")
else:
    log_buffer.get("info").append("Not removing shared memory from resource tracker\n\n")


RESULT_SHM_NAME = "shared_memory_with_results"


def worker_interval(poll_interval: float,
                    lock_name: str,
                    start_event: multiprocessing.synchronize.Event,
                    time_measure_queue: multiprocessing.Queue):
    """
    worker_interval function for performance tests w.r.t. poll interval
    i.e. the shmlock will do the same task for different poll intervals

    Parameters
    ----------
    poll_interval : float
        poll interval to be used for shmlock
    lock_name : str
        name of the lock being used amongst all processes
    start_event : multiprocessing.synchronize.Event
        synchronization event to start all processes at the same time
    time_measure_queue : multiprocessing.Queue
        queue to store time measurements

    Raises
    ------
    ValueError
        if invalid test type has been used
    """
    result = None

    try:
        result = shared_memory.SharedMemory(name=RESULT_SHM_NAME)

        shmlock.init_custom_resource_tracking()
        shm_lock = shmlock.ShmLock(lock_name, poll_interval=poll_interval)

        time_measure = []

        # log.info("waiting for start event to be set")
        start_event.wait()

        for _ in range(NUM_RUNS):
            # for each run measure time for lock acquirement and release
            start = time.perf_counter()
            try:
                shm_lock.acquire()
                current_value = struct.unpack_from("Q", result.buf, 0)[0]
                struct.pack_into("Q", result.buf, 0, current_value + 1)
            finally:
                shm_lock.release()
            end = time.perf_counter()
            time_measure.append(end - start)

        # put data to queue
        time_measure_queue.put(time_measure)
        time_measure_queue.close()

    finally:
        if result is not None:
            result.close()

if __name__ == "__main__":

    log.info("Running %s", __file__)

    procs = []

    # for ''unique logging'' for process spawning
    if len(log_buffer) > 0:
        for key, value in log_buffer.items():
            # log level according to key
            for val in value:
                getattr(log, key)(val)

    START_EVENT = multiprocessing.Event()
    RESULT = None
    try:
        RESULT = shared_memory.SharedMemory(name=RESULT_SHM_NAME, create=True, size=8)
        LOCK_NAME = "test_lock" # use the same lock for all processes
        server_proc = None

        for INTERVAL in (0.0005, 0.01, 0.04, 0.05, 0.1): # 0.05 default at the moment
            log.info("Running poll interval %f", INTERVAL)
            RESULT.buf[:] = bytearray(len(RESULT.buf[:]) * [0])

            # queue to collect results
            TIME_MEASUREMENT_QUEUE = multiprocessing.Queue()
            for i in range(NUM_PROCESSES):
                proc = multiprocessing.Process(target=worker_interval,
                                               args=(INTERVAL,
                                                     LOCK_NAME,
                                                     START_EVENT,
                                                     TIME_MEASUREMENT_QUEUE,))
                procs.append(proc)
                proc.start()

            time.sleep(1) # give processes some time
            START_EVENT.set()

            # collect data from queue
            time_measures = []
            # NOTE that this blocks until all processes have finished
            for _ in range(NUM_PROCESSES):
                time_measures.extend(TIME_MEASUREMENT_QUEUE.get())

            for proc in procs:
                proc: multiprocessing.Process
                # be aware
                # https://docs.python.org/2/library/multiprocessing.html#programming-guidelines
                # "Joining processes that use queues"
                proc.join()


            mean = sum(time_measures) / len(time_measures)
            variance = sum((x - mean) ** 2 for x in time_measures) / len(time_measures)
            standard_deviation = variance ** 0.5

            final_res = struct.unpack_from("Q", RESULT.buf, 0)[0]

            assert final_res == NUM_PROCESSES*NUM_RUNS,\
                "lock failed! this should never happen. expected result "\
                f"{NUM_PROCESSES*NUM_RUNS} != actual result {final_res}"

            # print results
            log.info("Test poll interval %f:", INTERVAL)
            log.info("average time: %fs", mean)
            log.info("max time: %fs", max(time_measures))
            log.info("min time: %fs", min(time_measures))
            log.info("standard deviation: %fs\n\n", standard_deviation)

    finally:
        if RESULT is not None:
            RESULT.close()
            RESULT.unlink()
