-- Feature registry demo entry
insert into public.feature_registry (name, version, path, meta)
values (
  'ts2vec_v1',
  '0.1.0',
  'features/generate_ts2vec_embeddings.py',
  '{"notes":"demo seed"}'
)
on conflict (name, version) do update set
  path = excluded.path,
  meta = excluded.meta;

insert into public.backtest_results (strategy_id, run_at, config, metrics, artifacts)
values (
  'demo_strategy',
  '2024-01-15T00:00:00+00',
  '{"strategy":"demo","strategy_id":"demo_strategy","window":"2024-01-01/2024-01-15"}',
  '{"sharpe":0.00,"max_drawdown":0.00,"n_trades":0}',
  '{"plots":["storage://backtests/demo_equity_curve.png"]}'
)
 on conflict do nothing;

insert into public.drift_events (metric, trigger_type, triggered_at, details)
values (
  'sharpe',
  'seed',
  '2024-01-15T00:00:00+00',
  '{"observed":0.0,"minimum":1.0,"context":{"source":"seed"}}'
)
on conflict do nothing;

-- Signal embeddings sample vector
insert into public.signal_embeddings (
  asset_symbol,
  time_range,
  embedding,
  emb_type,
  emb_version,
  regime_tag,
  label,
  meta
)
values (
  'AAPL',
  tstzrange('2024-01-02 09:30:00+00','2024-01-02 16:00:00+00','[)'),
  '[0.001,0.002,0.003,0.004,0.005,0.006,0.007,0.008,0.009,0.010,
    0.011,0.012,0.013,0.014,0.015,0.016,0.017,0.018,0.019,0.020,
    0.021,0.022,0.023,0.024,0.025,0.026,0.027,0.028,0.029,0.030,
    0.031,0.032,0.033,0.034,0.035,0.036,0.037,0.038,0.039,0.040,
    0.041,0.042,0.043,0.044,0.045,0.046,0.047,0.048,0.049,0.050,
    0.051,0.052,0.053,0.054,0.055,0.056,0.057,0.058,0.059,0.060,
    0.061,0.062,0.063,0.064,0.065,0.066,0.067,0.068,0.069,0.070,
    0.071,0.072,0.073,0.074,0.075,0.076,0.077,0.078,0.079,0.080,
    0.081,0.082,0.083,0.084,0.085,0.086,0.087,0.088,0.089,0.090,
    0.091,0.092,0.093,0.094,0.095,0.096,0.097,0.098,0.099,0.100,
    0.101,0.102,0.103,0.104,0.105,0.106,0.107,0.108,0.109,0.110,
    0.111,0.112,0.113,0.114,0.115,0.116,0.117,0.118,0.119,0.120,
    0.121,0.122,0.123,0.124,0.125,0.126,0.127,0.128]',
  'ts2vec',
  'v1',
  'demo',
  '{"y_next":0}',
  '{"notes":"seed"}'
)
on conflict (asset_symbol, time_range, emb_type, emb_version) do update set
  embedding = excluded.embedding,
  emb_type = excluded.emb_type,
  emb_version = excluded.emb_version,
  regime_tag = excluded.regime_tag,
  label = excluded.label,
  meta = excluded.meta;

-- Edgar Form 4 filing demo row
insert into public.edgar_filings (
    accession_number,
    cik,
    form_type,
    company_name,
    filing_date,
    filed_at,
    symbol,
    reporter,
    reporter_cik,
    xml_url,
    payload_sha256,
    xml_sha256,
    provenance
) values (
    '0000123456-24-000001',
    '0000123456',
    '4',
    'Acme Inc',
    '2024-12-31',
    '2024-12-31',
    'ACME',
    'John Doe',
    '0000554321',
    'https://www.sec.gov/Archives/edgar/data/0000123456/0000123456-24-000001/primary_doc.xml',
    'd5a1f28b39b0eae8e6a4df7fcb5a0aa32a4ed3d8f4e5c1d5a1475413b90fd0a8',
    '3f8f3b5d6f1a2a1234567890abcdef1234567890abcdef1234567890abcdef12',
    '{"parser_version":"form4-xml-v1","source":"seed"}'
)
on conflict (accession_number) do update set
    company_name = excluded.company_name,
    filing_date = excluded.filing_date,
    filed_at = excluded.filed_at,
    symbol = excluded.symbol,
    reporter = excluded.reporter,
    reporter_cik = excluded.reporter_cik,
    xml_url = excluded.xml_url,
    payload_sha256 = excluded.payload_sha256,
    xml_sha256 = excluded.xml_sha256,
    provenance = excluded.provenance;

