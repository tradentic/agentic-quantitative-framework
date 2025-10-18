# NVDA Insider Monitor Runbook

This runbook describes how to ingest NVIDIA (NVDA) Form 4 filings and evaluate the CEO alert rule locally.

## Prerequisites

* Configure environment variables:
  ```bash
  export SEC_USER_AGENT="Your Name (you@example.com)"
  export DEFAULT_SYMBOL="NVDA"
  ```
* Optionally set `DEFAULT_ISSUER_CIK` to help resolve accessions (NVDA: `0001045810`).

## Single filing ingestion

```bash
# Process a single Form 4 XML (dry-run, no persistence)
python -m flows.ingest_sec_form4 --xml-url "$TEST_FORM4_URL" --symbol NVDA --dry-run
```

You can also provide an accession number. The CLI will attempt to resolve it using the configured issuer CIK and default NVDA heuristics:

```bash
python -m flows.ingest_sec_form4 --accession 0001209191-24-031235 --symbol NVDA --dry-run
```

## Range ingestion

```bash
# Ingest the prior business day for NVDA only
python -m flows.ingest_sec_form4 --date "$(date -d 'yesterday' +%F)" --symbol NVDA
```

## Evaluate the alert rule immediately

```bash
python -m flows.monitor_nvda_insider
```

The flow logs the alert payload and dispatches to the configured sink (Supabase table, webhook, or log).

## Deployment

Register the scheduled Prefect deployment:

```bash
prefect deploy --prefect-file prefect.yaml --select monitor-nvda-insider
prefect deployments ls | rg monitor-nvda-insider
```

## Severity rationale

The alert is tagged as `HIGH` severity when:

1. A CEO Form 4 filing is detected within the lookback window (default 7 days), and
2. NVDA's short-term price trend is rising (`trend_up = True`).

Override the default symbol or issuer by exporting `DEFAULT_SYMBOL` / `DEFAULT_ISSUER_CIK` or by passing `--symbol` to the CLI.
