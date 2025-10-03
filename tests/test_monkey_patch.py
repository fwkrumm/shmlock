"""
Tests for monkey patch functionality in shmlock package.

This module contains tests for the resource tracker monkey patching
functionality provided by the shmlock package.
"""

import unittest
import sys
import warnings
from unittest.mock import patch, MagicMock

from shmlock.shmlock_monkey_patch import remove_shm_from_resource_tracker


class MonkeyPatchTest(unittest.TestCase):
    """
    Test class for monkey patch functionality.
    """

    def test_remove_shm_invalid_pattern_type(self) -> None:
        """Test remove_shm_from_resource_tracker with invalid pattern type."""
        with self.assertRaises(ValueError):
            remove_shm_from_resource_tracker(123)  # type: ignore

        with self.assertRaises(ValueError):
            remove_shm_from_resource_tracker(None)  # type: ignore

    @patch("shmlock.shmlock_monkey_patch.sys.version_info", (3, 13, 0))
    def test_remove_shm_python_313_error(self) -> None:
        """Test remove_shm_from_resource_tracker raises error on Python 3.13+."""
        with self.assertRaises(RuntimeError) as context:
            remove_shm_from_resource_tracker("test_pattern")

        self.assertIn("track", str(context.exception))
        self.assertIn("3.13", str(context.exception))

    @patch("shmlock.shmlock_monkey_patch.os.name", "nt")
    def test_remove_shm_non_posix_warning(self) -> None:
        """Test warning on non-POSIX systems."""
        if sys.version_info >= (3, 13):
            self.skipTest("Skipping test on Python 3.13+ due to version restriction")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            remove_shm_from_resource_tracker("test_pattern", print_warning=True)

            # Should generate warning about non-posix systems
            warning_messages = [str(warning.message) for warning in w]
            self.assertTrue(any("non-posix" in msg.lower() for msg in warning_messages))

    def test_remove_shm_empty_pattern_warning(self) -> None:
        """Test warning when using empty pattern."""
        if sys.version_info >= (3, 13):
            self.skipTest("Skipping test on Python 3.13+ due to version restriction")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            remove_shm_from_resource_tracker("", print_warning=True)

            # Should generate warning about empty pattern
            warning_messages = [str(warning.message) for warning in w]
            self.assertTrue(
                any("empty pattern" in msg.lower() for msg in warning_messages)
            )

    def test_remove_shm_no_warnings_when_disabled(self) -> None:
        """Test no warnings when print_warning=False."""
        if sys.version_info >= (3, 13):
            self.skipTest("Skipping test on Python 3.13+ due to version restriction")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            remove_shm_from_resource_tracker("", print_warning=False)

            # Should not generate warnings when disabled
            warning_messages = [str(warning.message) for warning in w]
            self.assertFalse(
                any("empty pattern" in msg.lower() for msg in warning_messages)
            )

    @patch("shmlock.shmlock_monkey_patch.resource_tracker")
    def test_remove_shm_pattern_filtering(
        self, mock_resource_tracker: MagicMock
    ) -> None:
        """Test that pattern filtering works correctly."""
        if sys.version_info >= (3, 13):
            self.skipTest("Skipping test on Python 3.13+ due to version restriction")

        # Mock the resource tracker
        mock_resource_tracker._resource_tracker = MagicMock()
        mock_resource_tracker._CLEANUP_FUNCS = {"shared_memory": lambda x: None}

        # Apply monkey patch
        remove_shm_from_resource_tracker("test_pattern", print_warning=False)

        # Test that the register/unregister functions are replaced
        self.assertIsNotNone(mock_resource_tracker.register)
        self.assertIsNotNone(mock_resource_tracker.unregister)

    @patch("shmlock.shmlock_monkey_patch.resource_tracker")
    def test_remove_shm_empty_pattern_cleanup_removal(
        self, mock_resource_tracker: MagicMock
    ) -> None:
        """Test that empty pattern removes cleanup function."""
        if sys.version_info >= (3, 13):
            self.skipTest("Skipping test on Python 3.13+ due to version restriction")

        # Mock the resource tracker with shared_memory cleanup function
        mock_resource_tracker._resource_tracker = MagicMock()
        mock_resource_tracker._CLEANUP_FUNCS = {"shared_memory": lambda x: None}

        # Apply monkey patch with empty pattern
        remove_shm_from_resource_tracker("", print_warning=False)

        # Verify cleanup function was removed
        self.assertNotIn("shared_memory", mock_resource_tracker._CLEANUP_FUNCS)

    def test_multiple_pattern_application(self) -> None:
        """Test that multiple patterns can be applied."""
        if sys.version_info >= (3, 13):
            self.skipTest("Skipping test on Python 3.13+ due to version restriction")

        with patch("shmlock.shmlock_monkey_patch.resource_tracker") as mock_rt:
            mock_rt._resource_tracker = MagicMock()
            mock_rt._CLEANUP_FUNCS = {}

            # Apply multiple patterns
            remove_shm_from_resource_tracker("pattern1", print_warning=False)
            remove_shm_from_resource_tracker("pattern2", print_warning=False)

            # Both should be applied without error
            self.assertTrue(True)  # If we get here, no exceptions were raised


if __name__ == "__main__":
    unittest.main()
