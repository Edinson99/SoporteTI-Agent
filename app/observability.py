"""Metricas locales y controles de trafico sin guardar contenido de solicitudes."""

from __future__ import annotations

import os
import threading
import time
from collections import Counter, OrderedDict, defaultdict, deque
from pathlib import PurePath
from typing import Any


class RequestTelemetry:
    """Agrega contadores y latencias en memoria usando solo rutas parametrizadas."""

    def __init__(self) -> None:
        self.started_at = time.monotonic()
        self._lock = threading.Lock()
        self._counts: Counter[tuple[str, str, int]] = Counter()
        self._latency_totals: defaultdict[tuple[str, str], float] = defaultdict(float)
        self._latency_max: defaultdict[tuple[str, str], float] = defaultdict(float)

    def record(
        self,
        method: str,
        route: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        key = (method.upper(), route, status_code)
        route_key = (method.upper(), route)
        with self._lock:
            self._counts[key] += 1
            self._latency_totals[route_key] += duration_seconds
            self._latency_max[route_key] = max(
                self._latency_max[route_key],
                duration_seconds,
            )

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            requests = [
                {
                    "method": method,
                    "route": route,
                    "status_code": status,
                    "count": count,
                }
                for (method, route, status), count in sorted(self._counts.items())
            ]
            latencies = [
                {
                    "method": method,
                    "route": route,
                    "average_ms": round(
                        self._latency_totals[(method, route)] / count * 1000,
                        2,
                    ),
                    "max_ms": round(self._latency_max[(method, route)] * 1000, 2),
                    "count": count,
                }
                for (method, route), count in sorted(self._latency_totals.items())
                for count in (
                    sum(
                        value
                        for (count_method, count_route, _), value in self._counts.items()
                        if count_method == method and count_route == route
                    ),
                )
                if count
            ]
        return {
            "uptime_seconds": round(time.monotonic() - self.started_at, 2),
            "requests": requests,
            "latency": latencies,
            "server_errors": sum(
                item["count"]
                for item in requests
                if item["status_code"] >= 500
            ),
        }


class SlidingWindowRateLimiter:
    """Límite por ruta y origen de conexión, mantenido solo en memoria."""

    def __init__(self, *, limit: int, window_seconds: int = 60) -> None:
        if limit < 1 or window_seconds < 1:
            raise ValueError("El limite y la ventana deben ser positivos.")
        self.limit = limit
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._requests: OrderedDict[tuple[str, str], deque[float]] = OrderedDict()

    def allow(self, client: str, route: str, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        key = (client, route)
        cutoff = current - self.window_seconds
        with self._lock:
            requests = self._requests.setdefault(key, deque())
            while requests and requests[0] <= cutoff:
                requests.popleft()
            if len(requests) >= self.limit:
                self._requests.move_to_end(key)
                return False
            requests.append(current)
            self._requests.move_to_end(key)
            while len(self._requests) > 2048:
                self._requests.popitem(last=False)
            return True


def rate_limit_from_environment() -> int:
    raw_value = os.getenv("SOPORTE_RATE_LIMIT_PER_MINUTE", "60").strip()
    try:
        limit = int(raw_value)
    except ValueError as exc:
        raise ValueError(
            "SOPORTE_RATE_LIMIT_PER_MINUTE debe ser un entero positivo."
        ) from exc
    if limit < 1:
        raise ValueError("SOPORTE_RATE_LIMIT_PER_MINUTE debe ser positivo.")
    return limit


def scrub_sentry_event(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any]:
    """Conserva el tipo de error y frames sin mensajes ni datos de solicitud."""
    sanitized = {
        key: event[key]
        for key in ("event_id", "timestamp", "platform", "level", "logger")
        if key in event
    }
    exception = event.get("exception")
    if isinstance(exception, dict):
        values = exception.get("values")
        if isinstance(values, list):
            safe_values = []
            for value in values:
                if not isinstance(value, dict):
                    continue
                safe_value: dict[str, Any] = {}
                if isinstance(value.get("type"), str):
                    safe_value["type"] = value["type"]
                stacktrace = value.get("stacktrace")
                if isinstance(stacktrace, dict):
                    frames = stacktrace.get("frames")
                    if isinstance(frames, list):
                        safe_frames = []
                        for frame in frames:
                            if not isinstance(frame, dict):
                                continue
                            safe_frame = {
                                key: frame[key]
                                for key in ("function", "lineno")
                                if key in frame
                            }
                            filename = frame.get("filename")
                            if isinstance(filename, str):
                                safe_frame["filename"] = PurePath(filename).name
                            safe_frames.append(safe_frame)
                        safe_value["stacktrace"] = {"frames": safe_frames}
                safe_values.append(safe_value)
            if safe_values:
                sanitized["exception"] = {"values": safe_values}
    return sanitized


def configure_sentry() -> bool:
    """Activa Sentry solo con DSN; elimina solicitudes y mensajes del evento."""
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
    except ImportError as exc:
        raise RuntimeError(
            "SENTRY_DSN esta configurado, pero falta sentry-sdk; "
            "instala requirements-observability.txt."
        ) from exc
    sentry_sdk.init(
        dsn=dsn,
        send_default_pii=False,
        before_send=scrub_sentry_event,
        integrations=[FastApiIntegration()],
        traces_sample_rate=0.0,
    )
    return True
