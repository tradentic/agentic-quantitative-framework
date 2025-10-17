create table if not exists public.provenance_events (
    id bigserial primary key,
    source text not null,
    source_url text,
    payload jsonb not null,
    artifact_sha256 text,
    parser_version text,
    created_at timestamptz not null default now()
);
comment on table public.provenance_events is 'Write-only log of ETL/feature provenance records.';
