# Coding Agent Prompt — NVDA Insider Default & Alerts (v1)

You are a coding agent working **from the repo root**. Implement a minimal, surgical set of changes so that **NVIDIA (ticker: `NVDA`) is the default focus** for insider-filing ingestion and monitoring, and add an initial **rule-based alert** when fresh CEO insider activity overlaps with a rising price regime. Keep all changes small, testable, and reversible. Do not modify unrelated code.

> Assumptions: DB-backed environment available (Postgres/Supabase), Prefect used for orchestration, existing Form 4 ingest flow present. Avoid hard-coding secrets.

---

## Objectives

1. **Default symbol = NVDA** across CLI, configs, and flows (overridable by flags/env).
2. **Single-filing & NVDA-focused ingest** ergonomics (URL/accession/symbol, dry-run supported).
3. **Alerting rule:** flag recent **CEO** Form-4 events that occur while short-term price trend is **up**.
4. **Daily monitor deployment:** a Prefect deployment that checks NVDA once per business day and logs or emits an alert record.

---

## Env & config

Update `.env.example` (do not commit secrets):

```
# Defaults
DEFAULT_SYMBOL="NVDA"              # can be overridden by CLI --symbol
DEFAULT_ISSUER_CIK=""             # optional; agent may resolve dynamically

# SEC / EDGAR
SEC_USER_AGENT="Your Name (email or site)"

# Market data (price/momentum) — choose your vendor keys if needed
VENDOR_API_KEY=""

# Alert sink (choose one or more)
ALERT_WEBHOOK_URL=""              # optional: Slack/Teams/webhook
ALERT_EMAIL=""                    # optional
```

Create a config file with sensible defaults:

* `configs/watchlist.yaml`

```yaml
symbols:
  - NVDA
priority_insiders:
  NVDA:
    - Jensen Huang
```

*(If you prefer exact identifiers, allow fuzzy name match and/or role == "CEO" from Form 4 headers.)*

---

## PR-1: CLI & flow defaults (NVDA)

**Goal:** Make NVDA the default target while keeping everything overridable.

**Files:** `flows/ingest_sec_form4.py` (or your actual entrypoint), `framework/config.py`

* Add `--symbol` to the ingest CLI; default = `os.getenv("DEFAULT_SYMBOL", "NVDA")`.
* Preserve `--xml-url` / `--accession` / `--date` modes; precedence:

  1. `--xml-url` (single filing)
  2. `--accession` (single filing)
  3. `--date` (+ `--limit`, filtered by `--symbol` when provided)
* Ensure that when range/date mode is used, **filter to NVDA** by default after parsing (compare `issuerTradingSymbol`).
* Help text: show explicit NVDA default and examples.

**Tests:** `tests/flows/test_cli_defaults.py`

* Help shows `--symbol` defaulting to NVDA.
* When nothing is passed, internal `args.symbol == "NVDA"`.

---

## PR-2: Insider role filter & recent-window helper

**Goal:** Easily detect CEO filings and “recent” status.

**Files:** `framework/sec_parse.py`, `features/insider_helpers.py`

* Extend the Form-4 parse to expose **reporting owner name** and **title/relationship** if present (often under `reportingOwnerRelationship/officerTitle`).
* Add `is_ceo(reporting_owner_block) -> bool` (string contains "CEO" case-insensitive).
* Add a tiny helper: `is_recent_filing(filing_date, now, days=7) -> bool`.

**Tests:** `tests/framework/test_insider_helpers.py` with small XML fixtures for officerTitle parsing.

---

## PR-3: Price-trend feature (lightweight)

**Goal:** Compute “price rising” flag for NVDA using a short lookback.

**Files:** `features/price_trend.py`, vendor client if needed (`framework/vendor_markets.py`).

* Implement `get_price_series(symbol, start, end, interval='1d')` via your vendor client (or reuse existing), returning close prices.
* Compute:

  * `ret_5d = close[-1]/close[-6] - 1`
  * `high_20d = close[-1] >= rolling_max_20d`
  * `trend_up = (ret_5d > 0) or high_20d`
