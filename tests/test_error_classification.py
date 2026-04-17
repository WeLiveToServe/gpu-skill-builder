"""Tests for HTTP error classification in providers/base.py."""
from unittest.mock import MagicMock

import pytest

from providers.base import classify_http_error


def _mock_http_error(status_code: int, body: str = "") -> "httpx.HTTPStatusError":
    import httpx
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.text = body
    return httpx.HTTPStatusError(message="error", request=MagicMock(), response=response)


class TestClassifyHttpError:
    def test_401_mentions_credentials(self):
        err = _mock_http_error(401)
        msg = classify_http_error(err)
        assert "401" in msg
        assert "credential" in msg.lower() or "authentication" in msg.lower()

    def test_403_mentions_permissions(self):
        err = _mock_http_error(403)
        msg = classify_http_error(err)
        assert "403" in msg
        assert "permission" in msg.lower() or "authorization" in msg.lower()

    def test_429_mentions_rate_limit(self):
        err = _mock_http_error(429)
        msg = classify_http_error(err)
        assert "429" in msg
        assert "rate" in msg.lower()

    def test_400_includes_body(self):
        err = _mock_http_error(400, body='{"error": "bad request"}')
        msg = classify_http_error(err)
        assert "400" in msg
        assert "bad request" in msg

    def test_500_mentions_server_error(self):
        err = _mock_http_error(500, body="Internal Server Error")
        msg = classify_http_error(err)
        assert "500" in msg
        assert "server" in msg.lower()

    def test_generic_exception_returns_str(self):
        err = ValueError("something went wrong")
        msg = classify_http_error(err)
        assert "something went wrong" in msg

    def test_body_truncated_at_300_chars(self):
        long_body = "x" * 500
        err = _mock_http_error(400, body=long_body)
        msg = classify_http_error(err)
        assert len(msg) < 500


class TestClassifyHttpErrorNoHttpx:
    def test_falls_back_to_str_when_httpx_unavailable(self, monkeypatch):
        import sys
        monkeypatch.setitem(sys.modules, "httpx", None)
        # Non-httpx exception should still return str()
        err = RuntimeError("network timeout")
        msg = classify_http_error(err)
        assert "network timeout" in msg
