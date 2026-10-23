"""Versioned offline SHA-1 corpus; credentials fail closed when unavailable."""

import hashlib
from pathlib import Path


class CorpusUnavailable(RuntimeError):
    pass


class CompromisedPasswordCorpus:
    def __init__(self, path: str | None, expected_sha256: str | None) -> None:
        self.path = path
        self.expected_sha256 = expected_sha256
        self._entries: set[str] | None = None

    def _load(self) -> set[str]:
        if self._entries is not None:
            return self._entries
        if not self.path or not self.expected_sha256:
            raise CorpusUnavailable("An approved compromised-password corpus is unavailable")
        try:
            content = Path(self.path).read_bytes()
        except OSError as exc:
            raise CorpusUnavailable(
                "An approved compromised-password corpus is unavailable"
            ) from exc
        if hashlib.sha256(content).hexdigest() != self.expected_sha256.lower():
            raise CorpusUnavailable("Compromised-password corpus integrity check failed")
        lines = content.decode("ascii").splitlines()
        if not lines or any(
            len(line) != 40 or not all(c in "0123456789ABCDEF" for c in line) for line in lines
        ):
            raise CorpusUnavailable("Compromised-password corpus format is invalid")
        self._entries = set(lines)
        return self._entries

    def require_acceptable(self, password: str) -> None:
        digest = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
        if digest in self._load():
            raise ValueError("Choose a different password")
