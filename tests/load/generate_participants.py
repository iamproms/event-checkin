#!/usr/bin/env python3
"""Generate deterministic synthetic attendee CSV data for import rehearsals.

The output uses example.test email addresses and generated names. It must never
be sent through a real transactional provider.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


FIRST_NAMES = (
    "Amina",
    "Chidi",
    "Dayo",
    "Efe",
    "Fatima",
    "Ifeoma",
    "Kunle",
    "Mariam",
    "Nneka",
    "Tunde",
)
LAST_NAMES = (
    "Adeyemi",
    "Balogun",
    "Eze",
    "Ibrahim",
    "Nwosu",
    "Okafor",
    "Olawale",
    "Sani",
    "Udo",
    "Yusuf",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=5000)
    parser.add_argument("--output", type=Path, default=Path("/tmp/event-attendees-5000.csv"))
    parser.add_argument(
        "--inject-errors-every",
        type=int,
        default=0,
        help="Make every Nth row invalid and the following row a duplicate (0 disables).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 1 <= args.rows <= 50_000:
        raise SystemExit("--rows must be between 1 and 50000")
    if args.inject_errors_every < 0:
        raise SystemExit("--inject-errors-every cannot be negative")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("full_name", "email", "phone", "organization", "source_reference"),
        )
        writer.writeheader()
        previous_valid_email = ""
        for index in range(1, args.rows + 1):
            first = FIRST_NAMES[(index - 1) % len(FIRST_NAMES)]
            last = LAST_NAMES[((index - 1) // len(FIRST_NAMES)) % len(LAST_NAMES)]
            email = f"attendee-{index:05d}@example.test"
            phone = f"+234700{index:07d}"
            if args.inject_errors_every and index % args.inject_errors_every == 0:
                email = "not-an-email"
                phone = "0800-invalid"
            elif (
                args.inject_errors_every
                and index > 1
                and (index - 1) % args.inject_errors_every == 0
            ):
                email = previous_valid_email

            writer.writerow(
                {
                    "full_name": f"{first} {last} {index:05d}",
                    "email": email,
                    "phone": phone,
                    "organization": f"Synthetic group {((index - 1) % 25) + 1:02d}",
                    "source_reference": f"SYN-{index:05d}",
                }
            )
            if email != "not-an-email":
                previous_valid_email = email

    print(f"wrote {args.rows} synthetic rows to {args.output}")


if __name__ == "__main__":
    main()
