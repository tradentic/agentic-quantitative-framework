"""OpenTelemetry helpers for initializing tracing across the framework."""

from __future__ import annotations

import os
from threading import Lock

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter


_LOCK = Lock()
_CONFIGURED = False
_REQUESTS_INSTRUMENTED = False


def _build_exporter() -> BatchSpanProcessor:
    exporter_name = os.getenv("OTEL_TRACES_EXPORTER", "console").lower()
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")

    if exporter_name == "otlp" and endpoint:
        exporter = OTLPSpanExporter(endpoint=endpoint)
    elif endpoint:
        exporter = OTLPSpanExporter(endpoint=endpoint)
    else:
        exporter = ConsoleSpanExporter()

    return BatchSpanProcessor(exporter)


def init_tracing(service_name: str = "agentic-quant") -> trace.Tracer:
    """Initialize tracing once and return a tracer for the requested service."""

    global _CONFIGURED, _REQUESTS_INSTRUMENTED

    with _LOCK:
        if not _CONFIGURED:
            resource = Resource.create({SERVICE_NAME: os.getenv("OTEL_SERVICE_NAME", service_name)})
            provider = TracerProvider(resource=resource)
            provider.add_span_processor(_build_exporter())
            trace.set_tracer_provider(provider)
            _CONFIGURED = True

        if not _REQUESTS_INSTRUMENTED:
            RequestsInstrumentor().instrument()
            _REQUESTS_INSTRUMENTED = True

    return trace.get_tracer(service_name)


__all__ = ["init_tracing"]
