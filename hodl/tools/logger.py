import os
import sys
import logging
import json_log_formatter


class LoggerWrapper:
    def __init__(self, logger, extra):
        self.logger = logger
        self.extra = extra

    def process(self, msg, kwargs, level='INFO'):
        kwargs["extra"] = self.extra | {'level': level}
        return msg, kwargs

    def debug(self, msg, *args, **kwargs):
        msg, kwargs = self.process(msg, kwargs, 'DEBUG')
        self.logger.debug(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        msg, kwargs = self.process(msg, kwargs, 'INFO')
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        msg, kwargs = self.process(msg, kwargs, 'WARNING')
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        msg, kwargs = self.process(msg, kwargs, 'ERROR')
        self.logger.error(msg, *args, **kwargs)

    def exception(self, msg, *args, **kwargs):
        e, kwargs = self.process(msg, kwargs, 'ERROR')
        self.logger.exception(msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        msg, kwargs = self.process(msg, kwargs, 'CRITICAL')
        self.logger.critical(msg, *args, **kwargs)


class Logger:
    def __init__(
            self,
            logger_name,
            log_level=None,
            log_root=None,
            file_max_size=512 * 1024,
            file_max_count=9,
            write_text=True,
            write_json=True,
            write_stdout=True,
    ):
        self.logger_name = logger_name
        self.log_level = log_level or 'INFO'
        self.log_root = log_root
        self.file_max_size = file_max_size
        self.file_max_count = file_max_count
        self.write_text = write_text
        self.write_json = write_json
        self.write_stdout = write_stdout

    def set_up(self):
        logger = logging.getLogger()
        while logger.hasHandlers():
            logger.removeHandler(logger.handlers[0])
        logger.propagate = False

        log_name = self.logger_name
        fmt = '%(asctime)s.%(msecs)03d|%(levelname)s%(state)s:%(message)s'
        text_formatter = logging.Formatter(fmt, datefmt='%m-%d %H:%M:%S')
        if self.write_stdout:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(text_formatter)
            logger = logging.getLogger(log_name)
            logger.setLevel(self.log_level)
            logger.addHandler(handler)
            logger.propagate = False

        if self.log_root:
            log_root = os.path.expanduser(self.log_root)
            os.makedirs(log_root, exist_ok=True)

        if self.log_root and self.write_text:
            filename = "{}.log".format(log_name)
            filename_path = os.path.join(self.log_root, filename)
            filename_path = os.path.expanduser(filename_path)
            handler = self._rotating_handler(
                filename=filename_path,
                mode='a',
                max_bytes=self.file_max_size,
                backup_count=self.file_max_count,
                encoding='utf8',
                use_gzip=False,
            )
            handler.setFormatter(text_formatter)
            logger = logging.getLogger(log_name)
            logger.setLevel(self.log_level)
            logger.addHandler(handler)

        log_name = self.logger_name
        filename = "{}.json".format(log_name)
        if self.log_root and self.write_json:
            filename_path = os.path.join(self.log_root, filename)
            filename_path = os.path.expanduser(filename_path)
            handler = self._rotating_handler(
                filename=filename_path,
                mode='a',
                max_bytes=self.file_max_size,
                backup_count=self.file_max_count,
                encoding='utf8',
                use_gzip=False,
            )
            json_log_formatter.BUILTIN_ATTRS.add('state')
            formatter = json_log_formatter.JSONFormatter(datefmt='%Y-%m-%d %H:%M:%S')
            handler.setFormatter(formatter)
            logger = logging.getLogger(log_name)
            logger.setLevel(self.log_level)
            logger.addHandler(handler)

    def logger(self, state=None, **kwargs):
        logger = logging.getLogger(self.logger_name)
        extra = dict(
            state=state or '',
            **(kwargs | (state.log_dict() if state else {})),
        )
        adapter = LoggerWrapper(logger, extra=extra)
        return adapter

    @classmethod
    def _rotating_handler(
            cls,
            filename,
            mode='a',
            max_bytes=128 * 1024,
            backup_count=4,
            encoding='utf8',
            use_gzip=False,
    ):
        if os.name == 'nt':
            handler = logging.FileHandler(filename=filename, mode=mode, encoding=encoding)
        else:
            from concurrent_log_handler import ConcurrentRotatingFileHandler
            handler = ConcurrentRotatingFileHandler(
                filename=filename,
                mode=mode,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding=encoding,
                use_gzip=use_gzip,
            )
        return handler


__all__ = ['LoggerWrapper', 'Logger', ]
