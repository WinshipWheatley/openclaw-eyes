"""Bounded, credential-free weather reads for the local operator front door."""

from __future__ import annotations

import hashlib
import http.client
import ipaddress
import json
import os
import re
import socket
import ssl
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping, MutableMapping


SCHEMA_VERSION = "weather_read_receipt_v1"
DEFAULT_PROFILE_PATH = Path("/home/openclaw/.openclaw/operator_weather_profile.json")
ALLOWED_HOSTS = frozenset(
    {"geocoding-api.open-meteo.com", "api.open-meteo.com"}
)
REQUEST_TIMEOUT_SECONDS = 2.5
MAX_RESPONSE_BYTES = 64 * 1024
CACHE_TTL_SECONDS = 300.0
MAX_CACHE_ENTRIES = 32

_CACHE: dict[str, tuple[float, "WeatherReadResult"]] = {}
_WEATHER_TERMS = re.compile(r"\b(weather|forecast|temperature|conditions)\b", re.I)
_EXPLICIT_LOCATION = re.compile(
    r"\b(?:weather|forecast|temperature|conditions)\s+(?:in|for|at)\s+(.+)$",
    re.I,
)
_TRAILING_SCOPE = re.compile(
    r"(?:\s+(?:today|tonight|tomorrow|right\s+now|this\s+(?:morning|afternoon|evening)))+$",
    re.I,
)

_WEATHER_CODES = {
    0: "clear",
    1: "mostly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "foggy",
    48: "foggy",
    51: "light drizzle",
    53: "drizzle",
    55: "heavy drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    71: "light snow",
    73: "snow",
    75: "heavy snow",
    80: "rain showers",
    81: "rain showers",
    82: "heavy rain showers",
    95: "thunderstorms",
    96: "thunderstorms with hail",
    99: "thunderstorms with hail",
}


@dataclass(frozen=True)
class WeatherReadResult:
    status: str
    location: str
    summary: str
    receipt: Mapping[str, Any]


class _NoWeatherRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Make redirects terminal so an allowlisted request cannot escape."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _PinnedWeatherResponse:
    def __init__(
        self,
        response: http.client.HTTPResponse,
        connection: http.client.HTTPSConnection,
        url: str,
    ) -> None:
        self._response = response
        self._connection = connection
        self._url = url

    def __enter__(self) -> "_PinnedWeatherResponse":
        return self

    def __exit__(self, *_args: Any) -> bool:
        self.close()
        return False

    def read(self, limit: int = -1) -> bytes:
        return self._response.read(limit)

    def geturl(self) -> str:
        return self._url

    def close(self) -> None:
        try:
            self._response.close()
        finally:
            self._connection.close()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def is_weather_request(text: Any) -> bool:
    return bool(_WEATHER_TERMS.search(str(text or "")))


def explicit_location_from_text(text: Any) -> str:
    match = _EXPLICIT_LOCATION.search(str(text or "").strip())
    if not match:
        return ""
    location = match.group(1).strip().rstrip("?.!,")
    location = _TRAILING_SCOPE.sub("", location).strip().rstrip("?.!,")
    return " ".join(location.split())[:160]


def _profile_path(profile_path: str | Path | None = None) -> Path:
    if profile_path is not None:
        return Path(profile_path)
    configured = os.environ.get("OPENCLAW_OPERATOR_WEATHER_PROFILE", "").strip()
    return Path(configured) if configured else DEFAULT_PROFILE_PATH


