-- Provenance lineage table capturing per-record metadata hashes and fetch timestamps.
set search_path = public;

create table if not exists public.provenance_events (
    id uuid primary key default gen_random_uuid(),
    table_name text not null,
    record_id text not null,
    meta jsonb not null default '{}'::jsonb,
    observed_at timestamptz not null default timezone('utc', now()),
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create unique index if not exists provenance_events_table_record_uniq
    on public.provenance_events (table_name, record_id);

create or replace function public.touch_provenance_events_updated_at()
returns trigger
language plpgsql
as
$$
begin
    new.updated_at := timezone('utc', now());
    return new;
end;
$$;

drop trigger if exists provenance_events_set_updated_at on public.provenance_events;
create trigger provenance_events_set_updated_at
    before update on public.provenance_events
    for each row execute function public.touch_provenance_events_updated_at();

comment on table public.provenance_events is
    'Lineage audit log tying Supabase table rows to provenance metadata, hashes, and fetch context.';