* Return `{ret_5d, high_20d, trend_up}`.

**Tests:** `tests/features/test_price_trend.py` using a synthetic rising series (no network).

---

## PR-4: Alert rule & sink

**Goal:** Create an alert when (recent CEO filing) AND (trend_up == True).

**Files:** `alerts/insider_nvda.py`, `framework/alerts.py`

* `evaluate_nvda_insider_alert(symbol='NVDA', lookback_days=7)`:

  1. Pull recent Form-4s for `symbol` in `lookback_days`.
  2. Keep only filings where any `reportingOwner` satisfies `is_ceo(...)`.
  3. Compute price trend for the past 20 trading days.
  4. If CEO filing exists **and** `trend_up`, build an `Alert` object:

     ```json
     {
       "symbol": "NVDA",
       "window": "YYYY-MM-DD..YYYY-MM-DD",
       "ceo_filings": <count>,
       "latest_filing": {"date": "YYYY-MM-DD", "owner": "...", "code": "S|P|M|A|D"},
       "trend_up": true,
       "ret_5d": 0.06,
       "high_20d": true,
       "severity": "HIGH"
     }
     ```
* Implement an alert sink function that either:

  * Writes to a table `insider_alerts` (if you want persistence), **or**
  * Posts JSON to `ALERT_WEBHOOK_URL`, **or**
  * Logs a structured line `[ALERT] {...json...}` if no sink configured.

**Tests:** `tests/alerts/test_insider_nvda_rule.py` with synthetic inputs (mocked vendor + parsed Form-4s).

---

## PR-5: Prefect daily monitor (NVDA)

**Goal:** A scheduled deployment that evaluates the NVDA rule daily.

**Files:** `flows/monitor_nvda_insider.py`, `prefect.yaml`

* New flow `monitor_nvda_insider()`:

  * Calls `evaluate_nvda_insider_alert('NVDA')`.
  * Emits to sink/log.
* Add a deployment `monitor-nvda-insider` with a weekday schedule (e.g., 21:00 UTC) and the correct `entrypoint: flows/monitor_nvda_insider.py:monitor_nvda_insider`.

**Tests:** `tests/flows/test_monitor_entrypoint.py`

* Importable entrypoint; no runtime execution required.

---

## PR-6: Docs & runbooks

**Goal:** Make it easy to run a single NVDA check or monitor.

**Files:** `docs/runbooks/nvda_insider_monitor.md`

* Examples:

  ```bash
  # Single filing by URL (dry-run)
  python -m flows.ingest_sec_form4 --xml-url "$TEST_FORM4_URL" --dry-run --symbol NVDA

  # Evaluate NVDA alert now
  python -m flows.monitor_nvda_insider
  ```
* Describe severity rationale and how to override `DEFAULT_SYMBOL`/watchlist.

---

## Acceptance criteria

* `--symbol` exists and defaults to **NVDA**; help text shows it.
* Parsing exposes `officerTitle`; `is_ceo(...)` returns True for CEO titles.
* Price-trend feature returns `{ret_5d, high_20d, trend_up}` with correct logic on synthetic data.
* Alert rule produces a **HIGH** alert when (CEO filing within 7 days) **and** (trend_up).
* New Prefect deployment `monitor-nvda-insider` is importable and listed by `prefect deployments ls` after deploy.
* Docs provide copy-paste commands; CI/unit tests pass.

---

## Quick operator smoke (after merge)

```bash
# Ensure env
export SEC_USER_AGENT="Your Name (you@example.com)"
export DEFAULT_SYMBOL="NVDA"

# Ingest one real Form 4 (dry-run)
python -m flows.ingest_sec_form4 --xml-url "$TEST_FORM4_URL" --symbol NVDA --dry-run

# Evaluate the NVDA alert rule now
python -m flows.monitor_nvda_insider

# Deploy the daily monitor
prefect deploy --prefect-file prefect.yaml
prefect deployments ls | rg monitor-nvda-insider
```

> Keep PRs small and focused. Make no claims about trading outcomes; this is an **operational alert** for review, not advice.
