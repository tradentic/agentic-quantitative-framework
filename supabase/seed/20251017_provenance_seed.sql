insert into public.provenance_events (
    table_name,
    record_id,
    meta,
    observed_at
) values (
    'edgar_filings',
    '0000123456-24-000001',
    jsonb_build_object(
        'source_url', 'https://www.sec.gov/Archives/edgar/data/0000123456/0000123456-24-000001/primary_doc.xml',
        'parser_version', 'form4-xml-v1',
        'payload_sha256', 'd5a1f28b39b0eae8e6a4df7fcb5a0aa32a4ed3d8f4e5c1d5a1475413b90fd0a8',
        'fetched_at', '2024-12-31T01:00:00+00:00'
    ),
    '2024-12-31T01:05:00+00:00'
)
on conflict (table_name, record_id) do update set
    meta = excluded.meta,
    observed_at = excluded.observed_at,
    updated_at = timezone('utc', now());
