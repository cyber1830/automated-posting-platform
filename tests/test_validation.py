import pytest

from app.validators import MessageValidationError, extract_link, validate_message

OK = "Check out our latest business platform and grow your online visibility. https://example.com"


def test_valid_message_returns_stripped_text():
    assert validate_message(f"  {OK}  ") == OK


def test_extract_link_strips_trailing_punctuation():
    assert extract_link("See https://example.com/a?b=1.") == "https://example.com/a?b=1"


@pytest.mark.parametrize(
    "message, reason",
    [
        ("", "empty"),
        ("   ", "empty"),
        ("no link here", "found none"),
        ("two https://a.com and https://b.com", "found 2"),
        ("same https://a.com https://a.com", "found 2"),
        ("go to www.example.com", "http:// or https://"),
        ("bad https://nodot", "Invalid URL"),
        ("bad https://", "Invalid URL"),
        ("bad https://exa_mple.com", "Invalid URL"),
        ("bad https://example.com:99999", "Invalid URL"),
        ("x" * 190 + " https://example.com", "200 characters"),
    ],
)
def test_invalid_messages(message, reason):
    with pytest.raises(MessageValidationError) as exc:
        validate_message(message)
    assert reason in str(exc.value)


def test_exactly_200_chars_is_allowed():
    link = "https://example.com"
    message = "a" * (200 - len(link) - 1) + " " + link
    assert len(message) == 200
    assert validate_message(message) == message
