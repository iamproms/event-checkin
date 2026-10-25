"""Public input boundaries and neutral responses without infrastructure."""

import pytest
from fastapi import HTTPException, Request
from pydantic import ValidationError

from app.api.registration import RegistrationBody, register
from app.registration.service import (
    RegistrationInvalid,
    normalize_email,
    normalize_name,
    normalize_phone,
    validate_answers,
)


def test_contact_normalization_and_field_validation() -> None:
    assert normalize_email("  Alice+Ticket@Exämple.com  ") == "alice+ticket@xn--exmple-cua.com"
    assert normalize_phone(" +234 (801) 234-5678 ") == "+2348012345678"
    assert normalize_name("  Ada  ") == "Ada"
    for value in ("08012345678", "+0 123", "+234 hello"):
        with pytest.raises(RegistrationInvalid):
            normalize_phone(value)
    schema = {
        "fields": [
            {
                "key": "meal",
                "label": "Meal",
                "type": "select",
                "required": True,
                "options": ["Vegan", "Other"],
            },
            {"key": "access", "label": "Access", "type": "checkbox", "required": True},
        ]
    }
    assert validate_answers(schema, {"meal": "Vegan", "access": True}) == {
        "meal": "Vegan",
        "access": True,
    }
    for answers in (
        {"meal": "Other", "access": False},
        {"meal": "Injected", "access": True},
        {"meal": "Vegan", "access": True, "extra": "x"},
    ):
        with pytest.raises(RegistrationInvalid):
            validate_answers(schema, answers)


class CaptureService:
    def __init__(self) -> None:
        self.calls = 0

    def register(self, host: str, slug: str, peer: str, **data: object) -> None:
        assert host == "event.example.test" and slug == "demo"
        assert data["marketing_opt_in"] is False
        self.calls += 1


def test_public_api_has_no_tenant_selector_and_rejects_cross_origin() -> None:
    capture = CaptureService()
    payload = {
        "full_name": "Ada",
        "email": "ada@example.test",
        "phone": "+2348012345678",
        "custom_answers": {},
        "form_version": 1,
        "notice_version": 1,
        "notice_acknowledged": True,
    }
    with pytest.raises(ValidationError):
        RegistrationBody.model_validate({**payload, "tenant_id": "elsewhere"})
    body = RegistrationBody.model_validate(payload)
    evil = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [(b"origin", b"https://evil.example.test")],
            "client": ("192.0.2.1", 1234),
        }
    )
    evil.state.trusted_hostname = "event.example.test"
    evil.state.trusted_origin = "https://event.example.test"
    evil.state.client_address = "192.0.2.1"
    with pytest.raises(HTTPException) as denied:
        register("demo", body, evil, capture)  # type: ignore[arg-type]
    assert denied.value.status_code == 403
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [],
            "client": ("192.0.2.1", 1234),
        }
    )
    request.state.trusted_hostname = "event.example.test"
    request.state.trusted_origin = "https://event.example.test"
    request.state.client_address = "192.0.2.1"
    response = register("demo", body, request, capture)  # type: ignore[arg-type]
    assert "ticket will arrive" in response["message"]
    assert capture.calls == 1
