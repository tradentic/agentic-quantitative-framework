-- Supabase automation for signal embedding workflows.

create table if not exists public.signal_embeddings (
  id bigint primary key generated always as identity,
  asset_id text not null,
  observed_at timestamptz not null,
  embedding vector(768) not null,
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists signal_embeddings_asset_observed_idx
  on public.signal_embeddings (asset_id, observed_at desc);

create extension if not exists vector;

create or replace function public.refresh_signal_embeddings(asset_ids text[], window_start timestamptz, window_end timestamptz, backfill boolean default false)
returns jsonb
language plpgsql
as $$
declare
  job_id uuid := gen_random_uuid();
begin
  insert into public.embedding_jobs(job_id, asset_ids, window_start, window_end, backfill)
  values (job_id, asset_ids, window_start, window_end, backfill);
  perform pg_notify('embedding_refresh', job_id::text);
  return jsonb_build_object('job_id', job_id);
end;
$$;

create or replace function public.prune_signal_embeddings(stale_before timestamptz, max_similarity double precision default 0.999, asset_universe text[] default null)
returns jsonb
language plpgsql
as $$
declare
  deleted_rows integer;
begin
  delete from public.signal_embeddings
  where observed_at < stale_before
    and (asset_universe is null or asset_id = any(asset_universe));
  get diagnostics deleted_rows = row_count;
  return jsonb_build_object('deleted_rows', deleted_rows);
end;
$$;

create or replace function public.run_strategy_backtest(strategy_id uuid, window_start timestamptz, window_end timestamptz, parameters jsonb)
returns jsonb
language plpgsql
as $$
begin
  return jsonb_build_object(
    'strategy_id', strategy_id,
    'window_start', window_start,
    'window_end', window_end,
    'parameters', coalesce(parameters, '{}'::jsonb)
  );
end;
$$;

create table if not exists public.embedding_jobs (
  job_id uuid primary key,
  asset_ids text[] not null,
  window_start timestamptz,
  window_end timestamptz,
  backfill boolean default false,
  created_at timestamptz not null default now()
);

create or replace function public.handle_new_embedding()
returns trigger
language plpgsql
as $$
begin
  perform pg_notify('embedding_ingested', row_to_json(NEW)::text);
  return new;
end;
$$;

create trigger signal_embedding_insert_trigger
  after insert on public.signal_embeddings
  for each row execute procedure public.handle_new_embedding();
