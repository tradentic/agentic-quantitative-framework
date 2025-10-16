set search_path = public;

-- daily_features idempotent writes keyed by (symbol, trade_date, feature_version)
drop index if exists public.daily_features_symbol_trade_date_idx;

alter table if exists public.daily_features
  add column if not exists feature_version text not null default 'v1';

create unique index if not exists daily_features_uniq
  on public.daily_features (symbol, trade_date, feature_version);

-- signal_fingerprints idempotent writes keyed by (asset_symbol, window_start, window_end, version)
drop index if exists public.signal_fingerprints_identity_idx;

alter table if exists public.signal_fingerprints
  add column if not exists version text not null default 'v1';

create unique index if not exists signal_fingerprints_uniq
  on public.signal_fingerprints (asset_symbol, window_start, window_end, version);
