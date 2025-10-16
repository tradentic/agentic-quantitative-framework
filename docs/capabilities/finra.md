# FINRA Off-Exchange Feature Enrichment

## Motivation
Daily market structure features derived from FINRA datasets provide visibility into short-selling pressure and alternative trading system (ATS) activity. These signals augment existing `daily_features` records with execution quality indicators that improve downstream factor modeling and surveillance.

## Inputs
- **FINRA Reg SHO daily files** (`{FINRA_BASE_URL}/regsho/daily/{MARKET}shvolYYYYMMDD.txt`): provides short sale and exempt share volumes.
- **FINRA ATS weekly summary files** (`{FINRA_BASE_URL}/ATS/ATS_W_Summary_YYYYMMDD.zip`): aggregates ATS share and trade counts per symbol, with weekly totals.
- **Supabase `daily_features` table** (optional): used to discover symbols requiring enrichment and to persist computed features.

## Outputs
- Upserted rows in `daily_features` keyed by `(symbol, trade_date)` with three computed columns:
  - `short_vol_share`: daily short volume ÷ reported total volume.
  - `short_exempt_share`: daily short exempt volume ÷ reported total volume.
  - `ats_share_of_total`: weekly ATS share volume ÷ reported total share volume, broadcast to each trading day in the week.
- Returned list of feature dictionaries from the Prefect flow when `persist=False`.

## Configuration
- `FINRA_BASE_URL` (default `https://cdn.finra.org/equity`)
- `FINRA_SHORT_VOLUME_MARKET` (default `TOT`)
- `FINRA_HTTP_TIMEOUT`, `FINRA_HTTP_RETRIES`, `FINRA_HTTP_BACKOFF`, `FINRA_HTTP_USER_AGENT`
- Supabase credentials: `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` (or public equivalents) for persistence.

## CLI Examples
```bash
# Execute the Prefect flow for a single trading session without persistence
activate_venv && python -c "from datetime import date; from flows.compute_offexchange_features import compute_offexchange_features; print(compute_offexchange_features(date(2024, 4, 1), persist=False))"

# Run via Prefect CLI (requires registered deployment)
prefect deployment run compute-offexchange-features/trading-session --params '{"trade_date": "2024-04-01"}'
```

## Failure Modes
- Missing FINRA files (HTTP 404) return `None` for the affected symbol, leaving feature columns null.
- Network failures trigger exponential backoff retry; repeated errors propagate `FinraHTTPError`.
- Absence of Supabase credentials results in in-memory computation only (logged warning).

## Validation Checks
- Unit tests confirm parsing of Reg SHO text and ATS ZIP payloads.
- Flow logs emit symbol counts and persistence summaries for manual audit.
- Ratios are bounded in `[0, 1]` whenever denominators are positive.
