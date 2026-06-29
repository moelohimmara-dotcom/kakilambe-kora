import logging
import json
import sys
from datetime import datetime


class StructuredLogger:
    """Structured JSON logger for KORA."""

    def __init__(self, name: str = "kora"):
        self._logger = logging.getLogger(name)
        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.DEBUG)

    def _emit(self, level: str, event: str, **kwargs):
        record = {
            "ts": datetime.utcnow().isoformat(),
            "level": level,
            "event": event,
            **kwargs,
        }
        msg = json.dumps(record, ensure_ascii=False, default=str)
        getattr(self._logger, level)(msg)

    def info(self, event: str, **kwargs):
        self._emit("info", event, **kwargs)

    def warning(self, event: str, **kwargs):
        self._emit("warning", event, **kwargs)

    def error(self, event: str, **kwargs):
        self._emit("error", event, **kwargs)

    def debug(self, event: str, **kwargs):
        self._emit("debug", event, **kwargs)


logger = StructuredLogger()
