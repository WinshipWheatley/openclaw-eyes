from __future__ import annotations

import json
import socket
from pathlib import Path
from urllib.parse import urlparse

import pytest

import weather_read_capability as weather


class _Response:
    def __init__(self, payload: dict, *, final_url: str = "https://api.open-meteo.com/"):
        self._body = json.dumps(payload).encode("utf-8")
        self._final_url = final_url

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, limit: int = -1) -> bytes:
        return self._body if limit < 0 else self._body[:limit]

    def geturl(self) -> str:
        return self._final_url


def _public_resolver(host: str, port: int, **_kwargs):
    return [
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("8.8.8.8", port))
    ]


def test_missing_location_never_calls_network() -> None:
    calls: list[object] = []

    result = weather.read_weather(
        "What's the weather today?",
        saved_location="",
        opener=lambda *_args, **_kwargs: calls.append(object()),
    )

    assert result.status == "LOCATION_REQUIRED"
    assert calls == []
    assert result.receipt["network_performed"] is False
    assert result.receipt["external_action_performed"] is False
    assert "city" in result.summary.lower()


def test_weather_read_uses_only_allowlisted_gets_and_emits_fresh_receipt() -> None:
    requests = []
    responses = iter(
        (
            _Response(
                {
                    "results": [
                        {
                            "name": "Annapolis",
                            "admin1": "Maryland",
                            "country": "United States",
                            "latitude": 38.9784,
                            "longitude": -76.4922,
                        }
                    ]
                }
            ),
            _Response(
                {
                    "current": {
                        "time": "2026-07-15T19:45",
                        "temperature_2m": 84.0,
                        "apparent_temperature": 88.0,
                        "precipitation": 0.0,
                        "weather_code": 1,
                        "wind_speed_10m": 7.5,
                    },
                    "current_units": {
                        "temperature_2m": "°F",
                        "apparent_temperature": "°F",
                        "precipitation": "inch",
                        "wind_speed_10m": "mph",
                    },
                }
            ),
        )
    )

    def opener(request, *, timeout, pinned_ip, server_hostname):
        assert pinned_ip == "8.8.8.8"
        assert server_hostname in weather.ALLOWED_HOSTS
        requests.append((request, timeout))
        response = next(responses)
        response._final_url = request.full_url
        return response

    result = weather.read_weather(
        "What's the weather in Annapolis, MD today?",
        opener=opener,
        resolver=_public_resolver,
        now_fn=lambda: "2026-07-15T23:45:00+00:00",
        cache={},
    )

    assert result.status == "READY"
    assert result.location == "Annapolis, Maryland, United States"
    assert "84°F" in result.summary
    assert "feels like 88°F" in result.summary
    assert len(requests) == 2
    assert {urlparse(item[0].full_url).hostname for item in requests} == {
        "geocoding-api.open-meteo.com",
        "api.open-meteo.com",
    }
    assert all(item[0].get_method() == "GET" for item in requests)
    assert all(0 < item[1] <= 3.0 for item in requests)
    assert result.receipt["network_method"] == "GET"
    assert result.receipt["credential_use"] is False
    assert result.receipt["arbitrary_url_allowed"] is False
    assert result.receipt["connection_ip_pinned"] is True
    assert result.receipt["external_action_performed"] is False
    assert result.receipt["observed_at"] == "2026-07-15T23:45:00+00:00"


def test_weather_read_reuses_fresh_bounded_cache() -> None:
    cache = {}
    call_count = 0

    def opener(_request, *, timeout, pinned_ip, server_hostname):
        nonlocal call_count
        assert pinned_ip == "8.8.8.8"
        assert server_hostname in weather.ALLOWED_HOSTS
        call_count += 1
        if call_count == 1:
            response = _Response(
                {
                    "results": [
                        {
                            "name": "Annapolis",
                            "admin1": "Maryland",
                            "country": "United States",
                            "latitude": 38.9784,
                            "longitude": -76.4922,
                        }
                    ]
                }
            )
        else:
            response = _Response(
                {
                    "current": {
                        "time": "2026-07-15T19:45",
                        "temperature_2m": 84.0,
                        "apparent_temperature": 88.0,
                        "precipitation": 0.0,
                        "weather_code": 1,
                        "wind_speed_10m": 7.5,
                    },
                    "current_units": {},
                }
            )
        response._final_url = _request.full_url
        return response

    first = weather.read_weather(
        "weather in Annapolis, MD",
        opener=opener,
        resolver=_public_resolver,
        now_epoch_fn=lambda: 1000.0,
        cache=cache,
    )
    second = weather.read_weather(
        "weather in Annapolis, MD",
        opener=opener,
        resolver=_public_resolver,
        now_epoch_fn=lambda: 1100.0,
        cache=cache,
    )

    assert first.status == "READY"
    assert second.status == "READY"
    assert call_count == 2
    assert second.receipt["cache_hit"] is True
    assert second.receipt["cache_age_seconds"] == 100.0
    assert len(cache) == 1


def test_weather_read_rejects_private_dns_before_opening_network() -> None:
    opened = False

    def forbidden_opener(*_args, **_kwargs):
        nonlocal opened
        opened = True
        raise AssertionError("private DNS target reached the opener")

    def private_resolver(_host: str, port: int, **_kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", port))
        ]

    result = weather.read_weather(
        "weather in Annapolis, MD",
        opener=forbidden_opener,
        resolver=private_resolver,
        cache={},
    )

    assert result.status == "UNAVAILABLE"
    assert result.receipt["error_type"] == "ValueError"
    assert opened is False


