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
from shmlock.shmlock_main import remove_shm_from_resource_tracker
from shmlock.shmlock_monkey_patch import _PATTERN_LIST

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
        self._shm_name = str(time.time())

        if sys.platform.startswith("linux"):
            # there is one test to be executed outside linux so we need this special check
            self.assertTrue(os.path.exists(self._shm_location), "shm location does not exist")

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
        """
        test empty uuid in created file
        """
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

    def test_error_function_if_lock_acquired(self):
        """
        test that query for error raises an exception if lock is acquired
        """
        l = shmlock.ShmLock(self._shm_name)

        with l:
            with self.assertRaises(shmlock.shmlock_exceptions.ShmLockRuntimeError):
                # query for error only allowed for unlocked locks because
                # acquired locks are seemingly working fine
                l.query_for_error_after_interrupt()

    def test_query_function(self):
        """
        test that query for error raises an exception if lock is acquired
        """
        l1 = shmlock.ShmLock(self._shm_name)
        l2 = shmlock.ShmLock(self._shm_name)

        # acquire lock
        l1.acquire()

        # l2 should now cleanly proceed and not throw anything
        l2.query_for_error_after_interrupt()


    def test_error_function_if_all_is_fine(self):
        """
        test that query for error does not raise an exception if all is fine and returns None
        """
        l = shmlock.ShmLock(self._shm_name)
        self.assertIsNone(l.query_for_error_after_interrupt())

    def test_monkey_patch(self):
        """
        test monkey patching of the lock

        NOTE that this is rather for code coverage. To test if the monkey patching
        works, we need to test the lock in a separate process. This is not done here but in the
        examples.

        NOTE that the patch makes only sense on posix systems. But we execute it on all systems
        """

        l = shmlock.ShmLock(self._shm_name)

        if sys.version_info >= (3, 13):
            with self.assertRaises(RuntimeError):
                # in python 3.13 and above shared memory blocks contain the track parameter
                # which can also be used in the ShmLock object. Use ShmLock(..., track=False) so
                # that shared memory block will not be tracked by the resource tracker
                remove_shm_from_resource_tracker(l.name)
        else:

            remove_shm_from_resource_tracker(l.name)

            self.assertTrue(len(_PATTERN_LIST) > 0, "monkey patching did not work")
            self.assertTrue(l.name in _PATTERN_LIST)

            with self.assertRaises(ValueError):
                # pattern must be a string
                remove_shm_from_resource_tracker(1)

if __name__ == "__main__":
    unittest.main(verbosity=2)
