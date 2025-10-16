-- Queue table for scheduled backtest runs orchestrated by Prefect.

create table if not exists public.backtest_requests (
    id uuid primary key default gen_random_uuid(),
    strategy_id text not null,
    config jsonb not null default '{}'::jsonb,
    status text not null default 'pending',
    created_at timestamptz not null default timezone('utc', now()),
    completed_at timestamptz
);

create index if not exists backtest_requests_status_idx
    on public.backtest_requests (status, created_at asc);
