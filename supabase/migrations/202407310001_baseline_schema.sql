-- Baseline schema for Supabase local development and migrations.

create extension if not exists "pgcrypto";
create extension if not exists "uuid-ossp";
create extension if not exists "vector";

create table if not exists public.signal_embeddings (
    id uuid primary key default gen_random_uuid(),
    asset_symbol text not null,
    time_range tstzrange not null,
    embedding vector(128) not null,
    regime_tag text,
    label jsonb not null default '{}'::jsonb,
    meta jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists signal_embeddings_asset_symbol_idx
    on public.signal_embeddings (asset_symbol, created_at desc);

create index if not exists signal_embeddings_time_range_idx
    on public.signal_embeddings using gist (time_range);

create index if not exists signal_embeddings_embedding_ivfflat_idx
    on public.signal_embeddings
    using ivfflat (embedding vector_cosine_ops)
    with (lists = 100);

create table if not exists public.signal_embeddings_archive (
    like public.signal_embeddings including defaults including constraints
);

create table if not exists public.feature_registry (
    feature_id uuid primary key default gen_random_uuid(),
    name text not null,
    version text not null,
    file_path text not null,
    description text,
    status text not null default 'proposed',
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (name, version)
);

create table if not exists public.backtest_results (
    id uuid primary key default gen_random_uuid(),
    strategy_id text not null,
    run_at timestamptz not null default now(),
    config jsonb not null,
    metrics jsonb not null,
    artifacts_path text
);

create index if not exists backtest_results_strategy_idx
    on public.backtest_results (strategy_id, run_at desc);

create table if not exists public.agent_state (
    agent_id text primary key,
    state jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now()
);

create table if not exists public.embedding_jobs (
    id uuid primary key default gen_random_uuid(),
    asset_symbol text not null,
    windows jsonb not null,
    metadata jsonb not null default '{}'::jsonb,
    status text not null default 'pending',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists embedding_jobs_status_idx
    on public.embedding_jobs (status, created_at);

create table if not exists public.backtest_requests (
    id uuid primary key default gen_random_uuid(),
    strategy_id text not null,
    config jsonb not null,
    status text not null default 'pending',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    completed_at timestamptz
);

comment on table public.signal_embeddings is 'Primary pgvector store for strategy embeddings.';
comment on table public.signal_embeddings_archive is 'Historical archive for pruned embeddings.';
comment on table public.feature_registry is 'Registry of feature proposals and versions.';
comment on table public.backtest_results is 'Stores summarized metrics and artifact paths for backtests.';
comment on table public.agent_state is 'Durable agent memory for LangGraph workflows.';
comment on table public.embedding_jobs is 'Queue of embedding refresh jobs consumed by Prefect flows.';
comment on table public.backtest_requests is 'Queue of backtest jobs orchestrated by Prefect.';
