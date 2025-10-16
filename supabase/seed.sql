-- Seed data for local development of the Agentic Quantitative Framework.

insert into public.feature_registry (id, name, version, path, meta)
values (
  '00000000-0000-0000-0000-0000000000f1',
  'ts2vec_v1',
  '0.1.0',
  'features/generate_ts2vec_embeddings.py',
  '{"notes":"demo seed"}'::jsonb
)
on conflict (id) do update
  set path = excluded.path,
      meta = excluded.meta;

insert into public.backtest_results (id, config, metrics, artifacts)
values (
  '00000000-0000-0000-0000-0000000000b1',
  '{"strategy":"demo","window":"2024-01-01/2024-01-15"}'::jsonb,
  '{"sharpe":0.0,"max_drawdown":0.0,"n_trades":0}'::jsonb,
  '{"plots":["storage://backtests/demo_equity_curve.png"]}'::jsonb
)
on conflict (id) do update
  set config = excluded.config,
      metrics = excluded.metrics,
      artifacts = excluded.artifacts;

insert into public.signal_embeddings (id, asset_symbol, time_range, embedding, regime_tag, label, meta)
values (
  '00000000-0000-0000-0000-0000000000e1',
  'AAPL',
  tstzrange('2024-01-02 09:30:00+00','2024-01-02 16:00:00+00','[)'),
  '[0.001,0.002,0.003,0.004,0.005,0.006,0.007,0.008,0.009,0.01,0.011,0.012,0.013,0.014,0.015,0.016,0.017,0.018,0.019,0.02,0.021,0.022,0.023,0.024,0.025,0.026,0.027,0.028,0.029,0.03,0.031,0.032,0.033,0.034,0.035,0.036,0.037,0.038,0.039,0.04,0.041,0.042,0.043,0.044,0.045,0.046,0.047,0.048,0.049,0.05,0.051,0.052,0.053,0.054,0.055,0.056,0.057,0.058,0.059,0.06,0.061,0.062,0.063,0.064,0.065,0.066,0.067,0.068,0.069,0.07,0.071,0.072,0.073,0.074,0.075,0.076,0.077,0.078,0.079,0.08,0.081,0.082,0.083,0.084,0.085,0.086,0.087,0.088,0.089,0.09,0.091,0.092,0.093,0.094,0.095,0.096,0.097,0.098,0.099,0.1,0.101,0.102,0.103,0.104,0.105,0.106,0.107,0.108,0.109,0.11,0.111,0.112,0.113,0.114,0.115,0.116,0.117,0.118,0.119,0.12,0.121,0.122,0.123,0.124,0.125,0.126,0.127,0.128]'::vector(128),
  'demo',
  '{"y_next":0}'::jsonb,
  '{"notes":"seed"}'::jsonb
)
on conflict (id) do update
  set time_range = excluded.time_range,
      embedding = excluded.embedding,
      regime_tag = excluded.regime_tag,
      label = excluded.label,
      meta = excluded.meta;
