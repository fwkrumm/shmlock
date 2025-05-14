"""
rather an integration tests -> run multiple processes and check if the shared memory lock works

an alternative for patching resource tracker for tests might be

https://github.com/vllm-project/vllm/pull/5512/commits/af0e16c70572c222e747a64f637b7c795f884334

related to
https://github.com/vllm-project/vllm/issues/5468
https://github.com/vllm-project/vllm/pull/5512

"""
import sys
import os
import multiprocessing
import unittest
import time
import signal
import shmlock


LOCK_NAME = "test_lock_name"


if os.name == "posix":
    if sys.version_info >= (3, 12, 0):
        # for 3.12.5 there is a deprecation warning concerning fork method and threads.
        # so we set it to spawn here
        multiprocessing.set_start_method("spawn", force=True)

    # otherwise it spams KeyErrors since resource tracker also tracks shm of other processes
    # and complains that it has not been unlinked because it was unlinked by another process
    if sys.version_info < (3, 13):
        # NOTE that this is not necessary for python 3.13 and above since there is the track
        # parameter to deactivate tracking
        shmlock.remove_shm_from_resource_tracker(LOCK_NAME)

def acquire_lock_worker():
    """
    acquire lock indefinitely until terminated
    """
    s = shmlock.ShmLock(LOCK_NAME, track=False if sys.version_info >= (3, 13) else None)

    def cleanup(signum, frame): # pylint:disable=(unused-argument)
        s.release(force=True)
        os._exit(0) # pylint:disable=(protected-access)

    signal.signal(signal.SIGTERM, cleanup)
    with s:
        while True:
            pass



class TestReleaseAtTermination(unittest.TestCase):
    """
    release at termination test of shmlock package

    Parameters
    ----------
    unittest : _type_
        _description_
    """

    def test_termination_release(self):
        """
        check that termination releases shared memory

        NOTE that the termination will on posix probably leave semaphore objects behind
        """

        # create a lock and a process
        l = shmlock.ShmLock(LOCK_NAME, track=False if sys.version_info >= (3, 13) else None)
        p = multiprocessing.Process(target=acquire_lock_worker)

        p.start()
        time.sleep(1)

        # check that process as started and lock has been acquired by the process
        self.assertTrue(p.is_alive(), "Process is not alive after start")
        self.assertFalse(l.acquire(timeout=False), "lock should be acquired by the process")

        # termiante the process
        p.terminate()
        p.join()

        # check that signal works to release the lock
        self.assertFalse(p.is_alive(), "Process is still alive after termination")
        self.assertTrue(l.acquire(timeout=1), "Lock not released after process termination")


if __name__ == "__main__":
    unittest.main(verbosity=2)
