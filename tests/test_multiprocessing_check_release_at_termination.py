"""
rather an integration tests -> run multiple processes and check if the shared memory lock works

an alternative for patching resource tracker for tests might be

https://github.com/vllm-project/vllm/pull/5512/commits/af0e16c70572c222e747a64f637b7c795f884334

related to
https://github.com/vllm-project/vllm/issues/5468
https://github.com/vllm-project/vllm/pull/5512

"""
import multiprocessing
from multiprocessing import shared_memory
import multiprocessing.synchronize
import unittest
import os
import sys
import time
import struct
import threading
import logging
import shmlock



def worker(lock_name: str):
    """
    acquire lock indefinitely
    """
    s = shmlock.ShmLock(lock_name)

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
        """

        shm_name = str(time.time())
        l = shmlock.ShmLock(shm_name)


        p = multiprocessing.Process(target=worker, args=(shm_name,))

        p.start()
        time.sleep(1)

        self.assertTrue(p.is_alive(), "Process is not alive after start")
        self.assertFalse(l.acquire(timeout=False), "lock should be acquired by the process")

        p.terminate()
        p.join()

        self.assertFalse(p.is_alive(), "Process is still alive after termination")
        self.assertTrue(l.acquire(timeout=1), "Lock not released after process termination")

if __name__ == "__main__":
    unittest.main(verbosity=2)
