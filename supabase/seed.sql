-- Seed data for local development of the Agentic Quantitative Framework.

insert into public.feature_registry (id, name, version, path, description, status, meta)
values (
    '00000000-0000-0000-0000-000000000001',
    'ts2vec_v1',
    'v1',
    'features/generate_ts2vec_embeddings.py',
    'Baseline TS2Vec embedding feature for price windows.',
    'active',
    jsonb_build_object('window', 64, 'horizon', '1h')
)
on conflict (id) do update
    set description = excluded.description,
        status = excluded.status,
        meta = excluded.meta,
        updated_at = timezone('utc', now());

insert into public.signal_embeddings (id, asset_symbol, time_range, embedding, regime_tag, label, meta)
values (
    '00000000-0000-0000-0000-000000000101',
    'AAPL',
    '[2024-01-01 00:00:00+00,2024-01-01 01:00:00+00)'::tstzrange,
    '[0.3444, 0.258, -0.0794, -0.2411, 0.0113, -0.0951, 0.2838, -0.1967, -0.0234, 0.0834, 0.4081, 0.0047, -0.2182, 0.2558, 0.1184, -0.2495, 0.4097, 0.4828, 0.3102, 0.4022, -0.1899, 0.2298, 0.3988, 0.184, -0.0279, -0.3993, -0.0658, 0.1109, 0.413, 0.4666, -0.023, 0.3653, -0.2395, 0.305, 0.0487, -0.486, 0.2197, -0.1012, 0.3248, 0.1682, -0.4989, -0.0064, 0.3676, -0.2561, -0.1748, 0.3705, -0.3089, 0.0675, -0.2614, 0.4675, 0.3032, -0.052, -0.4196, -0.1799, 0.0079, 0.4328, -0.3909, 0.0513, 0.2066, 0.0474, 0.3145, 0.0403, 0.4638, 0.1032, 0.0876, -0.055, 0.0963, -0.1151, 0.0757, -0.2097, -0.3106, -0.3133, 0.1128, 0.1567, -0.0235, -0.4102, 0.2576, 0.3768, 0.4234, 0.3425, 0.3982, 0.4231, 0.0406, -0.1087, 0.2053, -0.2244, 0.3116, 0.3495, 0.395, 0.0898, 0.4498, 0.0797, -0.0494, 0.1602, 0.4963, 0.4169, 0.2933, -0.4176, 0.1128, -0.0136, 0.1301, 0.3451, -0.257, 0.2315, -0.3829, -0.2795, 0.2946, -0.1675, 0.3159, -0.3994, -0.3536, 0.1977, -0.4548, 0.0739, 0.41, 0.0342, 0.1806, -0.4733, 0.135, 0.1063, 0.076, -0.1088, -0.1299, 0.4805, -0.4636, -0.4784, 0.461, -0.315]'::vector(128),
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

insert into public.backtest_results (id, config, metrics, artifacts)
values (
    '00000000-0000-0000-0000-000000000201',
    jsonb_build_object('strategy_id', 'mean_reversion_v1', 'lookback', 20, 'threshold', 1.5),
    jsonb_build_object('sharpe', 1.7, 'sortino', 2.3, 'max_drawdown', -0.12),
    jsonb_build_object(
        'summary', 'model-artifacts/backtests/mean_reversion_v1/20240101000000/summary.json',
        'plot', 'model-artifacts/backtests/mean_reversion_v1/20240101000000/equity_curve.png'
    )
)
on conflict (id) do update
    set config = excluded.config,
        metrics = excluded.metrics,
        artifacts = excluded.artifacts,
        created_at = timezone('utc', now());

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
