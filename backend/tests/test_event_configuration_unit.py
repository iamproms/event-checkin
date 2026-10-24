"""Pure M2-03 validation, including time-zone and schema attack cases."""

from datetime import UTC, datetime, timedelta

import pytest

from app.events.service import EventInvalid, utc, validate_form, validate_timezone, validate_windows


def test_form_schema_bounds_and_injection() -> None:
    assert validate_form({"fields": []}) == {"fields": []}
    assert validate_form(
        {
            "fields": [
                {
                    "key": "meal",
                    "label": "Meal preference",
                    "type": "select",
                    "required": False,
                    "options": ["Vegan", "Other"],
                },
            ]
        }
    )["fields"]
    for schema in (
        {"fields": [{"key": "email", "label": "Email", "type": "text", "required": True}]},
        {
            "fields": [
                {
                    "key": "note",
                    "label": "<script>alert(1)</script>",
                    "type": "text",
                    "required": False,
                    "html": "<script>",
                }
            ]
        },
        {
            "fields": [
                {
                    "key": "note",
                    "label": "<script>alert(1)</script>",
                    "type": "text",
                    "required": False,
                }
            ]
        },
        {
            "fields": [
                {
                    "key": "x",
                    "label": "X",
                    "type": "select",
                    "required": False,
                    "options": ["Same", "Same"],
                }
            ]
        },
        {"fields": [{"key": "x", "label": "X", "type": "text", "required": False}] * 31},
    ):
        with pytest.raises(EventInvalid):
            validate_form(schema)


def test_explicit_offsets_utc_and_dst_window() -> None:
    assert validate_timezone("Africa/Lagos") == "Africa/Lagos"
    assert validate_timezone("America/New_York") == "America/New_York"
    with pytest.raises(EventInvalid):
        validate_timezone("Mars/Phobos")
    with pytest.raises(EventInvalid):
        utc(datetime(2026, 11, 1, 1, 30))
    # Both occurrences of 01:30 on a fall-back day represent distinct instants.
    first = datetime.fromisoformat("2026-11-01T01:30:00-04:00")
    second = datetime.fromisoformat("2026-11-01T01:30:00-05:00")
    assert utc(second) - utc(first) == timedelta(hours=1)
    validate_windows(first, second, first - timedelta(days=1), first, first, second)
    with pytest.raises(EventInvalid):
        validate_windows(first, second, None, first, first, second)
    with pytest.raises(EventInvalid):
        validate_windows(first, second, first, second + timedelta(hours=1), first, second)
    with pytest.raises(EventInvalid):
        validate_windows(first, second, None, None, first - timedelta(minutes=1), second)
    with pytest.raises(EventInvalid):
        validate_windows(
            datetime.now(UTC), datetime.now(UTC) - timedelta(hours=1), None, None, None, None
        )
