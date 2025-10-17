# Verification Prompt — Path A SEC Form 4 Ingest (v1)

You are a coding agent running **from the repo root** of `agentic-quantitative-framework`. Your job is to **verify, end‑to‑end**, that the Path A guide (“Repo Flow: Ingest a Real SEC Form 4”) is executable and error‑free on this machine. Generate evidence and a concise pass/fail report.

> **Prime directive:** Prefer read‑first, write‑light. Use transactions or targeted deletes for any DB writes. Capture command outputs. Do **not** print secret values.

---

## Inputs (environment)

Set or read these inputs; **fail fast** if the required ones are missing:

* **Required:** `SEC_USER_AGENT` (string identifying user/email/site)
* **Required for persistence tests:** `DATABASE_URL` (Postgres/Supabase DSN)
* **One of:** `TEST_FORM4_XML_URL` **or** `TEST_FORM4_TXT_URL` (a real Form 4 filing URL; `.txt` is acceptable)

If `TEST_FORM4_*` vars are absent, stop with a clear message in the report asking the user to provide one URL.

---

## Deliverables

Create `reports/verification/SEC_Form4_PathA_<YYYYMMDD_HHMM>/` with:

1. `VERIFICATION.md` — summary, steps, results (pass/fail), and next steps
2. `VERIFICATION.json` — machine‑readable results (schema below)
3. `COMMAND_LOG.txt` — stdout/stderr concatenated from executed commands
4. `DB_CHECK.md` — pre/post row counts, sample rows, and cleanup notes

Also print a **console summary** (5 bullets) when done.

---

## Step‑by‑step procedure

### 0) Repo & environment preflight

1. Record repo info: branch, short SHA, dirty flag.
2. Confirm Python version ≥ 3.10.
3. Verify presence of `flows/ingest_sec_form4.py` (or the actual entrypoint path configured by the repo).
4. Run `python -m flows.ingest_sec_form4 --help` and capture help output; confirm it documents **at least one** of these flags: `--xml-url`, `--accession`, `--date`, `--limit`, `--dry-run`.
5. Confirm `SEC_USER_AGENT` is set (value redacted in logs).

### 1) (Optional) DB readiness — only if `DATABASE_URL` is present

1. Connect to DB; verify pgvector extension exists or is not required by this flow.
2. Dump existing counts for `insider_transactions` (or the table used by this flow) to `DB_CHECK.md`.

### 2) Dry‑run ingest — using a real Form 4 URL

1. Choose the URL: prefer `TEST_FORM4_XML_URL`; otherwise `TEST_FORM4_TXT_URL`.
2. Execute (from repo root):

   ```bash
   python -m flows.ingest_sec_form4 \
     --xml-url "$TEST_FORM4_XML_URL" \
     --dry-run
   ```

   If only a `.txt` URL is available, pass `--xml-url "$TEST_FORM4_TXT_URL"` and allow the flow to locate the embedded XML.
3. **Expectations:**

   * Exit code `0`
   * Console output contains parsed **issuer symbol**, **owner name(s)**, and **transactions** (date, code, shares, price, side)
   * A clear note that this was a **dry‑run** and **no DB write** occurred
4. Append stdout/stderr to `COMMAND_LOG.txt`.

### 3) CLI variants sanity (no persistence)

Run and log each; treat a failure as **warn** (not fatal) if the flag isn’t supported by this repo:

* By accession (if known): `python -m flows.ingest_sec_form4 --accession <ACCESSION> --dry-run`
* By date + limit: `python -m flows.ingest_sec_form4 --date <YYYY-MM-DD> --limit 1 --dry-run`
  Capture the exit codes and help text into `COMMAND_LOG.txt`.

### 4) Persist one filing (transactional)

**Only if `DATABASE_URL` is set.**

1. Start a DB transaction (or prepare a **targeted delete** by `source_url`) and note it in `DB_CHECK.md`.
2. Execute (same URL as step 2, but without `--dry-run`):

   ```bash
   python -m flows.ingest_sec_form4 \
     --xml-url "$TEST_FORM4_XML_URL"
   ```
3. **Expectations:**

   * Exit code `0`
   * At least one new row added to `insider_transactions` with **symbol**, **transaction_date**, **transaction_code**, **shares**, **px**, and a `source_url` matching the test URL
4. Record pre/post counts and show `SELECT symbol, transaction_date, transaction_code, shares, px FROM insider_transactions ORDER BY created_at DESC LIMIT 5;` in `DB_CHECK.md`.
5. **Cleanup:** if a transaction was opened, **ROLLBACK**; otherwise, run a targeted `DELETE FROM insider_transactions WHERE source_url = :test_url;` and record how many rows were removed.

### 5) Results & summary

* Mark each step as ✅/❌ with a one‑line justification.
* If any step failed, add a **Fix Plan** section with the smallest patch needed and the expected owner/file path.
* Emit a console summary:

  * Repo & SHA
  * Dry‑run ingest: pass/fail
  * Persist ingest: pass/fail (or skipped)
  * Rows written & cleanup status
  * Next actions

---

## `VERIFICATION.json` schema

```json
{
  "repo": {"branch": "string", "sha": "string", "dirty": true},
  "env": {"sec_user_agent": "present|missing", "database_url": "present|missing", "test_url": "present|missing"},
  "cli": {"help_ok": true, "flags": ["--xml-url", "--date", "--limit", "--dry-run"]},
  "dry_run": {"ran": true, "exit_code": 0, "parsed_symbol": "string", "transactions_found": true},
  "persist": {"ran": true, "exit_code": 0, "rows_added": 1, "rolled_back": true},
  "db": {"table": "insider_transactions", "pre_count": 0, "post_count": 1},
  "notes": "short free text"
}
```

---

## Tips & guards

* Rate‑limit HTTP calls and set a real `SEC_USER_AGENT` to avoid SEC blocks.
* If the flow expects different flags (e.g., `--url` instead of `--xml-url`), adapt the commands and record the difference in `VERIFICATION.md`.
* Prefer transactions for cleanup; if not feasible, use a targeted delete by `source_url`.

> Run these steps now. Populate the report directory with the artifacts above and print the console summary. Ensure every command that should succeed exits with code 0; otherwise report a minimal fix plan.
