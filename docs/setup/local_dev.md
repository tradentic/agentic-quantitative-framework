# Local Development Setup with OpenTelemetry

The agentic quantitative framework now emits OpenTelemetry traces from Prefect flows,
LangGraph tools, and Supabase helpers. Follow the steps below to capture spans during
local development or inside GitHub Codespaces.

## 1. Install Python dependencies

Ensure you have installed the project with the new observability packages:

```bash
pip install -e .
```

This pulls in `opentelemetry-sdk`, the OTLP exporter, and the Requests instrumentation
used by `observability/otel.py`.

## 2. Configure environment variables

Add the following variables to your `.env.local` (or export them inside the Codespaces
shell). They are also documented in `.env.example`.

```env
OTEL_TRACES_EXPORTER=otlp
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
# Optional: override the default service name
# OTEL_SERVICE_NAME=agentic-quant-dev
```

Setting `OTEL_TRACES_EXPORTER=otlp` ensures Prefect and the custom tracer emit to the
collector described below. If you omit these variables the tracer falls back to the
console span exporter for quick debugging.

## 3. Run the OpenTelemetry Collector

The repository ships with a minimal collector configuration at `otelcol/config.yaml`
that exposes an OTLP/HTTP receiver and logs spans to stdout. You can run it locally with:

```bash
otelcol --config=otelcol/config.yaml
```

If the `otelcol` binary is not installed yet, download the latest release from the
[OpenTelemetry Collector repository](https://github.com/open-telemetry/opentelemetry-collector-releases)
and extract it into your workspace before running the command above.

### Codespaces tip

The devcontainer forwards port `4318` to your local machine. You can start the collector
from the Codespaces terminal:

```bash
./otelcol/otelcol --config=otelcol/config.yaml
```

The Prefect agent, flows, and LangGraph tools will automatically send spans to the
collector once it is running.

## 4. Verify spans

Run any Prefect flow (for example `python -m flows.ingest_sec_form4 --mock`) or trigger a
LangGraph tool. The collector logs should display spans such as `flow.ingest_form4`,
`supabase.upsert`, and `agent_tool:run_backtest` with helpful attributes like `symbol`,
`rows`, or `strategy_id`.

If you prefer console-only tracing, omit the OTLP variables and the tracer will switch to
the `ConsoleSpanExporter`.
