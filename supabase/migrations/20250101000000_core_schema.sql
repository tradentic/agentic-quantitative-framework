-- Core schema additions for filings, insider transactions, engineered features,
-- signal fingerprints, and text chunks with embeddings.

set search_path = public;

create table if not exists public.edgar_filings (
    filing_id bigserial primary key,
    cik text not null,
    form_type text not null,
    accession_number text not null,
    filed_at date not null,
    period_of_report date,
    company_name text,
    source_url text,
    metadata jsonb default '{}'::jsonb,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create unique index if not exists edgar_filings_accession_number_idx
    on public.edgar_filings (accession_number);

create index if not exists edgar_filings_cik_idx
    on public.edgar_filings (cik, filed_at desc);

create table if not exists public.insider_transactions (
    transaction_id bigserial primary key,
    filing_id bigint references public.edgar_filings (filing_id) on delete set null,
    insider_name text not null,
    insider_title text,
    relationship text,
    symbol text not null,
    transaction_date date not null,
    transaction_type text,
    shares numeric(20, 4),
    price numeric(20, 4),
    owned_shares numeric(20, 4),
    metadata jsonb default '{}'::jsonb,
    created_at timestamptz not null default timezone('utc', now())
);

create index if not exists insider_transactions_symbol_date_idx
    on public.insider_transactions (symbol, transaction_date desc);

create index if not exists insider_transactions_filing_idx
    on public.insider_transactions (filing_id);

create table if not exists public.daily_features (
    feature_id bigserial primary key,
    symbol text not null,
    feature_date date not null,
    feature_key text not null,
    feature_value double precision not null,
    metadata jsonb default '{}'::jsonb,
    created_at timestamptz not null default timezone('utc', now())
);

create unique index if not exists daily_features_symbol_date_key_idx
    on public.daily_features (symbol, feature_date, feature_key);

create table if not exists public.signal_fingerprints (
    fingerprint_id uuid primary key default gen_random_uuid(),
    signal_name text not null,
    as_of date not null,
    version text not null default 'v1',
    fingerprint vector(128) not null,
    stats jsonb default '{}'::jsonb,
    tags text[] default array[]::text[],
    metadata jsonb default '{}'::jsonb,
    created_at timestamptz not null default timezone('utc', now())
);

create unique index if not exists signal_fingerprints_identity_idx
    on public.signal_fingerprints (signal_name, as_of, version);

create index if not exists signal_fingerprints_signal_date_idx
    on public.signal_fingerprints (signal_name, as_of desc);

create index if not exists signal_fingerprints_vector_idx
    on public.signal_fingerprints using ivfflat (fingerprint vector_cosine_ops)
    with (lists = 100);

create table if not exists public.text_chunks (
    chunk_id bigserial primary key,
    filing_id bigint references public.edgar_filings (filing_id) on delete cascade,
    chunk_order integer not null,
    chunk text not null,
    embedding vector(1536) not null,
    metadata jsonb default '{}'::jsonb,
    created_at timestamptz not null default timezone('utc', now())
);

create unique index if not exists text_chunks_filing_order_idx
    on public.text_chunks (filing_id, chunk_order);

create index if not exists text_chunks_embedding_idx
    on public.text_chunks using ivfflat (embedding vector_cosine_ops)
    with (lists = 100);
