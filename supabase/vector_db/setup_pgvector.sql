-- Enable required extensions
create extension if not exists "pgcrypto";
create extension if not exists vector;

-- Dedicated schema for quantitative feature memory
create schema if not exists quant_signals;

create table if not exists quant_signals.feature_vectors (
    id uuid primary key default gen_random_uuid(),
    feature_name text not null,
    dimension int not null,
    embedding vector(1536) not null,
    metadata jsonb default '{}'::jsonb,
    created_at timestamptz default timezone('utc', now())
);

create index if not exists feature_vectors_embedding_idx
    on quant_signals.feature_vectors
    using ivfflat (embedding vector_cosine_ops)
    with (lists = 100);

create index if not exists feature_vectors_created_idx
    on quant_signals.feature_vectors (created_at);
