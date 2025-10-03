"""
Base logger and helper functions for shmlock module.

This module provides a wrapper around the logging functionality and helper functions
to create configured loggers with optional color and file logging support.
"""
import logging
from typing import Optional

try:
    import coloredlogs
    HAS_COLOREDLOGS = True
except ModuleNotFoundError:
    coloredlogs = None
    HAS_COLOREDLOGS = False

from shmlock.shmlock_exceptions import ShmLockValueError


def create_logger(
    name: str = "ShmLockLogger",
    level: int = logging.INFO,
    file_path: Optional[str] = None,
    level_file: int = logging.DEBUG,
    use_colored_logs: bool = True,
    fmt: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
) -> logging.Logger:
    """
    Set up a logger with color (if available and enabled) and file logging (if enabled).
    
    Note that this logger is not set anywhere in the shmlock objects itself, so in case you want
    them to use it you have to manually set it via: ShmLock(..., logger=create_logger(...))

    NOTE that this is only a helper function which is never called automatically.

    Parameters
    ----------
    name : str, optional
        Name of the logger, by default "ShmLockLogger"
    level : int, optional
        Level of the streamhandler logger, by default logging.INFO
    file_path : str, optional
        Set a log file path in case desired, activates file logging, by default None
    level_file : int, optional
        Level for file logging, by default logging.DEBUG
    use_colored_logs : bool, optional
        If coloredlogs is available the module will be tried to be used, by default True
    fmt : str, optional
        Format of the logger, by default "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    Returns
    -------
    logging.Logger
        Logger object with the given name and level, if file_path is set it will
        also create a file handler with the given level_file
        
    Raises
    ------
    ValueError
        If level or level_file are invalid logging levels
    """
    # Validate logging levels
    if not isinstance(level, int) or level < 0:
        raise ValueError(f"Invalid logging level: {level}")
    if not isinstance(level_file, int) or level_file < 0:
        raise ValueError(f"Invalid file logging level: {level_file}")

    # Format for logger
    logger_format = logging.Formatter(fmt)

    # Set up logger
    logger = logging.getLogger(name)
    if file_path is not None:
        logger.setLevel(min(level_file, level))  # Use lower level to avoid missing logs
    else:
        logger.setLevel(level)

    # Prevent propagating of logs to root logger
    logger.propagate = False

    # Remove all existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Set stream handler
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        handler.setLevel(level)
        handler.setFormatter(logger_format)
        logger.addHandler(handler)

    if file_path is not None:
        # If path is set, set up file handler
        try:
            file_handler = logging.FileHandler(file_path)
            file_handler.setLevel(level_file)
            file_handler.setFormatter(logger_format)
            logger.addHandler(file_handler)
        except (OSError, PermissionError) as e:
            logger.warning(f"Could not create file handler for {file_path}: {e}")

    if use_colored_logs and HAS_COLOREDLOGS:
        # Set colored logs if available
        try:
            coloredlogs.install(logger=logger, level=level, fmt=fmt)
        except Exception as e:  # pylint: disable=broad-except
            logger.warning(f"Could not install colored logs: {e}")

    return logger


class ShmModuleBaseLogger:
    """
    Base logger wrapper for shmlock module classes.
    
    This class provides a common logging interface for all shmlock classes,
    ensuring consistent logging behavior throughout the module.
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        """
        Initialize the logger wrapper.
        
        Basically a wrapper around the logger which prints the log
        only if logger is set.

        Parameters
        ----------
        logger : logging.Logger, optional
            Logger to be used, by default None
            
        Raises
        ------
        ShmLockValueError
            If logger is not None and not a logging.Logger instance
        """
        self._logger: Optional[logging.Logger] = None

        if logger is not None and not isinstance(logger, logging.Logger):
            raise ShmLockValueError(
                f"logger must be of type logging.Logger, instead got {type(logger)}"
            )
        self._logger = logger

    def info(self, message: str, *args: object) -> None:
        """Log an info message."""
        if self._logger is not None:
            self._logger.info(message, *args)

    def debug(self, message: str, *args: object) -> None:
        """Log a debug message."""
        if self._logger is not None:
            self._logger.debug(message, *args)

    def warning(self, message: str, *args: object) -> None:
        """Log a warning message."""
        if self._logger is not None:
            self._logger.warning(message, *args)

    def error(self, message: str, *args: object) -> None:
        """Log an error message."""
        if self._logger is not None:
            self._logger.error(message, *args)

    def exception(self, message: str, *args: object) -> None:
        """Log an exception message with traceback."""
        if self._logger is not None:
            self._logger.exception(message, *args)

    def critical(self, message: str, *args: object) -> None:
        """Log a critical message."""
        if self._logger is not None:
            self._logger.critical(message, *args)
