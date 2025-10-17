insert into public.provenance_events (
    source,
    source_url,
    payload,
    artifact_sha256,
    parser_version
) values (
    'edgar_filings',
    'https://www.sec.gov/Archives/edgar/data/0000123456/0000123456-24-000001/primary_doc.xml',
    jsonb_build_object(
        'record_id', '0000123456-24-000001',
        'meta', jsonb_build_object(
            'fetched_at', '2024-12-31T01:00:00+00:00',
            'observed_at', '2024-12-31T01:05:00+00:00'
        )
    ),
    'd5a1f28b39b0eae8e6a4df7fcb5a0aa32a4ed3d8f4e5c1d5a1475413b90fd0a8',
    'form4-xml-v1'
);
