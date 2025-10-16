# Similarity Scans over Signal Fingerprints

## Motivation
- Rapidly identify historical windows most similar to a live signal fingerprint for recall, labeling, or human review.
- Support analysts with provenance-linked context when investigating sudden regime shifts or anomalous signals.

## Inputs & Outputs
- **Inputs:**
  - JSON file containing the query embedding (`symbol`, `window`, `embedding`, and optional `metadata`).
  - `k` nearest neighbours to retrieve.
  - Optional Supabase filter overrides (for example, `regime_tag=bull`).
- **Outputs:**
  - Console listing of the top-`k` match identifiers, scores, symbols, and windows.
  - Timestamped CSV report saved under `reports/similarity/` with rank, identifiers, similarity scores, and provenance URLs.
  - Markdown report mirroring the CSV content for lightweight sharing in notebooks or chat.

## Configuration
- `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` (or compatible public/anon variants) supplied via environment variables for pgvector access.
- `reports/similarity` directory configurable via `--output-dir`.
- `--allow-cross-symbol` to disable the default filter that constrains matches to the query symbol.
- Additional Supabase JSON filters applied through repeated `--filter key=value` flags.

## CLI Example
```bash
python -m flows.similarity_scans \
  ./data/aapl_window.json \
  --k 10 \
  --filter regime_tag=bull \
  --output-dir reports/similarity \
  --allow-cross-symbol
```

## Failure Modes
- `MissingSupabaseConfiguration` if Supabase credentials are not present in the environment.
- `ValueError` when the query JSON lacks required keys (`symbol`, `window`, or `embedding`).
- Downstream RPC errors from Supabase when the `match_signal_embeddings` function is unavailable or misconfigured.
- IO errors when the reports directory cannot be created or written to.

## Validation Checks
- Unit tests cover query parsing, report generation, filter parsing, and Supabase result normalization.
- Report writers validated against temporary directories to ensure both CSV and Markdown outputs are created with expected content.
- Similarity score coercion tested for `score`, `similarity`, and `distance`-only payloads to guarantee consistent CLI output.
