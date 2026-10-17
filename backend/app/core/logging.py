import contextvars
import json
import logging
import re
import sys

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)

# Belt and braces: even if a message or exception text carries a secret, it is masked before it's written.
REDACT = [
    (re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key|authorization|cookie)(\W{1,3})([^\s,;'\"&]+)"), r"\1\2[redacted]"),
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]+"), "[redacted]"),
    (re.compile(r"(postgres(?:ql)?(?:\+\w+)?://[^:/\s]+:)[^@\s]+@"), r"\1[redacted]@"),
]


def redact(text: str) -> str:
    for pattern, replacement in REDACT:
        text = pattern.sub(replacement, text)
    return text


class JsonFormatter(logging.Formatter):
    """One JSON object per line. Never log tokens, personal data or raw record text."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "msg": redact(record.getMessage()),
        }
        if record.exc_info:
            payload["exc"] = redact(self.formatException(record.exc_info))
        if (rid := request_id_var.get()) is not None:
            payload["request_id"] = rid
        for key in ("job_id",):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
