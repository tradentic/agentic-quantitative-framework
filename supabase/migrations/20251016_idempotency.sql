-- enforce idempotent writes for daily features and signal fingerprints
alter table if exists public.daily_features
  add column if not exists feature_version text not null default 'v1';

create unique index if not exists daily_features_uniq
  on public.daily_features (symbol, trade_date, feature_version);

alter table if exists public.signal_fingerprints
  add column if not exists version text not null default 'v1';

create unique index if not exists signal_fingerprints_uniq
  on public.signal_fingerprints (asset_symbol, window_start, window_end, version);