def test_weather_read_pins_the_validated_ip_against_dns_rebinding() -> None:
    resolution_calls = 0
    connections = []

    def rebinding_resolver(_host: str, port: int, **_kwargs):
        nonlocal resolution_calls
        resolution_calls += 1
        address = "8.8.8.8" if resolution_calls == 1 else "127.0.0.1"
        return [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, port))
        ]

    def opener(request, *, timeout, pinned_ip, server_hostname):
        connections.append(
            {
                "url": request.full_url,
                "timeout": timeout,
                "pinned_ip": pinned_ip,
                "server_hostname": server_hostname,
            }
        )
        return _Response({"ok": True}, final_url=request.full_url)

    payload = weather._read_json_get(
        "https://api.open-meteo.com/v1/forecast?latitude=1&longitude=1",
        opener=opener,
        resolver=rebinding_resolver,
    )

    assert payload == {"ok": True}
    assert resolution_calls == 1
    assert connections == [
        {
            "url": "https://api.open-meteo.com/v1/forecast?latitude=1&longitude=1",
            "timeout": weather.REQUEST_TIMEOUT_SECONDS,
            "pinned_ip": "8.8.8.8",
            "server_hostname": "api.open-meteo.com",
        }
    ]


def test_pinned_weather_opener_uses_numeric_socket_with_hostname_sni(monkeypatch) -> None:
    observed = {}

    class RawSocket:
        def settimeout(self, timeout):
            observed["socket_timeout"] = timeout

        def connect(self, address):
            observed["connect_address"] = address

        def close(self):
            observed["raw_closed"] = True

    class WrappedSocket:
        def getpeername(self):
            return ("8.8.8.8", 443)

        def close(self):
            observed["wrapped_closed"] = True

    class Context:
        def wrap_socket(self, raw_socket, *, server_hostname):
            observed["wrapped_raw_socket"] = raw_socket
            observed["server_hostname"] = server_hostname
            return WrappedSocket()

    class HTTPResponse:
        status = 200

        def read(self, limit=-1):
            return b'{"ok": true}'

        def close(self):
            observed["response_closed"] = True

    class HTTPSConnection:
        def __init__(self, host, port, *, timeout, context):
            observed["connection"] = (host, port, timeout, context)
            self.sock = None

        def request(self, method, target, *, headers):
            observed["request"] = (method, target, headers)

        def getresponse(self):
            return HTTPResponse()

        def close(self):
            observed["connection_closed"] = True

    raw_socket = RawSocket()
    context = Context()
    monkeypatch.setattr(weather.socket, "socket", lambda family, kind: raw_socket)
    monkeypatch.setattr(weather.ssl, "create_default_context", lambda: context)
    monkeypatch.setattr(weather.http.client, "HTTPSConnection", HTTPSConnection)
    request = weather.urllib.request.Request(
        "https://api.open-meteo.com/v1/forecast?latitude=1&longitude=1",
        headers={"User-Agent": "OpenClaw test"},
        method="GET",
    )

    with weather._open_pinned_request(
        request,
        timeout=2.5,
        pinned_ip="8.8.8.8",
        server_hostname="api.open-meteo.com",
    ) as response:
        assert response.read() == b'{"ok": true}'

    assert observed["connect_address"] == ("8.8.8.8", 443)
    assert observed["server_hostname"] == "api.open-meteo.com"
    assert observed["request"][0:2] == (
        "GET",
        "/v1/forecast?latitude=1&longitude=1",
    )
    assert observed["request"][2]["Host"] == "api.open-meteo.com"
    assert observed["connection_closed"] is True


@pytest.mark.parametrize(
    "address",
    ("::ffff:127.0.0.1", "fc00::1", "fe80::1"),
)
def test_weather_read_rejects_mapped_and_native_private_ipv6(address: str) -> None:
    def resolver(_host: str, port: int, **_kwargs):
        return [
            (socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, port, 0, 0))
        ]

    with pytest.raises(ValueError, match="non-public"):
        weather._validate_public_resolution(
            "api.open-meteo.com",
            resolver=resolver,
        )


def test_weather_read_rejects_redirected_final_host() -> None:
    result = weather.read_weather(
        "weather in Annapolis, MD",
        opener=lambda *_args, **_kwargs: _Response(
            {"results": []},
            final_url="http://127.0.0.1/internal",
        ),
        resolver=_public_resolver,
        cache={},
    )

    assert result.status == "UNAVAILABLE"
    assert result.receipt["error_type"] == "ValueError"


def test_default_weather_opener_disables_redirects() -> None:
    handler = weather._NoWeatherRedirectHandler()
    request = weather.urllib.request.Request(
        "https://api.open-meteo.com/v1/forecast",
        method="GET",
    )

    assert handler.redirect_request(
        request,
        None,
        302,
        "Found",
        {},
        "https://127.0.0.1/internal",
    ) is None


def test_saved_location_requires_explicit_operator_approval(tmp_path: Path) -> None:
    profile = tmp_path / "weather-profile.json"

    with pytest.raises(PermissionError, match="operator approval"):
        weather.save_operator_location(
            "Annapolis, MD",
            profile_path=profile,
            operator_approved=False,
        )

    assert not profile.exists()


def test_approved_saved_location_round_trips_without_extra_fields(tmp_path: Path) -> None:
    profile = tmp_path / "weather-profile.json"

    receipt = weather.save_operator_location(
        "Annapolis, MD",
        profile_path=profile,
        operator_approved=True,
        saved_at="2026-07-15T23:50:00+00:00",
    )

    assert weather.read_saved_location(profile_path=profile) == "Annapolis, MD"
    assert json.loads(profile.read_text(encoding="utf-8")) == {
        "location": "Annapolis, MD",
        "saved_at": "2026-07-15T23:50:00+00:00",
        "schema_version": "operator_weather_profile_v1",
    }
    assert receipt["status"] == "SAVED"
    assert receipt["operator_approved"] is True
    assert receipt["external_action_performed"] is False
