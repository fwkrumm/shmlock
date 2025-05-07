"""
tests of some special cases which occurred on linux
"""
import sys
import time
import os
import unittest
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
        self._shm_name = None
        super().__init__(*args, **kwargs)

    def setUp(self):
        """
        set up the test case
        """
        self.assertTrue(os.path.exists(self._shm_location), "shm location does not exist")
        self._shm_name = str(time.time())

        l = shmlock.ShmLock(self._shm_name)
        with l:
            # file should be generated at desired location
            self.assertTrue(os.path.isfile(os.path.join(self._shm_location,
                                                        self._shm_name)))

    @unittest.skipUnless(sys.platform.startswith("linux"), "test only for linux")
    def test_release_in_destructor(self):
        """
        test empty shm lock file
        """
        pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
