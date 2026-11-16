"""Input validation rules for the message: length, exactly one valid CTA link."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

MAX_MESSAGE_LENGTH = 200

_CANDIDATE = re.compile(r"(?:https?://|www\.)\S*", re.IGNORECASE)
_TRAILING = ".,;:!?)]}>\"'"
# Hostname: dotted labels, alphabetic (or punycode) TLD.
_HOST = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"(?:[a-z]{2,63}|xn--[a-z0-9-]{1,59})$"
)


class MessageValidationError(ValueError):
    """Raised with a human-readable reason when the message is not acceptable."""


def find_links(message: str) -> list[str]:
    """Return every link-looking token in the message, trailing punctuation removed."""
    return [m.group(0).rstrip(_TRAILING) for m in _CANDIDATE.finditer(message)]


def validate_url(link: str) -> str:
    """Validate a single URL; return it unchanged or raise MessageValidationError."""
    if link.lower().startswith("www."):
        raise MessageValidationError(
            f"Link must start with http:// or https:// (got '{link}')"
        )
    try:
        parts = urlsplit(link)
        host = parts.hostname
        _ = parts.port  # raises ValueError on a malformed/out-of-range port
    except ValueError:
        raise MessageValidationError(f"Invalid URL: '{link}'") from None
    if parts.scheme not in ("http", "https") or not host or not _HOST.match(host):
        raise MessageValidationError(f"Invalid URL: '{link}'")
    return link


def extract_link(message: str) -> str:
    """Return the single CTA link in the message, or raise MessageValidationError."""
    links = find_links(message)
    if not links:
        raise MessageValidationError(
            "Message must contain exactly one CTA link (found none)"
        )
    if len(links) > 1:
        raise MessageValidationError(
            f"Message must contain exactly one CTA link (found {len(links)})"
        )
    return validate_url(links[0])


def validate_message(message: str) -> str:
    """Full validation. Returns the cleaned (stripped) message."""
    text = message.strip()
    if not text:
        raise MessageValidationError("Message must not be empty")
    if len(text) > MAX_MESSAGE_LENGTH:
        raise MessageValidationError(
            f"Message must not exceed {MAX_MESSAGE_LENGTH} characters (got {len(text)})"
        )
    extract_link(text)
    return text
