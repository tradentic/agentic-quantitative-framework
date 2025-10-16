-- Core tables and indexes for the Agentic Quantitative Framework.

create table if not exists public.signal_embeddings (
    id uuid primary key default gen_random_uuid(),
    asset_symbol text not null,
    time_range tstzrange not null,
    embedding vector(128) not null,
    regime_tag text,
    label jsonb default '{}'::jsonb,
    meta jsonb default '{}'::jsonb,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists signal_embeddings_time_idx
    on public.signal_embeddings using gist (time_range);

create index if not exists signal_embeddings_asset_idx
    on public.signal_embeddings (asset_symbol);

create index if not exists signal_embeddings_embedding_idx
    on public.signal_embeddings using ivfflat (embedding vector_cosine_ops)
    with (lists = 100);

create table if not exists public.signal_embeddings_archive (
    id uuid primary key default gen_random_uuid(),
    asset_symbol text not null,
    time_range tstzrange not null,
    embedding vector(128) not null,
    regime_tag text,
    label jsonb default '{}'::jsonb,
    meta jsonb default '{}'::jsonb,
    archived_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.feature_registry (
    feature_id uuid primary key default gen_random_uuid(),
    name text not null,
    version text not null,
    file_path text not null,
    description text default ''::text,
    status text not null default 'proposed',
    metadata jsonb default '{}'::jsonb,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create unique index if not exists feature_registry_name_version_idx
    on public.feature_registry (name, version);

create table if not exists public.backtest_results (
    id uuid primary key default gen_random_uuid(),
    strategy_id text not null,
    run_at timestamptz not null,
    config jsonb not null,
    metrics jsonb not null,
    artifacts_path text,
    created_at timestamptz not null default timezone('utc', now())
);

create index if not exists backtest_results_strategy_idx
    on public.backtest_results (strategy_id, run_at desc);

create table if not exists public.agent_state (
    agent_id text primary key,
    state jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.embedding_jobs (
    id uuid primary key default gen_random_uuid(),
    asset_symbol text not null,
    windows jsonb not null,
    metadata jsonb default '{}'::jsonb,
    status text not null default 'pending',
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists embedding_jobs_status_idx
    on public.embedding_jobs (status, created_at desc);
