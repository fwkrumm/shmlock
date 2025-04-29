"""
tests of basics (lock/release) of shmlock package
"""
import time
import unittest
from multiprocessing import shared_memory
import shmlock
import shmlock.shmlock_exceptions

class BasicsTest(unittest.TestCase):
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
        super().__init__(*args, **kwargs)

    def test_lock_release(self):
        """
        test the basics
        """
        shm_name = str(time.time())
        obj = shmlock.ShmLock(shm_name)

        self.assertTrue(obj.acquire())
        with self.assertRaises(shmlock.shmlock_exceptions.ShmLockRuntimeError):
            obj.acquire() # already acquired for this object

        obj2 = shmlock.ShmLock(shm_name)
        self.assertFalse(obj2.acquire(timeout=1)) # acquired by other lock

        self.assertTrue(obj.release()) # relase should be successful
        self.assertTrue(obj2.acquire()) # not should be acquireable

        self.assertTrue(obj2.release()) # check successful release

        # double release should return False
        self.assertFalse(obj.release())
        self.assertFalse(obj2.release())


        shm = None
        with self.assertRaises(FileNotFoundError, msg = f"shm with name {shm_name} could not be "\
                               "acquired, this means that it has not been properly "\
                               "released by the locks!"):
            # attach should fail because there is no shm to attach to
            shm = shared_memory.SharedMemory(name=shm_name)

        if shm is not None:
            # juse in case, make sure that there are never leaking resources
            shm.close()
            shm.unlink()



if __name__ == "__main__":
    unittest.main(verbosity=2)
