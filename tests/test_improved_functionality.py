"""
Tests for improved functionality and edge cases in shmlock package.

This module contains tests for recently added functionality, edge cases,
and improved error handling in the shmlock package.
"""
import unittest
import time
import logging
import tempfile
import os
from typing import List
from unittest.mock import patch, MagicMock

import shmlock
import shmlock.shmlock_exceptions as exceptions
from shmlock.shmlock_uuid import ShmUuid
from shmlock.shmlock_config import ShmLockConfig, ExitEventMock
from shmlock.shmlock_base_logger import ShmModuleBaseLogger, create_logger


class ImprovedFunctionalityTest(unittest.TestCase):
    """
    Test class for improved functionality and edge cases.
    """

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.test_name = f"test_lock_{time.time()}"

    def test_shmlock_exception_hierarchy(self) -> None:
        """Test that exception hierarchy is correctly implemented."""
        # Test base exception
        base_exc = exceptions.ShmlockError("Base error message")
        self.assertIsInstance(base_exc, Exception)
        self.assertEqual(str(base_exc), "Base error message")

        # Test runtime error inheritance
        runtime_exc = exceptions.ShmLockRuntimeError("Runtime error")
        self.assertIsInstance(runtime_exc, exceptions.ShmlockError)
        self.assertIsInstance(runtime_exc, RuntimeError)

        # Test value error inheritance
        value_exc = exceptions.ShmLockValueError("Value error")
        self.assertIsInstance(value_exc, exceptions.ShmlockError)
        self.assertIsInstance(value_exc, ValueError)

    def test_shmlock_config_validation(self) -> None:
        """Test ShmLockConfig validation in __post_init__."""
        uuid_obj = ShmUuid()
        exit_event = ExitEventMock()

        # Test valid config
        config = ShmLockConfig(
            name="test_lock",
            poll_interval=0.1,
            exit_event=exit_event,
            track=None,
            timeout=1.0,
            uuid=uuid_obj,
            pid=12345
        )
        self.assertEqual(config.name, "test_lock")

        # Test invalid name (empty)
        with self.assertRaises(ValueError):
            ShmLockConfig(
                name="",
                poll_interval=0.1,
                exit_event=exit_event,
                track=None,
                timeout=1.0,
                uuid=uuid_obj,
                pid=12345
            )

        # Test invalid poll_interval (negative)
        with self.assertRaises(ValueError):
            ShmLockConfig(
                name="test_lock",
                poll_interval=-0.1,
                exit_event=exit_event,
                track=None,
                timeout=1.0,
                uuid=uuid_obj,
                pid=12345
            )

        # Test invalid timeout (negative)
        with self.assertRaises(ValueError):
            ShmLockConfig(
                name="test_lock",
                poll_interval=0.1,
                exit_event=exit_event,
                track=None,
                timeout=-1.0,
                uuid=uuid_obj,
                pid=12345
            )

        # Test invalid pid (zero)
        with self.assertRaises(ValueError):
            ShmLockConfig(
                name="test_lock",
                poll_interval=0.1,
                exit_event=exit_event,
                track=None,
                timeout=1.0,
                uuid=uuid_obj,
                pid=0
            )

    def test_shmUuid_equality_and_hash(self) -> None:
        """Test ShmUuid equality and hash functionality."""
        uuid1 = ShmUuid()
        uuid2 = ShmUuid()
        
        # Different UUIDs should not be equal
        self.assertNotEqual(uuid1, uuid2)
        self.assertNotEqual(hash(uuid1), hash(uuid2))
        
        # Same UUID should be equal to itself
        self.assertEqual(uuid1, uuid1)
        self.assertEqual(hash(uuid1), hash(uuid1))
        
        # Test equality with non-ShmUuid objects
        self.assertNotEqual(uuid1, "not_a_uuid")
        self.assertNotEqual(uuid1, 42)

    def test_shmUuid_conversion_edge_cases(self) -> None:
        """Test ShmUuid conversion methods with edge cases."""
        # Test invalid byte representation
        with self.assertRaises(ValueError):
            ShmUuid.byte_to_string(b"invalid_bytes")
        
        with self.assertRaises(ValueError):
            ShmUuid.byte_to_string(b"")
        
        # Test invalid string representation
        with self.assertRaises(ValueError):
            ShmUuid.string_to_bytes("not_a_uuid")
        
        with self.assertRaises(ValueError):
            ShmUuid.string_to_bytes("")

    def test_exit_event_mock_functionality(self) -> None:
        """Test ExitEventMock behavior."""
        mock_event = ExitEventMock()
        
        # Initial state should be False
        self.assertFalse(mock_event.is_set())
        
        # Test set functionality
        mock_event.set()
        self.assertTrue(mock_event.is_set())
        
        # Test clear functionality
        mock_event.clear()
        self.assertFalse(mock_event.is_set())
        
        # Test wait functionality
        start_time = time.time()
        mock_event.wait(0.1)
        elapsed = time.time() - start_time
        self.assertGreaterEqual(elapsed, 0.09)  # Allow for timing variance
        
        # Test wait when set (should not sleep)
        mock_event.set()
        start_time = time.time()
        mock_event.wait(0.1)
        elapsed = time.time() - start_time
        self.assertLess(elapsed, 0.05)  # Should return immediately

    def test_base_logger_invalid_logger(self) -> None:
        """Test ShmModuleBaseLogger with invalid logger types."""
        # Test with invalid logger type
        with self.assertRaises(exceptions.ShmLockValueError):
            ShmModuleBaseLogger(logger="not_a_logger")
        
        with self.assertRaises(exceptions.ShmLockValueError):
            ShmModuleBaseLogger(logger=42)

    def test_base_logger_without_logger(self) -> None:
        """Test ShmModuleBaseLogger without actual logger."""
        base_logger = ShmModuleBaseLogger()
        
        # All logging methods should work without error when no logger is set
        base_logger.info("test info")
        base_logger.debug("test debug")
        base_logger.warning("test warning")
        base_logger.error("test error")
        base_logger.exception("test exception")
        base_logger.critical("test critical")

    def test_create_logger_validation(self) -> None:
        """Test create_logger function parameter validation."""
        # Test invalid logging levels
        with self.assertRaises(ValueError):
            create_logger(level=-1)
        
        with self.assertRaises(ValueError):
            create_logger(level_file=-1)

    def test_create_logger_file_handling(self) -> None:
        """Test create_logger file handling edge cases."""
        # Test with invalid file path (should warn but not crash)
        with tempfile.TemporaryDirectory() as temp_dir:
            invalid_path = os.path.join(temp_dir, "nonexistent", "file.log")
            
            # This should create a logger but log a warning about file creation failure
            logger = create_logger(file_path=invalid_path)
            self.assertIsInstance(logger, logging.Logger)

    @patch('shmlock.shmlock_base_logger.coloredlogs')
    def test_create_logger_coloredlogs_error(self, mock_coloredlogs: MagicMock) -> None:
        """Test create_logger when coloredlogs installation fails."""
        # Mock coloredlogs.install to raise an exception
        mock_coloredlogs.install.side_effect = Exception("Mock installation error")
        
        # Should still create logger successfully
        logger = create_logger(use_colored_logs=True)
        self.assertIsInstance(logger, logging.Logger)

    def test_lock_name_validation(self) -> None:
        """Test lock name validation."""
        # Test empty string
        with self.assertRaises(exceptions.ShmLockValueError):
            shmlock.ShmLock("")
        
        # Test non-string types
        with self.assertRaises(exceptions.ShmLockValueError):
            shmlock.ShmLock(None)
        
        with self.assertRaises(exceptions.ShmLockValueError):
            shmlock.ShmLock(123)

    def test_poll_interval_validation(self) -> None:
        """Test poll interval validation."""
        # Test negative values
        with self.assertRaises(exceptions.ShmLockValueError):
            shmlock.ShmLock(self.test_name, poll_interval=-0.1)
        
        # Test zero
        with self.assertRaises(exceptions.ShmLockValueError):
            shmlock.ShmLock(self.test_name, poll_interval=0)
        
        # Test invalid types
        with self.assertRaises(exceptions.ShmLockValueError):
            shmlock.ShmLock(self.test_name, poll_interval="invalid")

    def test_lock_representation(self) -> None:
        """Test lock string representation methods."""
        lock = shmlock.ShmLock(self.test_name)
        
        # Test __repr__
        repr_str = repr(lock)
        self.assertIn(self.test_name, repr_str)
        self.assertIn("ShmLock", repr_str)
        
        # Test that UUID is included
        self.assertIn("uuid=", repr_str)

    def test_timeout_parameter_types(self) -> None:
        """Test different timeout parameter types."""
        lock = shmlock.ShmLock(self.test_name)
        
        try:
            # Test None timeout (should work)
            result = lock.acquire(timeout=None)
            if result:
                lock.release()
            
            # Test False timeout (should work - single attempt)
            result = lock.acquire(timeout=False)
            if result:
                lock.release()
            
            # Test True timeout (should work - 1 second)
            result = lock.acquire(timeout=True)
            if result:
                lock.release()
            
            # Test float timeout
            result = lock.acquire(timeout=0.1)
            if result:
                lock.release()
                
        except Exception as e:
            self.fail(f"Timeout parameter handling failed: {e}")

    def tearDown(self) -> None:
        """Clean up after tests."""
        # Try to clean up any remaining shared memory
        try:
            from multiprocessing import shared_memory
            shm = shared_memory.SharedMemory(name=self.test_name)
            shm.close()
            shm.unlink()
        except FileNotFoundError:
            pass  # Already cleaned up
        except Exception:
            pass  # Ignore other cleanup errors


if __name__ == '__main__':
    unittest.main()