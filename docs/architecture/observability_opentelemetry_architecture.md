# 📡 Observability & OpenTelemetry Integration Design

This document outlines the proposed observability architecture for the `agentic-quantitative-framework`, enabling deep inspection of pipelines, agent tools, and Supabase interactions using OpenTelemetry (OTel).

---

## 🎯 Goals
- Trace vector transformations end-to-end: from SEC filings → features → embeddings → scans → backtests.
- Monitor runtime, embedding drift, agent choices, and Supabase RPC latency.
- Centralize logs, traces, and metrics for real-time debugging and model evaluation.

---

## 🧱 Architecture Overview

```text
┌────────────┐      ┌──────────────┐     ┌─────────────────┐
│  SEC Form4 │───▶ │ Ingest Flows │──▶ │ Supabase (pg)   │
└────────────┘      └─────┬────────┘     └─────┬─────────────┘
                           │                        │
         ┌────────────────▼─────────┐        ┌─────▼──────┐
         │ Feature + Embedding Flow │──────▶ │ Fingerprint │
         └────────────────┬─────────┘        └─────┬──────┘
                          │                         │
                    ┌────▼────────────┐      ┌─────▼──────────┐
                    │ Similarity Scan │────▶ │ Backtest Agent │
                    └────────────┬────┘      └────────────────┘
                                 │
                         ┌───────▼────────┐
                         │ LangGraph Loop │
                         └────────────────┘
```

Every stage emits OpenTelemetry **spans**, optionally tagged with:
- `symbol`, `date`, `embedding_type`, `vector_dim`
- `rpc.table`, `model`, `sharpe`, `drift_flag`

---

## 📦 Files & Instrumentation Points

### `observability/otel.py`
Initializes OpenTelemetry SDK and returns a tracer instance with Prefect compatibility.

```python
# observability/otel.py
import os
from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.requests import RequestsInstrumentor

def init_tracing(service_name="agentic-quant"):
    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)

    if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"]))
    else:
        processor = BatchSpanProcessor(ConsoleSpanExporter())

    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    RequestsInstrumentor().instrument()
    return trace.get_tracer(service_name)
```

### Supabase RPCs & Inserts
Wrap interactions like:
```python
with tracer.start_as_current_span("supabase.insert") as span:
    span.set_attribute("table", "signal_embeddings")
    span.set_attribute("rows", len(payload))
    supabase.insert(...)
```

### Prefect Flows
Set the following in the Codespaces or dev `.env.local`:
```env
OTEL_TRACES_EXPORTER=otlp
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
```
In Prefect tasks:
```python
from observability.otel import init_tracing
tracer = init_tracing("flow-sec-ingest")

@task
def ingest():
    with tracer.start_as_current_span("sec_fetch_and_parse"):
        ...
```

### LangGraph Agent Loop
Wrap tool calls:
```python
with tracer.start_as_current_span(f"agent_tool:{tool_name}"):
    result = await fn(...)
```

---

## 🔎 Suggested Span Names & Tags

| Layer           | Span Name                    | Attributes                        |
|----------------|------------------------------|-----------------------------------|
| Ingest         | `sec_ingest.form4_fetch`     | `cik`, `accession`                |
| Feature        | `features.ofi_l5`            | `symbol`, `lookback_window`       |
| Embedding      | `embeddings.ts2vec`          | `dim`, `embedding_type`           |
| Supabase       | `supabase.upsert`            | `table`, `rows`, `on_conflict`    |
| Fingerprints   | `pca.project`                | `source_dim`, `target_dim`        |
| Backtest       | `backtest.eval_model`        | `sharpe`, `auc`, `signal_version` |
| Agentic Tool   | `agent_tool:run_backtest`    | `tool_name`, `params`             |
| Drift Monitor  | `monitor.sharpe_check`       | `threshold`, `flagged`            |

---

## 🚀 Deployment: Running OTel Collector in Codespaces

In your Codespaces `.devcontainer/devcontainer.json`, add port forward:
```json
"forwardPorts": [4318]
```

Then create a startup command or run:
```bash
curl -LO https://github.com/open-telemetry/opentelemetry-collector-releases/releases/latest/download/otelcol_1.0.0_linux_amd64.tar.gz
mkdir otelcol && tar -xzf otelcol_1.0.0_linux_amd64.tar.gz -C otelcol
otelcol/otelcol --config=otelcol/config.yaml
```
Example `otelcol/config.yaml`:
```yaml
receivers:
  otlp:
    protocols:
      http:

exporters:
  logging:
    loglevel: debug

service:
  pipelines:
    traces:
      receivers: [otlp]
      exporters: [logging]
```

Make sure `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318` is active.

---

## 🧰 Tooling Summary
- `opentelemetry-sdk`
- `opentelemetry-exporter-otlp`
- `opentelemetry-instrumentation-requests`
- `otelcol` binary or Docker image

---

This setup enables detailed, multi-layer tracing of every vector, RPC, and decision node. It integrates seamlessly with Prefect and LangGraph workflows.

