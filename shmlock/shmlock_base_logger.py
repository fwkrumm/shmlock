"""
base logger, only a wrapper around the logger

Also provides a helper function to create a logger with color and file logging (if desired).

Potentially make this an own package or at least own repo since the related tests have nothing to
do with the shmlock anymore.
"""
import logging
try:
    import coloredlogs
except ModuleNotFoundError:
    coloredlogs = None
from shmlock.shmlock_exceptions import ShmLockValueError


def create_logger(name: str = "ShmLockLogger",
                  level: int = logging.INFO,
                  file_path: str = None,
                  level_file: int = logging.DEBUG,
                  use_colored_logs: bool = True,
                  fmt: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s") -> \
                    logging.Logger:
    """
    set up a logger with color (if available and enabled) and file logging (if enabled).
    Note that this logger is not set anywhere in the shmlock objects itself, so in case you want
    them to use it you have to manually set it via
    ShmLock(..., logger=create_logger(...))

    NOTE that this is only a helper function which is never called automatically.

    Parameters
    ----------
    name : str, optional
        name of the logger, by default "ShmLockLogger"
    level : int, optional
        level of the streamhandler logger, by default logging.INFO
    file_path : str, optional
        set a log file path in case desired, activated file logging, by default None
    level_file : int, optional
        level for file logging, by default logging.DEBUG
    use_colored_logs : bool, optional
        if coloredlogs is available the module will be tried to be used, by default True
    fmt : str, optional
        format of the logger, by default "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    Returns
    -------
    logging.Logger
        logger object with the given name and level, if file_path is set it will
        also create a file handler with the given level_file.
    """

    # format for logger
    logger_format = logging.Formatter(fmt)

    # set up logger
    logger = logging.getLogger(name)
    if file_path is not None:
        logger.setLevel(min(level_file, level)) # use lower level of the two to avoid missing logs
    else:
        logger.setLevel(level)

    # prevent propagating of logs to root logger
    logger.propagate = False

    for handler in logger.handlers[:]:
        # remove all handlers to avoid duplicates
        logger.removeHandler(handler)

    # set stream handler
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        handler.setLevel(level)
        handler.setFormatter(logger_format)
        logger.addHandler(handler)

    if file_path is not None:
        # if path is set, set up file handler
        file_handler = logging.FileHandler(file_path)
        file_handler.setLevel(level_file)
        file_handler.setFormatter(logger_format)
        logger.addHandler(file_handler)

    if use_colored_logs and coloredlogs is not None:
        # set colored logs if available
        coloredlogs.install(logger=logger, level=level, fmt=fmt)

    return logger

class ShmModuleBaseLogger:

    """
    log if set, basic api
    """

    def __init__(self,
                 logger: logging.Logger = None):
        """
        default init for logger which other classes inherit.
        basically a wrapper around the logger which prints the log
        only if logger is set

        Parameters
        ----------
        logger : logging.Logger, optional
            logger to be used, by default None
        """
        self._logger = None

        if logger is not None and not isinstance(logger, logging.Logger):
            raise ShmLockValueError("logger must be of type logging.Logger, "\
                f"instead got {type(logger)}")
        self._logger = logger

    def info(self, message: str, *args):
        """
        log message info
        """
        if self._logger is not None:
            self._logger.info(message, *args)

    def debug(self, message: str, *args):
        """
        log message debug
        """
        if self._logger is not None:
            self._logger.debug(message, *args)

    def warning(self, message: str, *args):
        """
        log message warning
        """
        if self._logger is not None:
            self._logger.warning(message, *args)

    def error(self, message: str, *args):
        """
        log message error
        """
        if self._logger is not None:
            self._logger.error(message, *args)

    def exception(self, message: str, *args):
        """
        log message exception
        """
        if self._logger is not None:
            self._logger.exception(message, *args)

    def critical(self, message: str, *args):
        """
        log message critical
        """
        if self._logger is not None:
            self._logger.critical(message, *args)
