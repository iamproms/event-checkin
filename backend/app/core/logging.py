import json
import logging
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for name in (
            "request_id",
            "method",
            "route",
            "status_code",
            "duration_ms",
            "outcome",
            "reason_code",
        ):
            value = getattr(record, name, None)
            if value is not None:
                payload[name] = value
        return json.dumps(payload, separators=(",", ":"))


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=level, handlers=[handler], force=True)
