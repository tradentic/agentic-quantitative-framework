-- RPC stub that enqueues embedding refresh jobs for local development.

create or replace function public.rpc_refresh_embeddings(payload jsonb)
returns uuid
language plpgsql
as
$$
declare
    job_id uuid := coalesce((payload->>'id')::uuid, gen_random_uuid());
begin
    insert into public.embedding_jobs (id, asset_symbol, windows, metadata, status, created_at)
    values (
        job_id,
        payload->>'asset_symbol',
        payload->'windows',
        payload->'metadata',
        coalesce(payload->>'status', 'pending'),
        timezone('utc', now())
    )
    on conflict (id) do update
        set windows = excluded.windows,
            metadata = excluded.metadata,
            status = 'pending',
            updated_at = timezone('utc', now());

    perform pg_notify('embedding_jobs', job_id::text);
    return job_id;
end;
$$;
