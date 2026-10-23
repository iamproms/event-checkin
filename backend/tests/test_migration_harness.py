import subprocess
import sys
from pathlib import Path

import pytest
from test_tenant_postgres import BACKEND_DIR, _migrate


def test_migration_uses_current_python(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[list[str], Path, str, str]] = []

    def capture(command: list[str], *, cwd: Path, env: dict[str, str], check: bool) -> None:
        assert check is True
        calls.append((command, cwd, env["APP_ENV"], env["DATABASE_URL"]))

    monkeypatch.setattr(subprocess, "run", capture)
    _migrate("postgresql+psycopg://test:test@localhost/test", "head")
    assert calls == [
        (
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            BACKEND_DIR,
            "test",
            "postgresql+psycopg://test:test@localhost/test",
        )
    ]
