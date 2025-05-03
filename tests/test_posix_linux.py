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
        super().__init__(*args, **kwargs)

    def setUpModule(self):
        """
        set up the test case
        """
        self.assertTrue(os.path.exists(self._shm_location), "shm location does not exist")
        shm_name = str(time.time())

        l = shmlock.ShmLock(shm_name)
        with l:
            self.assertTrue(os.path.isfile(os.path.join(self._shm_location,
                                                    shm_name)))

    @unittest.skipUnless(sys.platform.startswith("linux"), "test only for linux")
    def test_release_in_destructor(self):
        """
        test empty shm lock file
        """
        lock_name = str(time.time())

        l = shmlock.ShmLock(lock_name)

        # create empty file
        with open(os.path.join(self._shm_location,
                               lock_name), "w+") as f:
            pass

        with self.assertRaises(shmlock.shmlock_exceptions.ShmLockValueError):
            # try to create a lock if an empty file exsits
            with l:
                pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
