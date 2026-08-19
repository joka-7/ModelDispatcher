"""Unit tests for provider-agnostic "retry after" hint extraction."""

from __future__ import annotations

from types import SimpleNamespace

from model_dispatcher.providers import (
    extract_retry_after_seconds,
    parse_retry_after_hint,
)


def test_parses_hours_minutes_seconds_message() -> None:
    assert parse_retry_after_hint("Please try again in 1h2m47.904s") == 3767.904


def test_parses_minutes_seconds_message() -> None:
    assert parse_retry_after_hint("Please try again in 48m55.872s") == 2935.872


def test_parses_plain_seconds_message() -> None:
    assert parse_retry_after_hint("retry after 30") == 30.0


def test_returns_none_for_a_message_with_no_hint() -> None:
    assert parse_retry_after_hint("rate limit exceeded") is None


def test_extract_prefers_the_http_header_over_message_text() -> None:
    exc = Exception(
        "try again in 1h0m0s"
    )  # would parse to 3600 if header weren't checked first
    exc.response = SimpleNamespace(headers={"retry-after": "12"})  # type: ignore[attr-defined]
    assert extract_retry_after_seconds(exc) == 12.0


def test_extract_falls_back_to_message_text_with_no_usable_header() -> None:
    exc = Exception("Please try again in 5s")
    assert extract_retry_after_seconds(exc) == 5.0


def test_extract_handles_a_non_numeric_header_gracefully() -> None:
    # An HTTP-date Retry-After value — rare for rate limits, but must not crash.
    exc = Exception("try again in 3s")
    exc.response = SimpleNamespace(  # type: ignore[attr-defined]
        headers={"retry-after": "Wed, 21 Oct 2026 07:28:00 GMT"}
    )
    assert extract_retry_after_seconds(exc) == 3.0


def test_extract_returns_none_when_nothing_is_found() -> None:
    assert extract_retry_after_seconds(Exception("boom")) is None


def test_extract_never_raises_on_a_malformed_response_object() -> None:
    exc = Exception("boom")
    exc.response = object()  # type: ignore[attr-defined] # no .headers at all
    assert extract_retry_after_seconds(exc) is None
