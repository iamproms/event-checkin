#!/usr/bin/env python3
"""Race one synthetic QR credential through five authorized gate sessions.

The config contains bearer secrets and must be mode 0600. The script prints
only HTTP status and outcome, never cookies, CSRF values or the credential.
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import stat
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from typing import Any


def load_config(path: Path) -> dict[str, Any]:
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise SystemExit(f"{path} must not be readable or writable by group/other")
    data = json.loads(path.read_text(encoding="utf-8"))
    sessions = data.get("sessions")
    if not isinstance(sessions, list) or len(sessions) != 5:
        raise SystemExit("config must contain exactly five gate sessions")
    return data


def redeem(
    barrier: Barrier,
    base_url: str,
    origin: str,
    event_id: str,
    credential: str,
    session: dict[str, str],
    context: ssl.SSLContext,
) -> tuple[int, str]:
    body = json.dumps(
        {
            "event_id": event_id,
            "gate_id": session["gate_id"],
            "credential": credential,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/v1/gate/redeem",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Origin": origin.rstrip("/"),
            "X-CSRF-Token": session["csrf"],
            "Cookie": (
                f"__Host-ecs_session={session['session_cookie']}; "
                f"__Host-ecs_csrf={session['csrf']}"
            ),
        },
    )
    barrier.wait(timeout=10)
    try:
        with urllib.request.urlopen(request, timeout=15, context=context) as response:
            payload = json.load(response)
            return response.status, str(payload.get("outcome", "missing"))
    except urllib.error.HTTPError as exc:
        return exc.code, "http_error"
    except (TimeoutError, urllib.error.URLError):
        return 0, "network_error"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(os.environ.get("SCAN_REHEARSAL_CONFIG", "/dev/null")),
    )
    args = parser.parse_args()
    if args.config == Path("/dev/null"):
        raise SystemExit("set SCAN_REHEARSAL_CONFIG or pass --config")
    config = load_config(args.config)

    context = ssl.create_default_context()
    if ca_file := config.get("ca_file"):
        context.load_verify_locations(cafile=str(ca_file))
    barrier = Barrier(5)
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [
            pool.submit(
                redeem,
                barrier,
                str(config["base_url"]),
                str(config.get("origin", config["base_url"])),
                str(config["event_id"]),
                str(config["credential"]),
                session,
                context,
            )
            for session in config["sessions"]
        ]
    results = [future.result() for future in futures]
    outcomes = [outcome for _, outcome in results]
    print(json.dumps({"results": results, "accepted": outcomes.count("accepted"), "duplicate": outcomes.count("duplicate")}))
    if outcomes.count("accepted") != 1 or outcomes.count("duplicate") != 4:
        raise SystemExit("atomic redemption assertion failed")


if __name__ == "__main__":
    main()
