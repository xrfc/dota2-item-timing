import json

import httpx
import pytest

from dota_items.sources.opendota import fetch_match


def test_fetch_preserves_raw_response_and_cache_avoids_second_request(tmp_path):
    calls = []
    raw = b'{"match_id":42, "players":[]}'

    def handle(request):
        calls.append(request)
        return httpx.Response(200, content=raw)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        path = fetch_match(42, tmp_path, client=client)
        assert path.read_bytes() == raw
        assert fetch_match(42, tmp_path, client=client) == path
    assert len(calls) == 1
    manifest = json.loads(path.with_suffix(".manifest.json").read_text())
    assert manifest["source"] == "opendota"


def test_mismatched_payload_is_not_cached(tmp_path):
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"match_id": 43}))
    ) as client:
        with pytest.raises(ValueError, match="unexpected"):
            fetch_match(42, tmp_path, client=client)
    assert not (tmp_path / "42.json").exists()


def test_long_rate_limit_wait_is_not_ignored(tmp_path):
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(429, headers={"Retry-After": "120"})
        )
    ) as client:
        with pytest.raises(ValueError, match="longer wait"):
            fetch_match(42, tmp_path, client=client)


def test_network_error_does_not_expose_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENDOTA_API_KEY", "test-secret")

    def handle(request):
        raise httpx.ConnectError(str(request.url), request=request)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError) as error:
            fetch_match(42, tmp_path, client=client)
    assert "test-secret" not in str(error.value)
