set search_path = public;

create table if not exists public.drift_events (
    id uuid primary key default gen_random_uuid(),
    metric text not null,
    trigger_type text not null,
    triggered_at timestamptz not null default timezone('utc', now()),
    details jsonb not null default '{}'::jsonb
);

create index if not exists drift_events_metric_triggered_at_idx
    on public.drift_events (metric, triggered_at desc);
