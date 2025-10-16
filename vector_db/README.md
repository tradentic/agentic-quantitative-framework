# Vector Memory Operations

The vector database stores embeddings for engineered features, strategy
summaries, and anomaly cases. Components:

- `schemas/` SQL definitions for pgvector-backed tables.
- `sync/` utilities that refresh embeddings after agent-driven retrains.
- `monitoring/` notebooks or scripts that track drift and recall quality.

Use the Supabase SQL migration at `supabase/vector_db/setup_pgvector.sql`
when bootstrapping a new environment.
