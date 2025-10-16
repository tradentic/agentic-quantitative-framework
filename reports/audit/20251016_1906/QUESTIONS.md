# Open Questions / Needed Inputs

1. **Supabase credentials** – Provide `SUPABASE_URL` and service role key (or confirm staging project) so RPC smoke tests and vector inserts can be exercised beyond static analysis.
2. **Embedding dimensions** – Confirm target dimensionality for TS2Vec/MiniRocket outputs so we can align pgvector columns (currently fixed at 128).
3. **MiniRocket dependency** – Should `sktime` be bundled in the default environment, or should we ship a pure NumPy fallback?
4. **DeepLOB weights** – Where should pretrained DeepLOB state_dict files live (Supabase storage bucket path, local artifact, or external vendor)?
5. **Prefect server** – Do we have a long-lived Prefect Cloud or self-hosted endpoint to target? Local CLI attempts spin up a temporary server that fails due to connection resets.
6. **Sample insider dataset** – Provide a minimal symbol/date slice (e.g., ticker + trade date) for validating the insider pipeline end-to-end without hitting live vendors.
7. **GPU availability** – Clarify whether production runs will have CUDA access for DeepLOB or if we should optimise CPU-only paths.
