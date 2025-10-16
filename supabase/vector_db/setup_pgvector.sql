-- pgvector schema for signal embeddings used by LangGraph agents.

create extension if not exists vector;

create table if not exists public.signal_embeddings (
    id uuid primary key,
    asset_symbol text not null,
    time_range tstzrange not null,
    embedding vector(128) not null,
    regime_tag text,
    label jsonb default '{}'::jsonb,
    meta jsonb default '{}'::jsonb,
    created_at timestamptz default timezone('utc', now())
);

create table if not exists public.signal_embeddings_archive (
    id uuid primary key,
    asset_symbol text not null,
    time_range tstzrange not null,
    embedding vector(128) not null,
    regime_tag text,
    label jsonb default '{}'::jsonb,
    meta jsonb default '{}'::jsonb,
    archived_at timestamptz default timezone('utc', now())
);

create index if not exists signal_embeddings_time_idx
    on public.signal_embeddings using gist (time_range);

create index if not exists signal_embeddings_asset_idx
    on public.signal_embeddings (asset_symbol);

create index if not exists signal_embeddings_embedding_idx
    on public.signal_embeddings using ivfflat (embedding vector_cosine_ops)
    with (lists = 32);
