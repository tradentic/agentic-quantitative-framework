set search_path = public;

-- Expand signal_embeddings idempotency to account for embedding type and version.
drop index if exists signal_embeddings_asset_time_range_uniq;

alter table if exists public.signal_embeddings
  add column if not exists emb_type text default 'ts2vec';

update public.signal_embeddings
  set emb_type = coalesce(emb_type, 'ts2vec');

alter table if exists public.signal_embeddings
  alter column emb_type set default 'ts2vec',
  alter column emb_type set not null;

alter table if exists public.signal_embeddings
  add column if not exists emb_version text default 'v1';

update public.signal_embeddings
  set emb_version = coalesce(emb_version, 'v1');

alter table if exists public.signal_embeddings
  alter column emb_version set default 'v1',
  alter column emb_version set not null;

create unique index if not exists signal_embeddings_identity_uniq
  on public.signal_embeddings (asset_symbol, time_range, emb_type, emb_version);
