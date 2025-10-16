# Questions Needed
1. Provide Supabase connection details (URL, service role key) or confirm local `.env` values so Supabase client and Prefect flows can run end-to-end.
2. Share market data vendor credentials (e.g., Polygon API key) and clarify acceptable usage limits for FINRA/SEC downloads to exercise microstructure + VPIN flows.
3. Confirm whether TS2Vec, MiniRocket (`sktime`), and DeepLOB (`torch`, weights path) should be installed in the shared environment or remain optional; if available, point to artifact locations.
4. Supply sample similarity-scan queries (embedding vectors or Supabase RPC filters) to validate `flows/similarity_scans.py` outputs.
5. Provide guidance on expected PCA artifact management (should agents auto-fit on demand or should a canonical artifact be supplied?).
