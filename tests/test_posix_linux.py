"""
tests of some special cases which occurred on linux
"""
import sys
import time
import os
import unittest
from multiprocessing import shared_memory
import shmlock
import shmlock.shmlock_exceptions
import shmlock.shmlock_main

class LinuxPosixTests(unittest.TestCase):
    """
    test of basics of shmlock package

    Parameters
    ----------
    unittest : _type_
        _description_
    """

    def __init__(self, *args, **kwargs):
        """
        test init method
        """
        self._shm_location = os.path.abspath("/dev/shm")
        self._shm_name = None
        super().__init__(*args, **kwargs)

    def setUp(self):
        """
        set up the test case
        """
        if sys.platform.startswith("linux"):
            # there is one test to be executed outside linux so we need this special check
            self.assertTrue(os.path.exists(self._shm_location), "shm location does not exist")
            self._shm_name = str(time.time())

            l = shmlock.ShmLock(self._shm_name)
            with l:
                # file should be generated at desired location
                self.assertTrue(os.path.isfile(os.path.join(self._shm_location,
                                                            self._shm_name)))

    @unittest.skipUnless(sys.platform.startswith("linux"), "test only for linux")
    def test_empty_shared_memory_file(self):
        """
        test empty shm lock file
        """

        l = shmlock.ShmLock(self._shm_name)

        # create empty file to fake flawed shared memory file to which shared memory cannot attach
        with open(os.path.join(self._shm_location,
                               self._shm_name), "w+", encoding="utf-8") as _:
            pass

        with self.assertRaises(shmlock.shmlock_exceptions.ShmLockValueError):
            # query for error if empty file exists should raise ShmLockValueError
            l.query_for_error_after_interrupt()

    @unittest.skipUnless(sys.platform.startswith("linux"), "test only for linux")
    def test_empty_uuid_in_created_file(self):
        l = shmlock.ShmLock(self._shm_name)

        # fake creation of block but lock did not write its uuid to the file. this happens
        # if the process is interrupted right after creation of shared memory file
        shm = None
        try:
            shm = shared_memory.SharedMemory(name=self._shm_name,
                                            create=True,
                                            size=shmlock.shmlock_main.LOCK_SHM_SIZE)

            with self.assertRaises(shmlock.shmlock_exceptions.ShmLockDanglingSharedMemoryError):
                # query for error if empty file exists should raise
                # ShmLockDanglingSharedMemoryError
                l.query_for_error_after_interrupt()

        finally:
            if shm is not None:
                shm.close()
                shm.unlink()


    @unittest.skipUnless(sys.platform.startswith("linux"), "test only for linux")
    def test_error_function_if_lock_acquired(self):
        l = shmlock.ShmLock(self._shm_name)

        with l:
            with self.assertRaises(shmlock.shmlock_exceptions.ShmLockRuntimeError):
                # query for error only allowed for unlocked locks because
                # acquired locks are seemingly working fine
                l.query_for_error_after_interrupt()

    def test_error_function_if_all_is_fine(self):
        l = shmlock.ShmLock(self._shm_name)
        self.assertIsNone(l.query_for_error_after_interrupt())

if __name__ == "__main__":
    unittest.main(verbosity=2)
