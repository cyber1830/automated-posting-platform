"""Pydantic request/response models."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.validators import MAX_MESSAGE_LENGTH, MessageValidationError, validate_message


class PostRequest(BaseModel):
    message: str = Field(
        ...,
        description=f"Max {MAX_MESSAGE_LENGTH} chars, containing exactly one http(s) link.",
        examples=[
            "Check out our latest business platform and grow your online visibility. https://example.com"
        ],
    )

    @field_validator("message")
    @classmethod
    def _check_message(cls, value: str) -> str:
        try:
            return validate_message(value)
        except MessageValidationError as exc:
            raise ValueError(str(exc)) from None


class PlatformResult(BaseModel):
    platform: str
    status: Literal["success", "failed"]
    posted_url: str | None = None
    public_access: bool = False
    date: str | None = Field(None, description="UTC date, YYYY-MM-DD")
    time: str | None = Field(None, description="UTC time, HH:MM:SS")
    error: str | None = None


class Summary(BaseModel):
    total: int
    succeeded: int
    failed: int


class PostResponse(BaseModel):
    success: bool = Field(description="True if at least one platform succeeded")
    summary: Summary
    results: list[PlatformResult]


class ErrorDetail(BaseModel):
    field: str
    message: str


class ValidationErrorResponse(BaseModel):
    success: Literal[False] = False
    error: Literal["validation_error"] = "validation_error"
    details: list[ErrorDetail]


class PlatformInfo(BaseModel):
    platform: str
    configured: bool
    missing_credentials: list[str]


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
