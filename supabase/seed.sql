-- Seed data for local development of the Agentic Quantitative Framework.

insert into public.feature_registry (feature_id, name, version, file_path, description, status, metadata)
values (
    '00000000-0000-0000-0000-000000000001',
    'ts2vec_price_window',
    'v1',
    'features/generate_ts2vec_embeddings.py',
    'Baseline TS2Vec embedding feature for price windows.',
    'active',
    jsonb_build_object('window', 64, 'horizon', '1h')
)
on conflict (feature_id) do update
    set description = excluded.description,
        status = excluded.status,
        metadata = excluded.metadata,
        updated_at = timezone('utc', now());

insert into public.signal_embeddings (id, asset_symbol, time_range, embedding, regime_tag, label, meta)
values (
    '00000000-0000-0000-0000-000000000101',
    'AAPL',
    '[2024-01-01 00:00:00+00,2024-01-01 01:00:00+00)'::tstzrange,
    '[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]'::vector(128),
    'calm',
    jsonb_build_object('label', 'baseline'),
    jsonb_build_object('source', 'seed', 't_stat', 0.8, 'regime_count', 5)
)
on conflict (id) do update
    set time_range = excluded.time_range,
        embedding = excluded.embedding,
        regime_tag = excluded.regime_tag,
        label = excluded.label,
        meta = excluded.meta,
        updated_at = timezone('utc', now());

insert into public.backtest_results (id, strategy_id, run_at, config, metrics, artifacts_path)
values (
    '00000000-0000-0000-0000-000000000201',
    'mean_reversion_v1',
    '2024-01-01T00:00:00+00:00',
    jsonb_build_object('lookback', 20, 'threshold', 1.5),
    jsonb_build_object('sharpe', 1.7, 'sortino', 2.3, 'max_drawdown', -0.12),
    'backtests/mean_reversion_v1/20240101000000/summary.json'
)
on conflict (id) do update
    set run_at = excluded.run_at,
        config = excluded.config,
        metrics = excluded.metrics,
        artifacts_path = excluded.artifacts_path;

insert into public.embedding_jobs (id, asset_symbol, windows, metadata, status)
values (
    '00000000-0000-0000-0000-000000000301',
    'AAPL',
    '[{"timestamp": "2024-01-02T00:00:00+00:00", "values": [1.0, 0.5, 0.25]}]'::jsonb,
    jsonb_build_object('priority', 'high'),
    'pending'
)
on conflict (id) do update
    set windows = excluded.windows,
        metadata = excluded.metadata,
        status = excluded.status,
        updated_at = timezone('utc', now());