def read_saved_location(*, profile_path: str | Path | None = None) -> str:
    try:
        payload = json.loads(_profile_path(profile_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(payload, Mapping):
        return ""
    return " ".join(str(payload.get("location") or "").strip().split())[:160]


def save_operator_location(
    location: str,
    *,
    operator_approved: bool,
    profile_path: str | Path | None = None,
    saved_at: str | None = None,
) -> dict[str, Any]:
    if not operator_approved:
        raise PermissionError("operator approval is required to save a weather location")
    normalized = " ".join(str(location or "").strip().split())[:160]
    if not normalized:
        raise ValueError("location is required")
    target = _profile_path(profile_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    timestamp = saved_at or _utc_now()
    payload = {
        "location": normalized,
        "saved_at": timestamp,
        "schema_version": "operator_weather_profile_v1",
    }
    temporary = target.with_name(f".{target.name}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)
    return {
        "status": "SAVED",
        "operator_approved": True,
        "external_action_performed": False,
        "saved_at": timestamp,
    }


def _validate_weather_url(url: str) -> urllib.parse.ParseResult:
    parsed = urllib.parse.urlparse(url)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("weather URL has an invalid port") from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname not in ALLOWED_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
    ):
        raise ValueError("weather URL is not allowlisted")
    return parsed


def _validate_public_resolution(
    hostname: str,
    *,
    resolver: Callable[..., Any],
) -> tuple[str, ...]:
    records = resolver(
        hostname,
        443,
        type=socket.SOCK_STREAM,
    )
    addresses = tuple(
        dict.fromkeys(
            str(record[4][0]).split("%", 1)[0]
            for record in records
            if len(record) >= 5 and record[4]
        )
    )
    if not addresses:
        raise ValueError("weather host did not resolve")
    for address in addresses:
        try:
            resolved = ipaddress.ip_address(address)
        except ValueError as exc:
            raise ValueError("weather host resolved to an invalid address") from exc
        if not resolved.is_global:
            raise ValueError("weather host resolved to a non-public address")
    return addresses


def _open_pinned_request(
    request: urllib.request.Request,
    *,
    timeout: float,
    pinned_ip: str,
    server_hostname: str,
) -> _PinnedWeatherResponse:
    parsed = _validate_weather_url(request.full_url)
    if parsed.hostname != server_hostname or request.get_method() != "GET":
        raise ValueError("weather connection metadata is inconsistent")

    resolved = ipaddress.ip_address(pinned_ip)
    if not resolved.is_global:
        raise ValueError("weather connection target is not public")
    family = socket.AF_INET6 if resolved.version == 6 else socket.AF_INET
    sockaddr: tuple[Any, ...] = (
        (str(resolved), 443, 0, 0)
        if family == socket.AF_INET6
        else (str(resolved), 443)
    )

    raw_socket = socket.socket(family, socket.SOCK_STREAM)
    connection: http.client.HTTPSConnection | None = None
    wrapped_socket: Any = None
    try:
        raw_socket.settimeout(timeout)
        raw_socket.connect(sockaddr)
        context = ssl.create_default_context()
        wrapped_socket = context.wrap_socket(
            raw_socket,
            server_hostname=server_hostname,
        )
        peer_ip = ipaddress.ip_address(
            str(wrapped_socket.getpeername()[0]).split("%", 1)[0]
        )
        if not peer_ip.is_global or peer_ip != resolved:
            raise ValueError("weather connection peer did not match the validated address")

        connection = http.client.HTTPSConnection(
            server_hostname,
            443,
            timeout=timeout,
            context=context,
        )
        connection.sock = wrapped_socket
        target = parsed.path or "/"
        if parsed.query:
            target = f"{target}?{parsed.query}"
        headers = dict(request.header_items())
        headers["Host"] = server_hostname
        connection.request("GET", target, headers=headers)
        response = connection.getresponse()
        if not 200 <= response.status < 300:
            raise ValueError(f"weather endpoint returned HTTP {response.status}")
        return _PinnedWeatherResponse(response, connection, request.full_url)
    except Exception:
        if connection is not None:
            connection.close()
        elif wrapped_socket is not None:
            wrapped_socket.close()
        else:
            raw_socket.close()
        raise


def _read_json_get(
    url: str,
    *,
    opener: Callable[..., Any],
    resolver: Callable[..., Any],
) -> Mapping[str, Any]:
    parsed = _validate_weather_url(url)
    addresses = _validate_public_resolution(str(parsed.hostname), resolver=resolver)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "OpenClaw local weather read/1.0"},
        method="GET",
    )
    with opener(
        request,
        timeout=REQUEST_TIMEOUT_SECONDS,
        pinned_ip=addresses[0],
        server_hostname=str(parsed.hostname),
    ) as response:
        get_url = getattr(response, "geturl", None)
        final_url = str(get_url() if callable(get_url) else url)
        final_parsed = _validate_weather_url(final_url)
        if final_parsed.hostname != parsed.hostname:
            raise ValueError("weather redirects are not allowed")
        body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError("weather response exceeded size limit")
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("weather response was not an object")
    return payload


def _format_number(value: Any) -> str:
    number = float(value)
    return str(int(number)) if number.is_integer() else f"{number:.1f}"


def _receipt(
    *,
    status: str,
    location: str,
    observed_at: str,
    network_performed: bool,
    cache_hit: bool = False,
    cache_age_seconds: float = 0.0,
    error_type: str = "",
) -> dict[str, Any]:
    material = f"{status}\0{location}\0{observed_at}"
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "receipt_id": f"weather-read:{hashlib.sha256(material.encode('utf-8')).hexdigest()[:16]}",
        "status": status,
        "location": location,
        "observed_at": observed_at,
        "network_performed": network_performed,
        "network_method": "GET" if network_performed else "NONE",
        "allowlisted_hosts": sorted(ALLOWED_HOSTS),
        "arbitrary_url_allowed": False,
        "redirects_allowed": False,
        "private_network_allowed": False,
        "dns_resolution_validated": network_performed,
        "connection_ip_pinned": network_performed,
        "credential_use": False,
        "external_action_performed": False,
        "send_or_payment_allowed": False,
        "cache_hit": cache_hit,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
    }
    if cache_hit:
        receipt["cache_age_seconds"] = cache_age_seconds
    if error_type:
        receipt["error_type"] = error_type
    return receipt


