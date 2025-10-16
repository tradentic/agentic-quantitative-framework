set search_path = public;

-- ---------------------------------------------------------------------------
-- Edgar filings alignment
-- ---------------------------------------------------------------------------
alter table if exists public.edgar_filings
    add column if not exists symbol text,
    add column if not exists reporter text,
    add column if not exists reporter_cik text,
    add column if not exists filing_date date,
    add column if not exists xml_url text,
    add column if not exists payload_sha256 text,
    add column if not exists xml_sha256 text,
    add column if not exists provenance jsonb default '{}'::jsonb;

do $$
begin
    if exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'edgar_filings'
          and column_name = 'filing_date'
    ) then
        update public.edgar_filings
        set filing_date = coalesce(filing_date, filed_at::date)
        where filing_date is null and filed_at is not null;
    end if;
end
$$;

-- ---------------------------------------------------------------------------
-- Insider transactions alignment
-- ---------------------------------------------------------------------------
alter table if exists public.insider_transactions
    add column if not exists accession_number text,
    add column if not exists transaction_code text,
    add column if not exists reporter_cik text,
    add column if not exists insider_name text;

create unique index if not exists insider_transactions_accession_date_code_symbol_idx
    on public.insider_transactions (accession_number, transaction_date, transaction_code, symbol);

-- ---------------------------------------------------------------------------
-- Daily features reshape for FINRA flow
-- ---------------------------------------------------------------------------
do $$
begin
    if exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'daily_features'
          and column_name = 'feature_date'
    ) then
        alter table public.daily_features rename column feature_date to trade_date;
    end if;
end
$$;

do $$
begin
    if exists (
        select 1
        from pg_indexes
        where schemaname = 'public'
          and indexname = 'daily_features_symbol_date_key_idx'
    ) then
        drop index if exists public.daily_features_symbol_date_key_idx;
    end if;
end
$$;

alter table if exists public.daily_features
    add column if not exists trade_date date,
    add column if not exists short_vol_share numeric(20, 4),
    add column if not exists short_exempt_share numeric(20, 4),
    add column if not exists ats_share_of_total numeric(20, 4),
    add column if not exists provenance jsonb default '{}'::jsonb;

alter table if exists public.daily_features
    drop column if exists feature_key,
    drop column if exists feature_value;

create unique index if not exists daily_features_symbol_trade_date_idx
    on public.daily_features (symbol, trade_date);

-- ---------------------------------------------------------------------------
-- Signal fingerprints alignment
-- ---------------------------------------------------------------------------
do $$
begin
    if exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'signal_fingerprints'
          and column_name = 'fingerprint_id'
    ) then
        alter table public.signal_fingerprints rename column fingerprint_id to id;
    end if;
end
$$;

do $$
begin
    if exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'signal_fingerprints'
          and column_name = 'as_of'
    ) then
        alter table public.signal_fingerprints rename column as_of to window_end;
    end if;
end
$$;

do $$
begin
    if exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'signal_fingerprints'
          and column_name = 'metadata'
    ) then
        alter table public.signal_fingerprints rename column metadata to meta;
    end if;
end
$$;

alter table if exists public.signal_fingerprints
    add column if not exists asset_symbol text,
    add column if not exists window_start date,
    add column if not exists provenance jsonb default '{}'::jsonb,
    add column if not exists meta jsonb default '{}'::jsonb;

update public.signal_fingerprints
set window_start = coalesce(window_start, window_end)
where window_end is not null and window_start is null;

drop index if exists public.signal_fingerprints_identity_idx;
create unique index if not exists signal_fingerprints_identity_idx
    on public.signal_fingerprints (signal_name, version, asset_symbol, window_start, window_end);
