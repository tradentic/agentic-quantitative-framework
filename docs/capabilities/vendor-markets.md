# Vendor Market Data Adapter

## Motivation
- Provide a single, typed interface for consuming vendor NBBO and trade data.
- Ensure downstream features receive timezone-aware, canonical DataFrames regardless of source.
- Support swapping vendors via configuration without code changes.

## Inputs
- `symbol` (`str`): ticker to query.
- `start`, `end` (`datetime`): timezone-aware UTC window.
- Environment variables:
  - `MARKET_VENDOR_SOURCE`: selects implementation (`polygon`).
  - `POLYGON_API_KEY`: secret for Polygon REST API.
  - Optional: `POLYGON_REST_BASE_URL`, `POLYGON_HTTP_TIMEOUT`, `POLYGON_PAGE_LIMIT` for tuning.

## Outputs
- Trades DataFrame with columns: `timestamp`, `price`, `size`, `exchange`, `conditions`, `sequence_number`, `participant_timestamp`, `trf_timestamp`, `tape`, `trade_id`, `trf_id`, `is_off_exchange`.
- Quotes DataFrame with columns: `timestamp`, `bid_price`, `bid_size`, `ask_price`, `ask_size`, `bid_exchange`, `ask_exchange`, `conditions`, `sequence_number`, `participant_timestamp`, `trf_timestamp`, `tape`, `is_off_exchange`.
- Both DataFrames are sorted ascending by SIP timestamp and use UTC timezone-aware `Timestamp` objects.

## Configs
- Configure via environment variables listed above.
- Set defaults for rate limits and pagination size through optional overrides.
- CLI respects `--vendor` flag to override environment defaults for ad-hoc testing.

## CLI Examples
```bash
export MARKET_VENDOR_SOURCE=polygon
export POLYGON_API_KEY="<your-api-key>"
python -m framework.vendor_markets AAPL 2024-01-02T09:30:00Z 2024-01-02T09:31:00Z
```
- Output prints head of trades and quotes DataFrames for inspection.

## Failure Modes
- Missing or empty API key raises `RuntimeError` during client resolution.
- Naive datetimes trigger `ValueError` enforcing timezone awareness.
- Network or HTTP errors bubble up as `RuntimeError` via request handling.
- Unsupported vendor in configuration raises a descriptive `RuntimeError`.

## Validation Checks
- Unit tests cover normalization schema and environment-based client resolution.
- CLI smoke test prints DataFrame heads for manual verification.
- Downstream consumers can assert non-empty frames and canonical columns before feature extraction.