-- Insider transactions tied to the demo filing
insert into public.insider_transactions (
    accession_number,
    insider_name,
    reporter_cik,
    symbol,
    transaction_date,
    transaction_code,
    shares,
    price
) values (
    '0000123456-24-000001',
    'John Doe',
    '0000554321',
    'ACME',
    '2024-12-30',
    'P',
    1000.0,
    10.5
)
on conflict (accession_number, transaction_date, transaction_code, symbol) do update set
    shares = excluded.shares,
    price = excluded.price,
    insider_name = excluded.insider_name,
    reporter_cik = excluded.reporter_cik;

-- FINRA daily features for the symbol
insert into public.daily_features (
    symbol,
    trade_date,
    short_vol_share,
    short_exempt_share,
    ats_share_of_total,
    feature_version,
    provenance
) values (
    'ACME',
    '2024-12-30',
    0.12,
    0.01,
    0.25,
    'offexchange-features-v1',
    '{"feature_version":"offexchange-features-v1","source":"seed"}'
)
on conflict (symbol, trade_date, feature_version) do update set
    short_vol_share = excluded.short_vol_share,
    short_exempt_share = excluded.short_exempt_share,
    ats_share_of_total = excluded.ats_share_of_total,
    feature_version = excluded.feature_version,
    provenance = excluded.provenance;

-- Demo fingerprint aligned to the new schema
insert into public.signal_fingerprints (
    id,
    signal_name,
    version,
    asset_symbol,
    window_start,
    window_end,
    fingerprint,
    provenance,
    meta
) values (
    '11111111-2222-3333-4444-555555555555',
    'demo_signal',
    'v2',
    'ACME',
    '2024-12-23',
    '2024-12-30',
    '[0.0078, 0.0156, 0.0234, 0.0312, 0.039, 0.0468, 0.0546, 0.0624, 0.0702, 0.078,
      0.0858, 0.0936, 0.1014, 0.1092, 0.117, 0.1248, 0.1326, 0.1404, 0.1482, 0.156,
      0.1638, 0.1716, 0.1794, 0.1872, 0.195, 0.2028, 0.2106, 0.2184, 0.2262, 0.234,
      0.2418, 0.2496, 0.2574, 0.2652, 0.273, 0.2808, 0.2886, 0.2964, 0.3042, 0.312,
      0.3198, 0.3276, 0.3354, 0.3432, 0.351, 0.3588, 0.3666, 0.3744, 0.3822, 0.39,
      0.3978, 0.4056, 0.4134, 0.4212, 0.429, 0.4368, 0.4446, 0.4524, 0.4602, 0.468,
      0.4758, 0.4836, 0.4914, 0.4992, 0.507, 0.5148, 0.5226, 0.5304, 0.5382, 0.546,
      0.5538, 0.5616, 0.5694, 0.5772, 0.585, 0.5928, 0.6006, 0.6084, 0.6162, 0.624,
      0.6318, 0.6396, 0.6474, 0.6552, 0.663, 0.6708, 0.6786, 0.6864, 0.6942, 0.702,
      0.7098, 0.7176, 0.7254, 0.7332, 0.741, 0.7488, 0.7566, 0.7644, 0.7722, 0.78,
      0.7878, 0.7956, 0.8034, 0.8112, 0.819, 0.8268, 0.8346, 0.8424, 0.8502, 0.858,
      0.8658, 0.8736, 0.8814, 0.8892, 0.897, 0.9048, 0.9126, 0.9204, 0.9282, 0.936,
      0.9438, 0.9516, 0.9594, 0.9672, 0.975, 0.9828, 0.9906, 0.9984]',
    '{"source":"seed","feature_version":"fingerprints-demo-v1"}',
    '{"ingested_by":"supabase/seed.sql"}'
)
on conflict (asset_symbol, window_start, window_end, version) do update set
    fingerprint = excluded.fingerprint,
    provenance = excluded.provenance,
    meta = excluded.meta;
