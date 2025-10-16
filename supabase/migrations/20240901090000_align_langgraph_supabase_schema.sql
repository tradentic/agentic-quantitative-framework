-- Align LangGraph agent tables with architecture review requirements.

create extension if not exists "uuid-ossp";
create extension if not exists vector;

create table if not exists public.signal_embeddings (
  id uuid primary key default gen_random_uuid(),
  asset_symbol text not null,
  time_range tstzrange not null,
  embedding vector(128) not null,
  regime_tag text,
  label jsonb,
  meta jsonb,
  created_at timestamptz default now()
);

alter table public.signal_embeddings
  alter column label set default '{}'::jsonb,
  alter column meta set default '{}'::jsonb,
  alter column created_at set default timezone('utc', now());

-- Prefer HNSW (robust default); keep IVFFlat commented as alternative.
drop index if exists public.signal_embeddings_embedding_idx;
create index if not exists signal_embeddings_hnsw
  on public.signal_embeddings using hnsw (embedding vector_cosine_ops);

-- Alternative:
-- create index if not exists signal_embeddings_ivfflat
--   on public.signal_embeddings using ivfflat (embedding vector_cosine_ops)
--   with (lists = 100);

create table if not exists public.feature_registry (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  version text not null,
  path text not null,
  meta jsonb,
  created_at timestamptz default now()
);

alter table public.feature_registry
  alter column meta set default '{}'::jsonb,
  alter column created_at set default timezone('utc', now());

create unique index if not exists feature_registry_name_version_idx
  on public.feature_registry (name, version);

create table if not exists public.backtest_results (
  id uuid primary key default gen_random_uuid(),
  config jsonb not null,
  metrics jsonb not null,
  artifacts jsonb,
  created_at timestamptz default now()
);

alter table public.backtest_results
  alter column artifacts set default '{}'::jsonb,
  alter column created_at set default timezone('utc', now());

