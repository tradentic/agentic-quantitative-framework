-- Supabase automation for signal embedding workflows and Prefect orchestration hooks.

create extension if not exists vector;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create or replace function public.rpc_queue_embedding_job(
  asset_symbol text,
  windows jsonb,
  metadata jsonb default '{}'::jsonb
)
returns uuid
language plpgsql
as $$
declare
  new_id uuid := gen_random_uuid();
begin
  insert into public.embedding_jobs (id, asset_symbol, windows, metadata, status)
  values (new_id, asset_symbol, coalesce(windows, '[]'::jsonb), coalesce(metadata, '{}'::jsonb), 'pending');
  return new_id;
end;
$$;

create or replace function public.rpc_prune_vectors(
  max_age_days integer default 90,
  min_t_stat double precision default 0.5,
  regime_diversity integer default 3,
  asset_universe text[] default null
)
returns jsonb
language plpgsql
as $$
declare
  cutoff timestamptz := now() - make_interval(days => max_age_days);
  archived_count integer := 0;
  deleted_count integer := 0;
begin
  if to_regclass('public.signal_embeddings_archive') is not null then
    insert into public.signal_embeddings_archive
      select *
      from public.signal_embeddings
      where created_at < cutoff
        and (asset_universe is null or asset_symbol = any(asset_universe));
    get diagnostics archived_count = row_count;
  end if;

  delete from public.signal_embeddings
  where created_at < cutoff
    and (asset_universe is null or asset_symbol = any(asset_universe));
  get diagnostics deleted_count = row_count;

  return jsonb_build_object(
    'archived_rows', archived_count,
    'deleted_rows', deleted_count,
    'criteria', jsonb_build_object(
      'max_age_days', max_age_days,
      'min_t_stat', min_t_stat,
      'regime_diversity', regime_diversity,
      'asset_universe', asset_universe
    )
  );
end;
$$;

create or replace function public.handle_new_embedding()
returns trigger
language plpgsql
as $$
begin
  perform pg_notify('embedding_ingested', row_to_json(new)::text);
  return new;
end;
$$;

-- Trigger wiring with explicit drops to remain idempotent.
drop trigger if exists signal_embeddings_set_updated_at on public.signal_embeddings;
create trigger signal_embeddings_set_updated_at
  before update on public.signal_embeddings
  for each row execute function public.set_updated_at();

drop trigger if exists signal_embeddings_insert_trigger on public.signal_embeddings;
create trigger signal_embeddings_insert_trigger
  after insert on public.signal_embeddings
  for each row execute function public.handle_new_embedding();

drop trigger if exists embedding_jobs_set_updated_at on public.embedding_jobs;
create trigger embedding_jobs_set_updated_at
  before update on public.embedding_jobs
  for each row execute function public.set_updated_at();

drop trigger if exists feature_registry_set_updated_at on public.feature_registry;
create trigger feature_registry_set_updated_at
  before update on public.feature_registry
  for each row execute function public.set_updated_at();

drop trigger if exists agent_state_set_updated_at on public.agent_state;
create trigger agent_state_set_updated_at
  before update on public.agent_state
  for each row execute function public.set_updated_at();

drop trigger if exists backtest_requests_set_updated_at on public.backtest_requests;
create trigger backtest_requests_set_updated_at
  before update on public.backtest_requests
  for each row execute function public.set_updated_at();

