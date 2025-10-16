-- RPC to enqueue embedding refresh jobs for downstream workers.

create or replace function public.rpc_refresh_embeddings(payload jsonb)
returns uuid
language plpgsql
as
$$
declare
    job_id uuid := coalesce((payload->>'id')::uuid, gen_random_uuid());
begin
    insert into public.embedding_jobs (id, asset_symbol, windows, metadata, status, created_at, updated_at)
    values (
        job_id,
        payload->>'asset_symbol',
        coalesce(payload->'windows', '[]'::jsonb),
        coalesce(payload->'metadata', '{}'::jsonb),
        coalesce(payload->>'status', 'pending'),
        timezone('utc', now()),
        timezone('utc', now())
    )
    on conflict (id) do update
        set asset_symbol = excluded.asset_symbol,
            windows = excluded.windows,
            metadata = excluded.metadata,
            status = 'pending',
            updated_at = timezone('utc', now());

    perform pg_notify('embedding_jobs', job_id::text);
    return job_id;
end;
$$;
