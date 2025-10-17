create table if not exists public.drift_events (
    id bigserial primary key,
    metric text not null,
    trigger_type text not null,
    triggered_at timestamptz not null default now(),
    details jsonb not null default '{}'::jsonb
);

comment on table public.drift_events is 'Historical log of drift signals emitted by monitoring agents.';
comment on column public.drift_events.metric is 'Metric key associated with the drift trigger.';
comment on column public.drift_events.trigger_type is 'Origin or strategy for the trigger (e.g. threshold breach).';
comment on column public.drift_events.details is 'JSON payload capturing thresholds, summary statistics, and metadata.';