def read_weather(
    text: str,
    *,
    saved_location: str | None = None,
    opener: Callable[..., Any] | None = None,
    resolver: Callable[..., Any] | None = None,
    now_fn: Callable[[], str] | None = None,
    now_epoch_fn: Callable[[], float] | None = None,
    cache: MutableMapping[str, tuple[float, WeatherReadResult]] | None = None,
) -> WeatherReadResult:
    observed_at = (now_fn or _utc_now)()
    location = explicit_location_from_text(text)
    if not location:
        location = (
            read_saved_location()
            if saved_location is None
            else " ".join(str(saved_location).strip().split())[:160]
        )
    if not location:
        return WeatherReadResult(
            status="LOCATION_REQUIRED",
            location="",
            summary="What city should I use for weather? I do not have a saved weather location yet.",
            receipt=_receipt(
                status="LOCATION_REQUIRED",
                location="",
                observed_at=observed_at,
                network_performed=False,
            ),
        )

    epoch = (now_epoch_fn or time.time)()
    active_cache = _CACHE if cache is None else cache
    cache_key = location.casefold()
    cached = active_cache.get(cache_key)
    if cached is not None:
        cached_at, cached_result = cached
        age = max(0.0, epoch - cached_at)
        if age <= CACHE_TTL_SECONDS:
            return replace(
                cached_result,
                receipt={
                    **dict(cached_result.receipt),
                    "cache_hit": True,
                    "cache_age_seconds": age,
                },
            )
        active_cache.pop(cache_key, None)

    open_url = opener or _open_pinned_request
    resolve_host = resolver or socket.getaddrinfo
    network_performed = False

    def tracked_open(
        request: urllib.request.Request,
        *,
        timeout: float,
        pinned_ip: str,
        server_hostname: str,
    ):
        nonlocal network_performed
        network_performed = True
        return open_url(
            request,
            timeout=timeout,
            pinned_ip=pinned_ip,
            server_hostname=server_hostname,
        )

    encoded = urllib.parse.urlencode(
        {"name": location, "count": 1, "language": "en", "format": "json"}
    )
    try:
        geocode = _read_json_get(
            f"https://geocoding-api.open-meteo.com/v1/search?{encoded}",
            opener=tracked_open,
            resolver=resolve_host,
        )
        results = geocode.get("results")
        if not isinstance(results, list) or not results or not isinstance(results[0], Mapping):
            raise LookupError("location_not_found")
        place = results[0]
        latitude = float(place["latitude"])
        longitude = float(place["longitude"])
        display_location = ", ".join(
            dict.fromkeys(
                str(part).strip()
                for part in (place.get("name"), place.get("admin1"), place.get("country"))
                if str(part or "").strip()
            )
        )
        forecast_query = urllib.parse.urlencode(
            {
                "latitude": latitude,
                "longitude": longitude,
                "current": (
                    "temperature_2m,apparent_temperature,precipitation,"
                    "weather_code,wind_speed_10m"
                ),
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
                "precipitation_unit": "inch",
                "timezone": "auto",
                "forecast_days": 1,
            }
        )
        forecast = _read_json_get(
            f"https://api.open-meteo.com/v1/forecast?{forecast_query}",
            opener=tracked_open,
            resolver=resolve_host,
        )
        current = forecast.get("current")
        if not isinstance(current, Mapping):
            raise ValueError("current weather missing")
        temperature = _format_number(current["temperature_2m"])
        feels_like = _format_number(current["apparent_temperature"])
        wind = _format_number(current.get("wind_speed_10m", 0))
        condition = _WEATHER_CODES.get(int(current.get("weather_code", -1)), "conditions reported")
        summary = (
            f"{display_location} is {temperature}°F and {condition}; "
            f"feels like {feels_like}°F, with wind at {wind} mph."
        )
        result = WeatherReadResult(
            status="READY",
            location=display_location,
            summary=summary,
            receipt=_receipt(
                status="READY",
                location=display_location,
                observed_at=observed_at,
                network_performed=network_performed,
            ),
        )
    except Exception as exc:
        result = WeatherReadResult(
            status="UNAVAILABLE",
            location=location,
            summary=f"Weather data for {location} is unavailable right now.",
            receipt=_receipt(
                status="UNAVAILABLE",
                location=location,
                observed_at=observed_at,
                network_performed=network_performed,
                error_type=type(exc).__name__,
            ),
        )

    if result.status == "READY":
        if len(active_cache) >= MAX_CACHE_ENTRIES:
            oldest = min(active_cache, key=lambda key: active_cache[key][0])
            active_cache.pop(oldest, None)
        active_cache[cache_key] = (epoch, result)
    return result


__all__ = [
    "WeatherReadResult",
    "explicit_location_from_text",
    "is_weather_request",
    "read_saved_location",
    "read_weather",
    "save_operator_location",
]
